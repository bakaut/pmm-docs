"""
Yandex Database (YDB) Cache Manager Module

A comprehensive caching system using Yandex Database (YDB) Serverless for vector similarity search.
Provides TTL-based caching, embedding storage, and KNN search capabilities.

Architecture:
- YDB serverless database with document API support
- TTL-based cache expiration via built-in YDB TTL
- Support for tenant-based multi-tenancy
- Automatic schema creation and management
- Vector embedding storage and similarity search

Key Features:
- Text and embedding caching with configurable TTL
- KNN search using cosine similarity
- Tenant and user-based filtering
- Automatic cache expiration via YDB TTL
- Batch operations support
- Error handling and logging
- Full compatibility with Redis cache manager interface

Installation Requirements:
- ydb SDK for Python
- Install: pip install ydb
"""

import time
import json
import hashlib
import logging
import struct
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
import ydb
import ydb_dbapi

from .config import Config
from .utils import Utils


@dataclass
class YDBCacheSettings:
    """YDB cache configuration settings"""
    endpoint: str = "localhost:2136"
    database: str = "/local"
    table_name: str = "cache_entries"
    username: Optional[str] = None
    password: Optional[str] = None
    secure: bool = False
    use_iam: bool = True
    service_account_key: Optional[str] = None
    embedding_dim: int = 1536
    default_ttl: int = 86400
    enable_embeddings: bool = True
    fault_tolerant: bool = True
    index_enabled: bool = False
    index_name: str = "embedding_vector_idx"
    index_config_levels: int = 2
    index_config_clusters: int = 128
    vector_pass_as_bytes: bool = True


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata"""
    text: str
    tenant: str
    user: str
    created_at: int
    embedding: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YDB storage"""
        data = {
            "text": self.text,
            "tenant": self.tenant,
            "user": self.user,
            "created_at": self.created_at
        }
        if self.embedding is not None:
            # embedding is already in YDB binary format (hex string)
            data["embedding"] = self.embedding if isinstance(self.embedding, str) else self.embedding.hex()
        return data


@dataclass
class SearchResult:
    """Represents a search result with similarity score"""
    id: str
    text: str
    user: str
    score: float


