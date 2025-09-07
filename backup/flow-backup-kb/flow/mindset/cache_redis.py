"""
Redis Cache Manager Module

A comprehensive caching system using Redis with RedisSearch (FT) for vector similarity search.
Provides TTL-based caching, embedding storage, and KNN search capabilities.

Architecture:
- Redis HASH storage with per-key TTL (row-based TTL)
- RedisSearch FT index for text and vector search
- Support for tenant-based multi-tenancy
- Automatic index creation and management
- Vector embedding storage and similarity search

Key Features:
- Text and embedding caching with configurable TTL
- KNN search using cosine similarity
- Tenant and user-based filtering
- Automatic cache expiration
- Batch operations support
- Error handling and logging
"""

import time
import json
import hashlib
import logging
from array import array
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

import redis
from redis.exceptions import ResponseError, ConnectionError as RedisConnectionError

from .config import Config
from .utils import Utils


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata"""
    text: str
    tenant: str
    user: str
    created_at: int
    embedding: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        data = {
            "text": self.text,
            "tenant": self.tenant,
            "user": self.user,
            "created_at": self.created_at
        }
        if self.embedding is not None:
            data["embedding"] = self.embedding
        return data


@dataclass
class SearchResult:
    """Represents a search result with similarity score"""
    id: str
    text: str
    user: str
    score: float


class CacheManager:
    """
    Redis-based cache manager with vector search capabilities.

    Provides caching for text content with automatically generated embeddings and supports
    KNN search for similarity matching using RedisSearch.
    """

    def __init__(self, config: Config, llm_manager=None, logger: Optional[logging.Logger] = None):
        """
        Initialize CacheManager with configuration.

        Args:
            config: Configuration object containing cache settings
            llm_manager: LLM manager instance for generating embeddings
            logger: Optional logger instance
        """
        self.config = config
        self.llm_manager = llm_manager
        self.logger = logger or logging.getLogger(__name__)

        # Initialize Utils for base64 operations
        self.utils = Utils(config, self.logger)

        # Cache configuration
        self.redis_url = self.config.cache_redis_url
        self.index_name = self.config.cache_index_name
        self.key_prefix = self.config.cache_key_prefix
        self.embedding_dim = self.config.cache_embedding_dimensions
        self.default_ttl = self.config.cache_default_ttl

        # Redis connection
        self._redis_client: Optional[redis.Redis] = None

        # Initialize on first use
        self._initialized = False

        # Fault tolerance configuration - enables graceful degradation when cache fails
        self._fault_tolerant = self.config.cache_fault_tolerant

    @property
    def redis_client(self) -> redis.Redis:
        """Get Redis client instance, creating if necessary"""
        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis.from_url(self.redis_url)
                # Test connection
                self._redis_client.ping()
                self.logger.debug("Success connected to Redis")
            except Exception as e:
                self.logger.error("Failed to connect to Redis: %s", e)
                raise
        return self._redis_client

    def ensure_index(self) -> bool:
        """
        Ensure RedisSearch index exists, create if necessary.

        Returns:
            bool: True if index exists or was created successfully
        """
        try:
            # Check if index already exists
            self.redis_client.execute_command("FT.INFO", self.index_name)
            self.logger.debug("Cache index %s already exists", self.index_name)
            return True
        except ResponseError:
            # Index doesn't exist, create it
            pass

        try:
            # Create FT index with FLAT vector algorithm (simple but reliable)
            # For production, consider HNSW for better performance
            create_cmd = [
                "FT.CREATE", self.index_name,
                "ON", "HASH",
                "PREFIX", 1, self.key_prefix,
                "SCHEMA",
                    "text", "TEXT", "NOSTEM", "WEIGHT", "1.0",  # NOSTEM for better Russian support
                    "tenant", "TAG",
                    "user", "TAG",
                    "created_at", "NUMERIC", "SORTABLE"
            ]

            # Add vector field only if embeddings are enabled
            if self.config.cache_enable_embeddings:
                create_cmd.extend([
                    "embedding", "VECTOR", "FLAT", "6",
                        "TYPE", "FLOAT32",
                        "DIM", self.embedding_dim,
                        "DISTANCE_METRIC", "COSINE"
                ])

            self.logger.debug("Creating Redis index with command: %s", " ".join(map(str, create_cmd)))
            self.redis_client.execute_command(*create_cmd)
            self.logger.info("Created cache index %s with embedding support: %s",
                           self.index_name, self.config.cache_enable_embeddings)
            return True

        except Exception as e:
            self.logger.error("Failed to create cache index: %s", e)
            self.logger.error("Index creation command was: %s", " ".join(map(str, create_cmd)) if 'create_cmd' in locals() else 'N/A')
            return False

    def _initialize(self):
        """Initialize the cache system if not already done"""
        if not self._initialized:
            if self.ensure_index():
                self._initialized = True
            else:
                raise RuntimeError("Failed to initialize cache index")

    def _escape_tag_value(self, value: Union[str, int, float, None]) -> str:
        """
        Escape TAG field values for RedisSearch queries.

        RedisSearch TAG fields require escaping of special characters,
        particularly important for numeric values that might be interpreted
        as numeric literals instead of string tags.

        Args:
            value: The tag value to escape (will be converted to string if not already)

        Returns:
            str: Escaped value safe for use in RedisSearch TAG queries
        """
        if value is None:
            return ""

        # Convert to string if not already (handles int, float, etc.)
        value_str = str(value)

        if not value_str:
            return value_str

        # Escape common special characters in RedisSearch
        # Note: Curly braces {} are used for exact matching, so we don't escape them
        escaped = value_str.replace('-', '\\-').replace(':', '\\:').replace('@', '\\@')

        # For purely numeric values, we might need additional handling
        # but the curly brace syntax should handle most cases
        return escaped

    def _hash_user_id(self, user_id: Union[str, int, None]) -> str:
        """
        Generate SHA1 hash of user ID to avoid escaping issues.

        Telegram user IDs can be large integers that cause escaping issues
        in RedisSearch queries. Using SHA1 hash provides a consistent,
        alphanumeric string that doesn't require escaping.

        Args:
            user_id: User identifier (telegram ID, email, etc.)

        Returns:
            str: SHA1 hash of the user ID, or empty string if None
        """
        if user_id is None:
            return ""

        # Convert to string and generate SHA1 hash
        user_str = str(user_id)
        return hashlib.sha1(user_str.encode("utf-8")).hexdigest()

    def _qhash(self, s: str) -> str:
        """Generate short hash from string for key generation"""
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

    def _pack_f32(self, vec: List[float]) -> bytes:
        """Pack float list to bytes for Redis storage"""
        if len(vec) != self.embedding_dim:
            raise ValueError(f"Embedding dimension {len(vec)} != {self.embedding_dim}")
        return array('f', vec).tobytes()

    def _unpack_f32(self, data: bytes) -> List[float]:
        """Unpack bytes to float list"""
        return array('f', data).tolist()

    def _generate_key(self, tenant: str, key_signature: str) -> str:
        """Generate cache key from tenant and signature"""
        return f"{self.key_prefix}{tenant}:{self._qhash(key_signature)}"

    def put_cache(self,
                  tenant: str,
                  user: str,
                  key_signature: str,
                  text: str,
                  ttl_seconds: Optional[int] = 86400) -> str:
        """
        Store cache entry with automatically generated embedding.

        Args:
            tenant: Tenant identifier (e.g., organization, environment)
            user: User identifier (will be hashed for safe storage)
            key_signature: Unique signature for the cache key
            text: Text content to cache (embedding will be generated from this)
            ttl_seconds: TTL in seconds (uses default if 24h (in seconds = 86400 ))

        Returns:
            str: Generated cache key
        """
        self._initialize()

        # Ensure text is a string - if it's not, convert it
        if not isinstance(text, str):
            if isinstance(text, (list, dict)):
                text = json.dumps(text, ensure_ascii=False)
                self.logger.debug("Converted non-string input to JSON: %s", type(text).__name__)
            else:
                text = str(text)
                self.logger.debug("Converted non-string input to string: %s", type(text).__name__)

        key = self._generate_key(tenant, key_signature)
        ttl = ttl_seconds or self.default_ttl

        # Hash user ID to avoid escaping issues
        user_hash = self._hash_user_id(user)

        # Prepare cache entry
        entry_data = {
            "text": text,
            "tenant": tenant,
            "user": user_hash,  # Store hashed user ID
            "created_at": int(time.time())
        }

        # Generate and add embedding if enabled and LLM manager is available
        if self.config.cache_enable_embeddings and self.llm_manager is not None:
            try:
                embedding = self.llm_manager.embd_text(text)
                if embedding and isinstance(embedding, list):
                    entry_data["embedding"] = self._pack_f32(embedding)
                    self.logger.debug("Generated embedding for cache entry (dim: %d)", len(embedding))
                else:
                    self.logger.warning("Failed to generate embedding for text: %s", text[:50])
            except Exception as e:
                self.logger.error("Failed to generate embedding: %s", e)
                # Continue without embedding
        try:
            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.hset(key, mapping=entry_data)
            pipe.expire(key, ttl)
            pipe.execute()

            self.logger.debug("Cached entry for key %s (tenant: %s, user: %s, ttl: %ds)",
                            key, tenant, user, ttl)
            return key

        except Exception as e:
            self.logger.error("Failed to cache entry: %s", e)
            raise

    def get_cache(self,
                  key: str,
                  extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cache entry by key.

        Args:
            key: Cache key
            extend_ttl_seconds: Optional TTL extension

        Returns:
            Dict with cache entry data or None if not found
        """
        self._initialize()

        try:
            if extend_ttl_seconds:
                # Atomic get + TTL extension
                pipe = self.redis_client.pipeline()
                pipe.hgetall(key)
                pipe.expire(key, extend_ttl_seconds)
                results = pipe.execute()
                data = results[0]
            else:
                data = self.redis_client.hgetall(key)

            if not data:
                return None

            # Convert bytes to strings for text fields
            result = {
                "text": data.get(b"text", b"").decode("utf-8"),
                "tenant": data.get(b"tenant", b"").decode("utf-8"),
                "user": data.get(b"user", b"").decode("utf-8"),  # This is the hashed user ID
                "created_at": int(data.get(b"created_at", b"0"))
            }

            # Include embedding if present (but don't decode it)
            if b"embedding" in data:
                result["embedding"] = data[b"embedding"]

            self.logger.debug("Retrieved cache entry for key %s", key)
            return result

        except Exception as e:
            self.logger.error("Failed to retrieve cache entry: %s", e)
            return None

    def get_cache_by_signature(self,
                             tenant: str,
                             key_signature: str,
                             extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cache entry by tenant and signature.

        Args:
            tenant: Tenant identifier
            key_signature: Key signature
            extend_ttl_seconds: Optional TTL extension

        Returns:
            Dict with cache entry data or None if not found
        """
        key = self._generate_key(tenant, key_signature)
        return self.get_cache(key, extend_ttl_seconds)

    def delete_cache(self, key: str) -> bool:
        """
        Delete cache entry by key.

        Args:
            key: Cache key to delete

        Returns:
            bool: True if entry was deleted, False if not found
        """
        try:
            result = self.redis_client.delete(key)
            if result > 0:
                self.logger.debug("Deleted cache entry %s", key)
                return True
            return False
        except Exception as e:
            self.logger.error("Failed to delete cache entry: %s", e)
            return False

    def knn_search(self,
                   tenant: str,
                   query_vector: List[float],
                   k: int = 10,
                   user: Optional[str] = None,
                   additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform KNN similarity search using embeddings.

        Args:
            tenant: Tenant to search within
            query_vector: Query embedding vector
            k: Number of results to return
            user: Optional user filter (will be hashed for searching)
            additional_filters: Optional additional RedisSearch filters

        Returns:
            Dict with total count and search hits
        """
        if not self.config.cache_enable_embeddings:
            raise ValueError("Embeddings are not enabled in cache configuration")

        self._initialize()

        try:
            # Pack query vector
            vec_bytes = self._pack_f32(query_vector)

            # Build filter query with proper RedisSearch syntax
            # Use wildcard base query with explicit filters
            filters = []
            filters.append(f'@tenant:{{{tenant}}}')
            if user:
                # Hash user ID instead of escaping to avoid special characters
                user_hash = self._hash_user_id(user)
                filters.append(f'@user:{{{user_hash}}}')
            if additional_filters:
                filters.append(additional_filters)

            # Combine filters with AND logic
            if len(filters) == 1:
                base_filter = filters[0]
            else:
                # Use explicit parentheses with space separation for AND logic
                base_filter = '(' + ' '.join(filters) + ')'

            self.logger.debug("KNN search filter: %s", base_filter)

            # For KNN with filters, use the filter in the query part
            knn_query = f'({base_filter})=>[KNN {k} @embedding $vec AS score]'

            # Execute KNN search with DIALECT 2 for modern syntax
            search_cmd = [
                "FT.SEARCH", self.index_name,
                knn_query,
                "PARAMS", 2, "vec", vec_bytes,
                "SORTBY", "score",
                "RETURN", 3, "text", "user", "score",
                "DIALECT", 2,
                "LIMIT", 0, k
            ]

            self.logger.debug("KNN search command: %s", ' '.join(map(str, search_cmd[:3])))

            result = self.redis_client.execute_command(*search_cmd)

            # Parse results: [total_count, doc_id, fields, doc_id, fields, ...]
            total = result[0]
            hits = []

            for i in range(1, len(result), 2):
                doc_id = result[i].decode() if isinstance(result[i], bytes) else str(result[i])
                fields = result[i + 1]

                # Parse field-value pairs
                field_data = {}
                for j in range(0, len(fields), 2):
                    field_name = fields[j].decode() if isinstance(fields[j], bytes) else str(fields[j])
                    field_value = fields[j + 1]
                    if isinstance(field_value, bytes):
                        field_value = field_value.decode()
                    field_data[field_name] = field_value

                hit = SearchResult(
                    id=doc_id,
                    text=field_data.get("text", ""),
                    user=field_data.get("user", ""),
                    score=float(field_data.get("score", 0.0))
                )
                hits.append(hit)

            self.logger.debug("KNN search returned %d results for tenant %s", len(hits), tenant)
            return {
                "total": total,
                "hits": [{"id": h.id, "text": h.text, "user": h.user, "score": h.score} for h in hits]
            }

        except Exception as e:
            self.logger.error("KNN search failed: %s", e)
            self.logger.error("KNN search details - tenant: %s, user: %s, k: %d", tenant, user, k)
            if 'knn_query' in locals():
                self.logger.error("Failed KNN query: %s", knn_query)
            if 'search_cmd' in locals():
                self.logger.error("Failed search command: %s", ' '.join(map(str, search_cmd[:5])))
            return {"total": 0, "hits": []}

    def semantic_search(self,
                       tenant: str,
                       query_text: str,
                       k: int = 10,
                       user: Optional[str] = None,
                       additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform semantic similarity search using text query (generates embedding internally).

        Args:
            tenant: Tenant to search within
            query_text: Text query (embedding will be generated from this)
            k: Number of results to return
            user: Optional user filter
            additional_filters: Optional additional RedisSearch filters

        Returns:
            Dict with total count and search hits
        """
        if not self.config.cache_enable_embeddings:
            raise ValueError("Embeddings are not enabled in cache configuration")

        if not self.llm_manager:
            raise ValueError("LLM manager is required for semantic search")

        try:
            # Generate embedding from text
            query_embedding = self.llm_manager.embd_text(query_text)
            if not query_embedding or not isinstance(query_embedding, list):
                self.logger.error("Failed to generate embedding for query text: %s", query_text[:50])
                return {"total": 0, "hits": []}

            # Perform KNN search with generated embedding
            return self.knn_search(tenant, query_embedding, k, user, additional_filters)

        except Exception as e:
            self.logger.error("Semantic search failed: %s", e)
            return {"total": 0, "hits": []}

    def text_search(self,
                    tenant: str,
                    query: str,
                    user: Optional[str] = None,
                    limit: int = 10,
                    offset: int = 0) -> Dict[str, Any]:
        """
        Perform full-text search on cached content.

        Args:
            tenant: Tenant to search within
            query: Text query
            user: Optional user filter (will be hashed for searching)
            limit: Maximum results to return (max 1000)
            offset: Results offset

        Returns:
            Dict with total count and search hits, empty if cache fails
        """
        try:
            self._initialize()

            # Skip cache operations if initialization failed in fault-tolerant mode
            if not self._initialized:
                self.logger.debug("Cache not initialized, skipping text_search operation")
                return {"total": 0, "hits": []}

            # Validate and clamp limit to Redis maximum
            max_limit = 1000  # Conservative limit well below Redis max

            # Ensure limit is an integer
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                self.logger.warning("Invalid limit value %s, using default 10", limit)
                limit = 10

            if limit > max_limit:
                self.logger.warning("Limit %d exceeds maximum %d, clamping to maximum", limit, max_limit)
                limit = max_limit

            if limit < 0:
                limit = 10  # Default

            # Ensure offset is an integer
            try:
                offset = int(offset)
            except (ValueError, TypeError):
                self.logger.warning("Invalid offset value %s, using default 0", offset)
                offset = 0

            if offset < 0:
                offset = 0

            # Build filter with proper RedisSearch syntax
            filters = []
            filters.append(f'@tenant:{{{tenant}}}')
            if user:
                # Hash user ID instead of escaping to avoid special characters
                user_hash = self._hash_user_id(user)
                filters.append(f'@user:{{{user_hash}}}')

            # Escape the search query for safe text search
            escaped_query = self.utils._escape_search_text(query.strip())

            if not escaped_query:
                self.logger.warning("Empty search query after escaping")
                return {"total": 0, "hits": []}

            # Build the search query with multiple approaches for better matching
            # Try exact phrase match, prefix match, and fuzzy match
            text_queries = []

            # 1. Exact phrase search (if query has spaces)
            if ' ' in escaped_query:
                text_queries.append(f'"{escaped_query}"')

            # 2. Prefix match for partial word matching (good for Cyrillic)
            text_queries.append(f'{escaped_query}*')

            # 3. Individual words with OR logic
            words = escaped_query.split()
            if len(words) > 1:
                word_query = '|'.join(words)
                text_queries.append(f'({word_query})')
            else:
                # Single word - also try without asterisk
                text_queries.append(escaped_query)

            # Combine text queries with OR logic
            combined_text_query = '|'.join(text_queries)

            # Combine filters
            if len(filters) == 1:
                base_filter = filters[0]
            else:
                base_filter = '(' + ' '.join(filters) + ')'

            # Final query combining filters and text search
            full_query = f'{base_filter} @text:({combined_text_query})'

            self.logger.debug("Text search query: %s", full_query)
            self.logger.debug("Original query: '%s', Escaped: '%s'", query, escaped_query)

            # Execute search
            search_cmd = [
                "FT.SEARCH", self.index_name, full_query,
                "RETURN", 3, "text", "user", "created_at",
                "LIMIT", offset, limit
            ]

            result = self.redis_client.execute_command(*search_cmd)

            # Parse results
            total = result[0]
            hits = []

            for i in range(1, len(result), 2):
                doc_id = result[i].decode() if isinstance(result[i], bytes) else str(result[i])
                fields = result[i + 1]

                # Parse field-value pairs
                field_data = {}
                for j in range(0, len(fields), 2):
                    field_name = fields[j].decode() if isinstance(fields[j], bytes) else str(fields[j])
                    field_value = fields[j + 1]
                    if isinstance(field_value, bytes):
                        field_value = field_value.decode()
                    field_data[field_name] = field_value

                hits.append({
                    "id": doc_id,
                    "text": field_data.get("text", ""),
                    "user": field_data.get("user", ""),
                    "created_at": int(field_data.get("created_at", 0))
                })

            self.logger.debug("Text search returned %d results for query: %s", len(hits), query)
            return {"total": total, "hits": hits}

        except Exception as e:
            self.logger.error("Text search failed: %s", e)
            self.logger.error("Text search details - tenant: %s, user: %s, query: %s", tenant, user, query)
            if 'full_query' in locals():
                self.logger.error("Failed search query: %s", full_query)
            if self._fault_tolerant:
                self.logger.warning("Continuing without cache due to text search error")
                return {"total": 0, "hits": []}
            raise

    def clear_tenant_cache(self, tenant: str) -> int:
        """
        Clear all cache entries for a specific tenant.

        Args:
            tenant: Tenant identifier

        Returns:
            int: Number of entries deleted, 0 if cache fails
        """
        try:
            self._initialize()

            # Skip cache operations if initialization failed in fault-tolerant mode
            if not self._initialized:
                self.logger.debug("Cache not initialized, skipping clear_tenant_cache operation")
                return 0

            # Search for all keys with this tenant - use reasonable batch size
            batch_size = 1000  # Process in batches to avoid large result sets
            total_deleted = 0
            offset = 0

            while True:
                search_result = self.redis_client.execute_command(
                    "FT.SEARCH", self.index_name, f'@tenant:{{{tenant}}}',
                    "RETURN", 0,  # Only return document IDs
                    "LIMIT", offset, batch_size
                )

                total_found = search_result[0]
                if total_found == 0 or len(search_result) <= 1:
                    break

                # Extract document IDs (they are the Redis keys)
                keys_to_delete = []
                for i in range(1, len(search_result), 2):
                    key = search_result[i].decode() if isinstance(search_result[i], bytes) else str(search_result[i])
                    keys_to_delete.append(key)

                # Delete this batch
                if keys_to_delete:
                    deleted = self.redis_client.delete(*keys_to_delete)
                    total_deleted += deleted
                    self.logger.debug("Deleted %d cache entries in batch for tenant %s", deleted, tenant)

                # If we got fewer results than batch size, we're done
                if len(keys_to_delete) < batch_size:
                    break

                offset += batch_size

            if total_deleted > 0:
                self.logger.info("Cleared %d cache entries for tenant %s", total_deleted, tenant)
            return total_deleted

        except Exception as e:
            self.logger.error("Failed to clear tenant cache: %s", e)
            if self._fault_tolerant:
                self.logger.warning("Continuing without cache due to clear tenant cache error")
                return 0
            raise

    def get_cache_stats(self, tenant: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache statistics.

        Args:
            tenant: Optional tenant filter

        Returns:
            Dict with cache statistics, empty if cache fails
        """
        try:
            self._initialize()

            # Skip cache operations if initialization failed in fault-tolerant mode
            if not self._initialized:
                self.logger.debug("Cache not initialized, skipping get_cache_stats operation")
                return {"total_documents": 0, "index_size": 0}

            # Get index info
            index_info = self.redis_client.execute_command("FT.INFO", self.index_name)
            self.logger.debug("Index info retrieved with %d items", len(index_info))

            # Parse index info
            stats = self._parse_redis_info_response(index_info)
            self.logger.debug("Index info stats", extra={"index_info": stats})
            # Get tenant-specific stats if requested
            if tenant:
                # Use count-only query to avoid LIMIT issues
                search_result = self.redis_client.execute_command(
                    "FT.SEARCH", self.index_name, f'@tenant:{{{tenant}}}',
                    "LIMIT", 0, 0  # Count only - this should be safe
                )
                stats["tenant_documents"] = search_result[0]

            return stats

        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            if self._fault_tolerant:
                self.logger.warning("Continuing without cache due to get cache stats error")
                return {"total_documents": 0, "index_size": 0}
            raise

    def _parse_value_recursively(self, value: Any) -> Any:
        """
        Recursively parse a value that may contain nested lists with byte strings.

        Args:
            value: The value to parse (can be bytes, list, or other types)

        Returns:
            Parsed value with all byte strings decoded and base64 decoded if applicable
        """
        if isinstance(value, bytes):
            # Decode bytes to string and try base64 decoding
            decoded_str = value.decode('utf-8', errors='ignore')
            return self.utils._try_decode_base64(decoded_str)
        elif isinstance(value, list):
            # Recursively parse each item in the list
            parsed_list = []
            for item in value:
                parsed_item = self._parse_value_recursively(item)
                parsed_list.append(parsed_item)
            return parsed_list
        elif isinstance(value, str):
            # Try base64 decoding on string values
            return self.utils._try_decode_base64(value)
        else:
            # Return other types as-is (int, float, None, etc.)
            return value
    def _parse_redis_info_response(self, redis_info: List) -> Dict[str, Any]:
        """
        Parse Redis FT.INFO response into a readable dictionary format.

        Redis returns info as a flat list: [key1, value1, key2, value2, ...]
        This function converts it to a proper dictionary with decoded strings.
        Some keys and values may be base64 encoded and will be automatically decoded.
        Values can contain complex nested structures with byte strings.

        Args:
            redis_info: Raw response from FT.INFO command

        Returns:
            Dict with parsed and decoded information
        """
        parsed_info = {}

        for i in range(0, len(redis_info), 2):
            # Decode key
            raw_key = redis_info[i].decode() if isinstance(redis_info[i], bytes) else str(redis_info[i])
            key = self.utils._try_decode_base64(raw_key)

            # Parse value recursively to handle nested structures
            value = redis_info[i + 1]
            parsed_value = self._parse_value_recursively(value)

            parsed_info[key] = parsed_value

        return parsed_info

    def get_index_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the RedisSearch index.

        Returns:
            Dict with index information
        """
        try:
            self._initialize()

            if not self._initialized:
                return {"error": "Cache not initialized"}

            # Get index info
            index_info = self.redis_client.execute_command("FT.INFO", self.index_name)

            # Parse the info into a more readable format
            return self._parse_redis_info_response(index_info)

        except Exception as e:
            return {"error": str(e)}

    def get_user_hash(self, user_id: Union[str, int, None]) -> str:
        """
        Get SHA1 hash of user ID for external use.

        This method allows external code to generate the same hash
        that's used internally for user filtering in searches.

        Args:
            user_id: User identifier to hash

        Returns:
            str: SHA1 hash of the user ID
        """
        return self._hash_user_id(user_id)

    def health_check(self) -> Dict[str, Any]:
        """
        Perform cache health check.

        Returns:
            Dict with health status, never raises in fault-tolerant mode
        """
        try:
            # Test Redis connection
            self.redis_client.ping()

            # Test index existence
            index_exists = False
            try:
                self.redis_client.execute_command("FT.INFO", self.index_name)
                index_exists = True
            except ResponseError:
                pass

            return {
                "redis_connected": True,
                "index_exists": index_exists,
                "index_name": self.index_name,
                "fault_tolerant": self._fault_tolerant
            }

        except Exception as e:
            self.logger.error("Cache health check failed: %s", e)
            result = {
                "redis_connected": False,
                "index_exists": False,
                "error": str(e),
                "index_name": self.index_name,
                "fault_tolerant": self._fault_tolerant
            }

            if self._fault_tolerant:
                self.logger.warning("Cache health check failed, continuing in fault-tolerant mode")
                return result
            else:
                raise

    def is_available(self) -> bool:
        """
        Check if cache is available and working.

        Returns:
            bool: True if cache is working, False otherwise
        """
        try:
            health = self.health_check()
            return health.get("redis_connected", False) and health.get("index_exists", False)
        except Exception as e:
            self.logger.error("Cache availability check failed: %s", e)
            return False