class CacheYDBManager:
    """
    YDB-based cache manager with vector search capabilities.

    Provides caching for text content with automatically generated embeddings and supports
    KNN search for similarity matching using YDB document storage.
    """

    def __init__(self, config: Config, llm_manager=None, logger: Optional[logging.Logger] = None):
        """
        Initialize CacheYDBManager with configuration.

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

        # Create YDB cache settings from config
        self.ydb_settings = YDBCacheSettings(
            endpoint=getattr(config, 'cache_ydb_endpoint', 'localhost:2136'),
            database=getattr(config, 'cache_ydb_database', '/local'),
            table_name=getattr(config, 'cache_ydb_table', 'cache_entries'),
            username=getattr(config, 'cache_ydb_username', None),
            password=getattr(config, 'cache_ydb_password', None),
            secure=getattr(config, 'cache_ydb_secure', False),
            use_iam=getattr(config, 'cache_ydb_use_iam', True),
            service_account_key=getattr(config, 'cache_ydb_service_account_key', None),
            embedding_dim=getattr(config, 'cache_embedding_dimensions', 1536),
            default_ttl=getattr(config, 'cache_default_ttl', 86400),
            enable_embeddings=getattr(config, 'cache_enable_embeddings', True),
            fault_tolerant=getattr(config, 'cache_fault_tolerant', True),
            index_enabled=getattr(config, 'cache_enable_embeddings', True),
            vector_pass_as_bytes=True
        )

        # Legacy property aliases for compatibility
        self.table_name = self.ydb_settings.table_name
        self.embedding_dim = self.ydb_settings.embedding_dim
        self.default_ttl = self.ydb_settings.default_ttl
        self._fault_tolerant = self.ydb_settings.fault_tolerant

        # YDB connection using ydb_dbapi (langchain-ydb pattern)
        self.connection: Optional[ydb_dbapi.Connection] = None

        # Initialize on first use
        self._initialized = False
        self._vector_index_available = None  # None=unknown, True=available, False=unavailable

    def _get_connection(self) -> ydb_dbapi.Connection:
        """Get YDB connection using ydb_dbapi (langchain-ydb pattern)"""
        if self.connection is None:
            try:
                if not self.ydb_settings.endpoint or not self.ydb_settings.database:
                    raise ValueError("YDB endpoint and database must be configured")

                # Parse endpoint to extract host and port
                if '://' in self.ydb_settings.endpoint:
                    # Remove protocol if present
                    endpoint = self.ydb_settings.endpoint.split('://')[-1]
                else:
                    endpoint = self.ydb_settings.endpoint
                
                if ':' in endpoint:
                    host, port = endpoint.rsplit(':', 1)
                    port = int(port)
                else:
                    host = endpoint
                    port = 2136  # Default YDB port

                # Create connection using ydb_dbapi (langchain-ydb pattern)
                self.connection = ydb_dbapi.connect(
                    host=host,
                    port=port,
                    database=self.ydb_settings.database,
                    username=self.ydb_settings.username,
                    password=self.ydb_settings.password,
                    protocol="grpcs" if self.ydb_settings.secure else "grpc"
                )
                
                self.logger.debug("Successfully connected to YDB using ydb_dbapi")
            except Exception as e:
                self.logger.error("Failed to connect to YDB: %s", e)
                raise

        return self.connection

    def _execute_query(self, query: str, params: Optional[Dict] = None, ddl: bool = False) -> List[Dict]:
        """Execute query using ydb_dbapi cursor (langchain-ydb pattern)"""
        connection = self._get_connection()
        with connection.cursor() as cursor:
            if ddl:
                cursor.execute_scheme(query, params)
                return []
            else:
                cursor.execute(query, params)
                
                if cursor.description is None:
                    return []
                
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _vector_index_exists(self) -> bool:
        """Check if vector index exists using ydb_dbapi pattern"""
        try:
            # Use DESCRIBE TABLE to check if index exists
            connection = self._get_connection()
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f"DESCRIBE TABLE `{self.table_name}`")
                    # If we can describe the table, check for indexes
                    # Note: This is a simplified check - in practice you might need 
                    # to parse the description or use YDB-specific queries
                    return True  # Assume index exists if table exists
                except Exception:
                    return False
        except Exception as e:
            self.logger.debug("Failed to check vector index existence: %s", e)
            return False

    def _table_exists(self) -> bool:
        """Check if cache table exists using ydb_dbapi pattern"""
        try:
            connection = self._get_connection()
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f"DESCRIBE TABLE `{self.table_name}`")
                    return True
                except Exception:
                    return False
        except Exception as e:
            self.logger.debug("Table existence check failed: %s", e)
            return False

    def _create_vector_index(self) -> bool:
        """Create vector index using ydb_dbapi pattern from langchain-ydb"""
        if not self.ydb_settings.enable_embeddings:
            self.logger.debug("Embeddings disabled, skipping vector index creation")
            return True
            
        try:
            # Use langchain-ydb pattern for index creation
            create_index_query = f"""
                ALTER TABLE `{self.table_name}`
                ADD INDEX {self.ydb_settings.index_name}
                GLOBAL USING vector_kmeans_tree
                ON (embedding)
                WITH (
                    similarity=cosine,
                    vector_type="Float",
                    vector_dimension={self.embedding_dim},
                    levels={self.ydb_settings.index_config_levels},
                    clusters={self.ydb_settings.index_config_clusters}
                )
            """

            # Retry with immediate attempts for schema operation limits
            for attempt in range(3):
                try:
                    self._execute_query(create_index_query, ddl=True)
                    self.logger.info("Created vector index for table %s", self.table_name)
                    return True
                except Exception as e:
                    if "schema operations" in str(e).lower() and attempt < 2:
                        self.logger.warning("Index creation limit hit, retrying (attempt %d/3)", attempt + 1)
                        continue
                    else:
                        self.logger.error("Failed to create vector index: %s", e)
                        # Don't fail the entire initialization if vector index creation fails
                        self.logger.warning("Continuing without vector index - vector search will be disabled")
                        return False
            
            return False

        except Exception as e:
            self.logger.error("Failed to create vector index: %s", e)
            # Don't fail the entire initialization if vector index creation fails
            self.logger.warning("Continuing without vector index - vector search will be disabled")
            return False

    def _create_table(self) -> bool:
        """Create cache table using ydb_dbapi pattern from langchain-ydb"""
        try:
            # Create table schema using langchain-ydb pattern
            create_query = f"""
                CREATE TABLE IF NOT EXISTS `{self.table_name}` (
                    id Utf8,
                    tenant Utf8,
                    user_hash Utf8,
                    text Utf8,
                    created_at Uint64,
                    expires_at Datetime,
                    embedding {self._get_vector_type()},
                    PRIMARY KEY (id)
                )
            """

            # Retry with immediate attempts for schema operation limits
            for attempt in range(3):
                try:
                    self._execute_query(create_query, ddl=True)
                    break
                except Exception as e:
                    if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                        self.logger.info("Table %s already exists, continuing", self.table_name)
                        break
                    elif "schema operations" in str(e).lower() and attempt < 2:
                        self.logger.warning("Schema operation limit hit, retrying (attempt %d/3)", attempt + 1)
                        continue
                    else:
                        raise
            
            # Set TTL separately (if needed)
            try:
                ttl_query = f"""
                    ALTER TABLE `{self.table_name}` 
                    SET TTL = Interval("PT{self.default_ttl}S") ON expires_at
                """
                self._execute_query(ttl_query, ddl=True)
            except Exception as e:
                self.logger.warning("Failed to set TTL, table created without TTL: %s", e)
            
            self.logger.info("Created YDB cache table %s with TTL", self.table_name)
            return True

        except Exception as e:
            self.logger.error("Failed to create YDB table: %s", e)
            return False

    def ensure_schema(self) -> bool:
        """Ensure YDB table and vector index exist, create if necessary"""
        try:
            # Step 1: Ensure table exists
            table_created = False
            if not self._table_exists():
                self.logger.info("Creating YDB cache table %s", self.table_name)
                if not self._create_table():
                    self.logger.error("Failed to create table, cache will be disabled")
                    return False
                table_created = True
                # Note: Removed sleep() - YDB handles schema operation sequencing internally
            else:
                self.logger.debug("YDB cache table %s already exists", self.table_name)
            
            # Step 2: Ensure vector index exists (only if embeddings are enabled)
            if self.config.cache_enable_embeddings:
                try:
                    if not self._vector_index_exists():
                        self.logger.info("Creating vector index for table %s", self.table_name)
                        # Don't fail if vector index creation fails - cache can work without it
                        index_created = self._create_vector_index()
                        if index_created:
                            self._vector_index_available = True
                            self.logger.info("Vector index created successfully")
                        else:
                            self.logger.warning("Vector index creation failed - vector search will be limited")
                            self._vector_index_available = False
                    else:
                        self.logger.debug("Vector index for table %s already exists", self.table_name)
                        self._vector_index_available = True
                except Exception as e:
                    self.logger.warning("Vector index check/creation failed: %s", e)
                    self._vector_index_available = False
            else:
                self._vector_index_available = False
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to ensure YDB schema: %s", e)
            # For cache, we want to be fault-tolerant - return False but don't crash
            return False

    def _initialize(self):
        """Initialize the cache system if not already done"""
        if not self._initialized:
            try:
                if self.ensure_schema():
                    self._initialized = True
                    self.logger.info("YDB cache schema initialized successfully")
                else:
                    if self._fault_tolerant:
                        self._initialized = True  # Mark as initialized to prevent retries
                        self.logger.warning("Schema initialization failed, continuing in fault-tolerant mode without cache")
                    else:
                        raise RuntimeError("Failed to initialize YDB cache schema")
            except Exception as e:
                if self._fault_tolerant:
                    self._initialized = True  # Mark as initialized to prevent retries
                    self.logger.warning("Schema initialization exception: %s. Continuing in fault-tolerant mode without cache", e)
                else:
                    self.logger.error("Failed to initialize YDB cache: %s", e)
                    raise RuntimeError(f"Failed to initialize YDB cache schema: {e}") from e

    def _escape_tag_value(self, value: Union[str, int, float, None]) -> str:
        """Escape values for YDB queries"""
        if value is None:
            return ""
        return str(value).replace("'", "''")

    def _hash_user_id(self, user_id: Union[str, int, None]) -> str:
        """Generate SHA1 hash of user ID"""
        if user_id is None:
            return ""
        user_str = str(user_id)
        return hashlib.sha1(user_str.encode("utf-8")).hexdigest()

    def _qhash(self, s: str) -> str:
        """Generate short hash from string for key generation"""
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

    def _convert_vector_to_bytes_if_needed(self, vector: List[float]) -> bytes:
        """Convert vector to bytes using langchain-ydb pattern"""
        if self.ydb_settings.vector_pass_as_bytes:
            # Pack floats and add type byte (1 for Float) - langchain-ydb pattern
            packed_data = struct.pack("f" * len(vector), *vector)
            return packed_data + b'\x01'  # Add type byte for Float
        return vector

    def _get_vector_type(self) -> str:
        """Get YDB vector column type"""
        if self.ydb_settings.vector_pass_as_bytes:
            return "String"
        return "List<Float>"

    def _pack_f32(self, vec: List[float]) -> bytes:
        """Pack float list to YDB binary format using langchain-ydb pattern"""
        if len(vec) != self.embedding_dim:
            raise ValueError(f"Embedding dimension {len(vec)} != {self.embedding_dim}")
        
        return self._convert_vector_to_bytes_if_needed(vec)

    def _unpack_f32(self, data: bytes) -> List[float]:
        """Unpack bytes back to float list using langchain-ydb pattern"""
        try:
            if isinstance(data, str):
                # Convert hex string back to bytes if needed
                data = bytes.fromhex(data)
            
            # Remove type byte (last byte) - langchain-ydb pattern
            if len(data) < 1:
                raise ValueError("Invalid binary data")
            
            vector_data = data[:-1]
            type_byte = data[-1]
            
            if type_byte != 1:  # 1 = Float type
                raise ValueError(f"Expected Float type (1), got {type_byte}")
            
            # Unpack floats
            float_count = len(vector_data) // 4  # 4 bytes per float
            if float_count != self.embedding_dim:
                raise ValueError(f"Expected {self.embedding_dim} floats, got {float_count}")
            
            return list(struct.unpack(f"{float_count}f", vector_data))
        except Exception as e:
            self.logger.error("Failed to unpack vector data: %s", e)
            raise

    def _generate_key(self, tenant: str, key_signature: str) -> str:
        """Generate cache key from tenant and signature"""
        return f"{tenant}:{self._qhash(key_signature)}"

    def put_cache(self,
                  tenant: str,
                  user: str,
                  key_signature: str,
                  text: str,
                  ttl_seconds: Optional[int] = 86400) -> str:
        """Store cache entry with automatically generated embedding"""
        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, skipping cache operation: %s", e)
                return ""  # Return empty key to indicate cache miss
            else:
                raise

        if not isinstance(text, str):
            if isinstance(text, (list, dict)):
                text = json.dumps(text, ensure_ascii=False)
            else:
                text = str(text)

        key = self._generate_key(tenant, key_signature)
        ttl = ttl_seconds or self.default_ttl
        user_hash = self._hash_user_id(user)

        # Calculate expiration time as datetime for YDB TTL
        import datetime
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl)
        
        # Prepare entry data
        entry_data = {
            "id": key,
            "tenant": tenant,
            "user_hash": user_hash,
            "text": text,
            "created_at": int(time.time()),
            "expires_at": expires_at,
            "embedding": None
        }

        # Generate embedding if enabled
        if self.ydb_settings.enable_embeddings and self.llm_manager is not None:
            try:
                embedding = self.llm_manager.embd_text(text)
                if embedding and isinstance(embedding, list):
                    # Store in YDB binary vector format using langchain-ydb pattern
                    entry_data["embedding"] = self._pack_f32(embedding)
                    self.logger.debug("Generated embedding for cache entry (dim: %d)", len(embedding))
                else:
                    self.logger.warning("Failed to generate embedding for text: %s", text[:50])
            except Exception as e:
                self.logger.error("Failed to generate embedding: %s", e)

        try:
            # Use ydb_dbapi cursor for insertion
            query = f"""
                UPSERT INTO `{self.table_name}` (id, tenant, user_hash, text, created_at, expires_at, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            params = [
                key,
                tenant,
                user_hash,
                text,
                entry_data["created_at"],
                expires_at,
                entry_data["embedding"]
            ]
            
            self._execute_query(query, params)

            self.logger.debug("Cached entry for key %s (tenant: %s, user: %s, ttl: %ds)",
                            key, tenant, user, ttl)
            return key

        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Failed to cache entry (fault-tolerant mode): %s", e)
                return ""  # Return empty key to indicate cache miss
            else:
                self.logger.error("Failed to cache entry: %s", e)
                raise

    def get_cache(self, key: str, extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cache entry by key using ydb_dbapi pattern"""
        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, returning cache miss: %s", e)
                return None  # Return None to indicate cache miss
            else:
                raise

        try:
            # Use ydb_dbapi cursor for SELECT
            query = f"SELECT * FROM `{self.table_name}` WHERE id = ?"
            
            results = self._execute_query(query, [key])
            
            if not results:
                return None

            row = results[0]
            result = {
                "text": row["text"],
                "tenant": row["tenant"],
                "user": row["user_hash"],
                "created_at": int(row["created_at"])
            }

            if row.get("embedding"):
                try:
                    # Store the binary data directly - it will be converted when needed for similarity
                    result["embedding"] = row["embedding"]
                except Exception as e:
                    self.logger.warning("Failed to process embedding: %s", e)

            # Handle TTL extension if requested
            if extend_ttl_seconds:
                import datetime
                new_expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=extend_ttl_seconds)
                
                update_query = f"UPDATE `{self.table_name}` SET expires_at = ? WHERE id = ?"
                
                try:
                    self._execute_query(update_query, [new_expires_at, key])
                except Exception as e:
                    self.logger.warning("Failed to extend TTL: %s", e)

            return result

        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Failed to retrieve cache entry (fault-tolerant mode): %s", e)
                return None  # Return None to indicate cache miss
            else:
                self.logger.error("Failed to retrieve cache entry: %s", e)
                return None

    def get_cache_by_signature(self, tenant: str, key_signature: str, 
                             extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cache entry by tenant and signature"""
        key = self._generate_key(tenant, key_signature)
        return self.get_cache(key, extend_ttl_seconds)

    def delete_cache(self, key: str) -> bool:
        """Delete cache entry by key using ydb_dbapi pattern"""
        try:
            query = f"DELETE FROM `{self.table_name}` WHERE id = ?"
            self._execute_query(query, [key])
            
            self.logger.debug("Deleted cache entry %s", key)
            return True

        except Exception as e:
            self.logger.error("Failed to delete cache entry: %s", e)
            return False

    def knn_search(self, tenant: str, query_vector: List[float], k: int = 10,
                   user: Optional[str] = None, additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """Perform KNN similarity search using YDB's native vector capabilities with fallback"""
        if not self.ydb_settings.enable_embeddings:
            raise ValueError("Embeddings are not enabled in cache configuration")

        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, returning empty search results: %s", e)
                return {"total": 0, "hits": []}
            else:
                raise

        try:
            # Convert query vector to YDB binary format using langchain-ydb pattern
            query_vector_binary = self._pack_f32(query_vector)
            
            # Check if vector index is available, try using it first
            if self._vector_index_available is True:
                try:
                    return self._knn_search_with_index(tenant, query_vector_binary, k, user)
                except Exception as index_error:
                    self.logger.warning("Vector index search failed: %s", index_error)
                    self._vector_index_available = False  # Mark as unavailable for future queries
                    self.logger.info("Falling back to full table scan for vector search")
                    return self._knn_search_fallback(tenant, query_vector, k, user)
            elif self._vector_index_available is False:
                # We know index is not available, skip to fallback
                self.logger.debug("Using fallback vector search (index unavailable)")
                return self._knn_search_fallback(tenant, query_vector, k, user)
            else:
                # Unknown state, try index first and update availability
                try:
                    result = self._knn_search_with_index(tenant, query_vector_binary, k, user)
                    self._vector_index_available = True  # Mark as available
                    return result
                except Exception as index_error:
                    self.logger.warning("Vector index search failed: %s", index_error)
                    self._vector_index_available = False  # Mark as unavailable
                    self.logger.info("Falling back to full table scan for vector search")
                    return self._knn_search_fallback(tenant, query_vector, k, user)

        except Exception as e:
            self.logger.error("KNN search failed: %s", e)
            self.logger.error("Vector search details - tenant: %s, user: %s, k: %d", tenant, user, k)
            return {"total": 0, "hits": []}
    
    def _knn_search_with_index(self, tenant: str, query_vector_binary: bytes, k: int, user: Optional[str] = None) -> Dict[str, Any]:
        """Perform KNN search using vector index with ydb_dbapi pattern"""
        # Build the query with optional user filter
        where_conditions = ["tenant = ?"]
        params = [tenant]
        
        if user:
            user_hash = self._hash_user_id(user)
            where_conditions.append("user_hash = ?")
            params.append(user_hash)
        
        where_clause = " AND ".join(where_conditions)
        
        # Use YDB's vector index with VIEW syntax for efficient search
        search_query = f"""
            SELECT id, text, user_hash, 
                   Knn::CosineSimilarity(embedding, ?) AS similarity_score
            FROM `{self.table_name}` VIEW {self.ydb_settings.index_name}
            WHERE {where_clause}
            ORDER BY Knn::CosineSimilarity(embedding, ?) DESC
            LIMIT ?
        """
        
        # Add query vector to params twice (for similarity calculation and ordering)
        all_params = [query_vector_binary] + params + [query_vector_binary, k]
        
        self.logger.debug("Executing YDB vector search query")
        
        results = self._execute_query(search_query, all_params)
        
        # Convert results to expected format
        hits = []
        for row in results:
            hits.append({
                "id": row["id"],
                "text": row["text"],
                "user": row["user_hash"],
                "score": float(row["similarity_score"])
            })

        self.logger.debug("YDB vector index search returned %d results", len(hits))
        return {"total": len(hits), "hits": hits}
    
    def _knn_search_fallback(self, tenant: str, query_vector: List[float], k: int, user: Optional[str] = None) -> Dict[str, Any]:
        """Fallback KNN search without vector index using ydb_dbapi pattern"""
        # Build query
        where_clause = "WHERE tenant = ? AND embedding IS NOT NULL"
        params = [tenant]
        
        if user:
            user_hash = self._hash_user_id(user)
            where_clause += " AND user_hash = ?"
            params.append(user_hash)
        
        query = f"SELECT id, text, user_hash, embedding FROM `{self.table_name}` {where_clause}"

        results = self._execute_query(query, params)
        
        # Compute similarities manually
        similarities = []
        
        for row in results:
            try:
                # Unpack stored vector from binary format
                stored_vector = self._unpack_f32(row["embedding"])
                
                # Compute cosine similarity
                import math
                dot_product = sum(a * b for a, b in zip(query_vector, stored_vector))
                magnitude_a = math.sqrt(sum(a * a for a in query_vector))
                magnitude_b = math.sqrt(sum(b * b for b in stored_vector))
                
                if magnitude_a == 0 or magnitude_b == 0:
                    similarity = 0
                else:
                    similarity = dot_product / (magnitude_a * magnitude_b)
                
                similarities.append({
                    "id": row["id"],
                    "text": row["text"],
                    "user": row["user_hash"],
                    "score": similarity
                })
            except Exception as e:
                self.logger.warning("Failed to compute similarity for entry %s: %s", row["id"], e)

        # Sort by similarity and take top k
        similarities.sort(key=lambda x: x["score"], reverse=True)
        hits = similarities[:k]

        self.logger.debug("YDB fallback vector search returned %d results", len(hits))
        return {"total": len(hits), "hits": hits}

    def semantic_search(self, tenant: str, query_text: str, k: int = 10,
                       user: Optional[str] = None, additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """Perform semantic similarity search using text query"""
        if not self.ydb_settings.enable_embeddings:
            raise ValueError("Embeddings are not enabled in cache configuration")

        if not self.llm_manager:
            raise ValueError("LLM manager is required for semantic search")

        try:
            query_embedding = self.llm_manager.embd_text(query_text)
            if not query_embedding or not isinstance(query_embedding, list):
                return {"total": 0, "hits": []}

            return self.knn_search(tenant, query_embedding, k, user, additional_filters)

        except Exception as e:
            self.logger.error("Semantic search failed: %s", e)
            return {"total": 0, "hits": []}

    def text_search(self, tenant: str, query: str, user: Optional[str] = None,
                    limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Perform full-text search on cached content using ydb_dbapi pattern"""
        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, returning empty search results: %s", e)
                return {"total": 0, "hits": []}
            else:
                raise

        try:
            limit = max(1, min(int(limit), 1000))
            offset = max(0, int(offset))

            # Build query
            where_clause = "WHERE tenant = ? AND text LIKE ?"
            params = [tenant, f"%{query}%"]
            
            if user:
                user_hash = self._hash_user_id(user)
                where_clause += " AND user_hash = ?"
                params.append(user_hash)

            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM `{self.table_name}` {where_clause}"
            count_results = self._execute_query(count_query, params)
            total = count_results[0]["total"] if count_results else 0

            # Get paginated results
            result_query = f"""
                SELECT id, text, user_hash, created_at 
                FROM `{self.table_name}` {where_clause} 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """
            
            result_params = params + [limit, offset]
            results = self._execute_query(result_query, result_params)
            
            hits = []
            for row in results:
                hits.append({
                    "id": row["id"],
                    "text": row["text"],
                    "user": row["user_hash"],
                    "created_at": int(row["created_at"])
                })

            return {"total": total, "hits": hits}

        except Exception as e:
            self.logger.error("Text search failed: %s", e)
            if self._fault_tolerant:
                return {"total": 0, "hits": []}
            raise

    def clear_tenant_cache(self, tenant: str) -> int:
        """Clear all cache entries for a specific tenant using ydb_dbapi pattern"""
        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, skipping clear operation: %s", e)
                return 0
            else:
                raise

        try:
            # Get count first
            count_query = f"SELECT COUNT(*) as total FROM `{self.table_name}` WHERE tenant = ?"
            count_results = self._execute_query(count_query, [tenant])
            total = count_results[0]["total"] if count_results else 0

            # Delete entries
            delete_query = f"DELETE FROM `{self.table_name}` WHERE tenant = ?"
            self._execute_query(delete_query, [tenant])
            
            if total > 0:
                self.logger.info("Cleared %d cache entries for tenant %s", total, tenant)
            return total

        except Exception as e:
            self.logger.error("Failed to clear tenant cache: %s", e)
            if self._fault_tolerant:
                return 0
            raise

    def get_cache_stats(self, tenant: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics using ydb_dbapi pattern"""
        try:
            self._initialize()
        except Exception as e:
            if self._fault_tolerant:
                self.logger.warning("Cache initialization failed, returning default stats: %s", e)
                return {"total_documents": 0, "index_size": 0}
            else:
                raise

        try:
            if tenant:
                query = f"SELECT COUNT(*) as total FROM `{self.table_name}` WHERE tenant = ?"
                results = self._execute_query(query, [tenant])
            else:
                query = f"SELECT COUNT(*) as total FROM `{self.table_name}`"
                results = self._execute_query(query)
            
            total_docs = 0
            if results:
                total_docs = results[0]["total"]
            
            stats = {
                "total_documents": total_docs,
                "index_size": 0  # YDB doesn't expose index size directly
            }
            
            if tenant:
                stats["tenant_documents"] = total_docs

            return stats

        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            if self._fault_tolerant:
                return {"total_documents": 0, "index_size": 0}
            raise

    def get_user_hash(self, user_id: Union[str, int, None]) -> str:
        """Get SHA1 hash of user ID for external use"""
        return self._hash_user_id(user_id)

    def health_check(self) -> Dict[str, Any]:
        """Perform cache health check using ydb_dbapi pattern"""
        try:
            # Test YDB connection with a simple SELECT query
            self._execute_query("SELECT 1 as test")

            # Check if our table exists (optional)
            table_exists = self._table_exists()

            return {
                "ydb_connected": True,
                "table_exists": table_exists,
                "table_name": self.table_name,
                "fault_tolerant": self._fault_tolerant,
                "vector_index_available": self._vector_index_available
            }

        except Exception as e:
            self.logger.error("Cache health check failed: %s", e)
            result = {
                "ydb_connected": False,
                "table_exists": False,
                "error": str(e),
                "table_name": self.table_name,
                "fault_tolerant": self._fault_tolerant,
                "vector_index_available": self._vector_index_available
            }

            if self._fault_tolerant:
                return result
            else:
                raise

    def is_available(self) -> bool:
        """Check if cache is available and working"""
        try:
            health = self.health_check()
            return health.get("ydb_connected", False) and health.get("table_exists", False)
        except Exception:
            return False

    def __del__(self):
        """Cleanup YDB connection on object destruction"""
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass