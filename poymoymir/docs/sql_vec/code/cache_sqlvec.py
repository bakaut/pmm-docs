"""
SQLite-Vec Cache Manager Module

A comprehensive caching system using SQLite with sqlite-vec extension for vector similarity search.
Provides TTL-based caching, embedding storage, and KNN search capabilities.

Architecture:
- SQLite database with sqlite-vec extension for vector operations
- TTL-based cache expiration via automated cleanup
- Support for tenant-based multi-tenancy
- Automatic schema creation and management
- Vector embedding storage and similarity search

Key Features:
- Text and embedding caching with configurable TTL
- KNN search using cosine similarity
- Tenant and user-based filtering
- Automatic cache expiration
- Batch operations support
- Error handling and logging
- Full compatibility with Redis cache manager interface

Installation Requirements:
- sqlite-vec extension for SQLite
- Install: pip install sqlite-vec

Usage:
    from cache_sqlvec import CacheSQLVecManager
    cache = CacheSQLVecManager(config, llm_manager, logger)
"""

import time
import json
import hashlib
import logging
try:
    import apsw
    # APSW provides better extension support and performance
    SQLITE_MODULE = 'apsw'
except ImportError:
    import sqlite3 as apsw
    # Fallback to built-in sqlite3 if APSW not available
    SQLITE_MODULE = 'sqlite3'
import threading
import os
from array import array
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path

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
        """Convert to dictionary for storage"""
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


class CacheSQLVecManager:
    """
    SQLite-based cache manager with vector search capabilities using sqlite-vec.

    Provides caching for text content with automatically generated embeddings and supports
    KNN search for similarity matching using sqlite-vec extension.
    """

    def __init__(self, config: Config, llm_manager=None, logger: Optional[logging.Logger] = None):
        """Initialize CacheSQLVecManager with configuration."""
        self.config = config
        self.llm_manager = llm_manager
        self.logger = logger or logging.getLogger(__name__)

        # Initialize Utils for base64 operations
        self.utils = Utils(config, self.logger)

        # Cache configuration
        self.db_path = getattr(config, 'cache_sqlite_path', '/function/storage/songs/sqlvec.db')

        # Ensure database directory exists
        db_dir = Path(self.db_path).parent
        if db_dir != Path('.'):
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                self.logger.debug("Created database directory: %s", db_dir)
            except Exception as e:
                self.logger.warning("Could not create database directory %s: %s", db_dir, e)
                # Fall back to current directory
                self.db_path = Path(self.db_path).name
                self.logger.info("Using database file in current directory: %s", self.db_path)
        self.index_name = self.config.cache_index_name
        self.key_prefix = self.config.cache_key_prefix
        self.embedding_dim = self.config.cache_embedding_dimensions
        self.default_ttl = self.config.cache_default_ttl

        # Connection pooling and thread safety
        self._local = threading.local()
        self._db_lock = threading.Lock()

        # Initialize on first use
        self._initialized = False

        # Fault tolerance configuration
        self._fault_tolerant = self.config.cache_fault_tolerant

        # Runtime flag for embedding availability (set during connection)
        self._embeddings_disabled = False

        # Auto-disable embeddings in cloud function environments
        if '/function/' in str(self.db_path) or os.getenv('FUNCTION_NAME') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
            self.logger.info("Detected cloud function environment, embeddings will be disabled if sqlite-vec unavailable")
            self._cloud_environment = True
        else:
            self._cloud_environment = False

    def _get_connection(self) -> apsw.Connection:
        """Get thread-local database connection using APSW or sqlite3 fallback"""
        if not hasattr(self._local, 'connection'):
            try:
                # Ensure the database directory exists and is writable
                db_path = Path(self.db_path)
                db_dir = db_path.parent

                # Check directory permissions
                if not db_dir.exists():
                    db_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.debug("Created database directory: %s", db_dir)

                if not db_dir.is_dir():
                    raise RuntimeError(f"Database directory path exists but is not a directory: {db_dir}")

                # Check write permissions
                if not os.access(db_dir, os.W_OK):
                    raise RuntimeError(f"No write permission for database directory: {db_dir}")

                self.logger.debug("Creating %s connection to: %s", SQLITE_MODULE, self.db_path)

                if SQLITE_MODULE == 'apsw':
                    # Use APSW for better extension support
                    conn = apsw.Connection(str(self.db_path))
                    # APSW doesn't need check_same_thread - it's inherently thread-safe

                    # Set up row factory equivalent for APSW
                    def row_factory(cursor, row):
                        """Convert APSW row to dict-like object"""
                        try:
                            description = cursor.getdescription()
                            if description:
                                row_dict = {description[i][0]: row[i] for i in range(len(row))}

                                # Create a dict-like object that supports both dict and attribute access
                                class RowDict(dict):
                                    def __getitem__(self, key):
                                        if isinstance(key, int):
                                            # Support numeric indexing
                                            return list(self.values())[key]
                                        return super().__getitem__(key)

                                return RowDict(row_dict)
                            else:
                                # Return raw row if no description available
                                return row
                        except Exception:
                            # Fallback to raw row
                            return row

                    conn.setrowtrace(row_factory)

                else:
                    # Fallback to built-in sqlite3
                    conn = apsw.connect(self.db_path, check_same_thread=False)
                    conn.row_factory = apsw.Row

                # Test basic connectivity
                if SQLITE_MODULE == 'apsw':
                    # APSW: simple execute and consume
                    cursor = conn.execute("SELECT 1")
                    list(cursor)  # Consume all results
                else:
                    # sqlite3: execute and fetch
                    cursor = conn.execute("SELECT 1")
                    cursor.fetchone()

                # Enable sqlite-vec extension
                sqlite_vec_available = False
                try:
                    if SQLITE_MODULE == 'apsw':
                        # APSW has better extension support
                        conn.enableloadextension(True)
                        # Try different extension names
                        vec_extensions = ['vec0', 'sqlite_vec']
                        for ext_name in vec_extensions:
                            try:
                                conn.loadextension(ext_name)
                                sqlite_vec_available = True
                                self.logger.debug("Successfully loaded %s extension via APSW", ext_name)
                                break
                            except Exception as ext_err:
                                self.logger.debug("Failed to load %s: %s", ext_name, ext_err)

                        # Try sqlite-vec Python module path
                        if not sqlite_vec_available:
                            try:
                                import sqlite_vec
                                conn.loadextension(sqlite_vec.loadable_path())
                                sqlite_vec_available = True
                                self.logger.debug("Successfully loaded sqlite-vec via Python module path")
                            except Exception as py_err:
                                self.logger.debug("Failed to load via Python module: %s", py_err)
                    else:
                        # Fallback to sqlite3 method
                        if hasattr(conn, 'enable_load_extension'):
                            conn.enable_load_extension(True)
                            # Try sqlite-vec Python module first
                            try:
                                import sqlite_vec
                                conn.load_extension(sqlite_vec.loadable_path())
                                sqlite_vec_available = True
                                self.logger.debug("Successfully loaded sqlite-vec extension via sqlite3")
                            except Exception:
                                # Fallback to direct extension name
                                conn.load_extension("vec0")
                                sqlite_vec_available = True
                                self.logger.debug("Successfully loaded vec0 extension via sqlite3")
                        else:
                            self.logger.warning("SQLite connection does not support loading extensions")
                except Exception as e:
                    self.logger.warning("Failed to load sqlite-vec extension: %s", e)

                # Handle embedding requirements based on availability
                if self.config.cache_enable_embeddings and not sqlite_vec_available:
                    if self._cloud_environment:
                        # In cloud environments, automatically disable embeddings
                        self.logger.info("Cloud environment detected: automatically disabling embeddings")
                        self._embeddings_disabled = True
                    else:
                        # In local environments, log a warning but continue
                        self.logger.warning("Embeddings are enabled but sqlite-vec is not available")
                        self.logger.info("Install sqlite-vec with: pip install sqlite-vec")
                        self.logger.info("For better extension support, install APSW: pip install apsw")
                        self._embeddings_disabled = True
                else:
                    self._embeddings_disabled = not sqlite_vec_available

                # Set SQLite optimizations
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")

                self._local.connection = conn
                self.logger.debug("%s connection established successfully", SQLITE_MODULE)

            except Exception as e:
                error_msg = f"Failed to connect to SQLite database '{self.db_path}': {e}"
                self.logger.error(error_msg)
                self.logger.error("Database path: %s", os.path.abspath(self.db_path))
                self.logger.error("Current working directory: %s", os.getcwd())
                self.logger.error("Directory exists: %s", db_dir.exists() if 'db_dir' in locals() else 'unknown')
                self.logger.error("Directory writable: %s", os.access(db_dir, os.W_OK) if 'db_dir' in locals() and db_dir.exists() else 'unknown')
                raise RuntimeError(error_msg) from e

        return self._local.connection

    def _execute(self, query: str, params: tuple = ()):
        """Execute SQL query with error handling for both APSW and sqlite3"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(query, params)

            if SQLITE_MODULE == 'apsw':
                # APSW returns an iterator, create a wrapper for compatibility
                class APSWCursorWrapper:
                    def __init__(self, apsw_cursor, connection):
                        self._cursor = apsw_cursor
                        self._connection = connection
                        self._results = None
                        self._description = None
                        self._consumed = False

                    def _ensure_results(self):
                        if not self._consumed:
                            try:
                                self._results = list(self._cursor)
                                # Get description after consuming
                                try:
                                    self._description = self._cursor.getdescription()
                                except Exception:
                                    self._description = None
                                self._consumed = True
                            except Exception as e:
                                self._results = []
                                self._description = None
                                self._consumed = True

                    def fetchone(self):
                        self._ensure_results()
                        return self._results[0] if self._results else None

                    def fetchall(self):
                        self._ensure_results()
                        return self._results or []

                    @property
                    def rowcount(self):
                        # For APSW, get changes from connection for DML operations
                        try:
                            return self._connection.changes()
                        except Exception:
                            self._ensure_results()
                            return len(self._results) if self._results else -1

                    def __iter__(self):
                        self._ensure_results()
                        return iter(self._results or [])

                return APSWCursorWrapper(cursor, conn)
            else:
                # Standard sqlite3 cursor
                return cursor

        except Exception as e:
            self.logger.error("SQL execution error: %s", e)
            self.logger.error("Query: %s", query)
            self.logger.error("Params: %s", params)
            raise

    def _commit(self):
        """Commit current transaction"""
        if SQLITE_MODULE == 'apsw':
            # APSW uses autocommit mode by default, no explicit commit needed
            pass
        else:
            conn = self._get_connection()
            conn.commit()

    def ensure_schema(self) -> bool:
        """Ensure database schema exists, create if necessary."""
        try:
            with self._db_lock:
                # Create main cache table
                self._execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        id TEXT PRIMARY KEY,
                        tenant TEXT NOT NULL,
                        user_hash TEXT NOT NULL,
                        text TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        embedding BLOB
                    )
                """)

                # Create indexes for performance
                self._execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_tenant
                    ON cache_entries(tenant)
                """)

                self._execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_expires
                    ON cache_entries(expires_at)
                """)

                # Create FTS table for full-text search
                self._execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS cache_fts
                    USING fts5(id, text, tenant, user_hash)
                """)

                # Create triggers to keep FTS in sync
                self._execute("""
                    CREATE TRIGGER IF NOT EXISTS cache_fts_insert AFTER INSERT ON cache_entries
                    BEGIN
                        INSERT INTO cache_fts(id, text, tenant, user_hash)
                        VALUES (NEW.id, NEW.text, NEW.tenant, NEW.user_hash);
                    END
                """)

                self._execute("""
                    CREATE TRIGGER IF NOT EXISTS cache_fts_delete AFTER DELETE ON cache_entries
                    BEGIN
                        DELETE FROM cache_fts WHERE id = OLD.id;
                    END
                """)

                self._execute("""
                    CREATE TRIGGER IF NOT EXISTS cache_fts_update AFTER UPDATE ON cache_entries
                    BEGIN
                        UPDATE cache_fts SET text = NEW.text, tenant = NEW.tenant,
                               user_hash = NEW.user_hash WHERE id = NEW.id;
                    END
                """)

                # Create vector table if embeddings are enabled and available
                if self.config.cache_enable_embeddings and not getattr(self, '_embeddings_disabled', False):
                    try:
                        self._execute(f"""
                            CREATE VIRTUAL TABLE IF NOT EXISTS cache_vectors
                            USING vec0(id TEXT PRIMARY KEY, embedding float[{self.embedding_dim}])
                        """)
                        self.logger.debug("Created vector table with sqlite-vec")
                    except Exception as e:
                        self.logger.error("Failed to create vector table: %s", e)
                        self.logger.warning("Vector similarity search will not be available")
                        # Mark embeddings as disabled for this session
                        self._embeddings_disabled = True

                self._commit()
                self.logger.info("Cache schema initialized successfully")
                return True

        except Exception as e:
            self.logger.error("Failed to create cache schema: %s", e)
            return False

    def _initialize(self):
        """Initialize the cache system if not already done"""
        if not self._initialized:
            if self.ensure_schema():
                self._initialized = True
                # Start cleanup thread
                self._start_cleanup_thread()
            else:
                raise RuntimeError("Failed to initialize cache schema")

    def _start_cleanup_thread(self):
        """Start background thread for TTL cleanup"""
        def cleanup_expired():
            while True:
                try:
                    current_time = int(time.time())

                    # Delete expired entries
                    cursor = self._execute(
                        "DELETE FROM cache_entries WHERE expires_at < ?",
                        (current_time,)
                    )
                    deleted_count = cursor.rowcount
                    self._commit()

                    if deleted_count > 0:
                        self.logger.debug("Cleaned up %d expired cache entries", deleted_count)

                    # Sleep for 5 minutes before next cleanup
                    time.sleep(300)

                except Exception as e:
                    self.logger.error("Cache cleanup error: %s", e)
                    time.sleep(60)  # Shorter sleep on error

        cleanup_thread = threading.Thread(target=cleanup_expired, daemon=True)
        cleanup_thread.start()
        self.logger.debug("Started cache cleanup thread")

    def _hash_user_id(self, user_id: Union[str, int, None]) -> str:
        """Generate SHA1 hash of user ID to avoid issues with special characters."""
        if user_id is None:
            return ""

        user_str = str(user_id)
        return hashlib.sha1(user_str.encode("utf-8")).hexdigest()

    def _qhash(self, s: str) -> str:
        """Generate short hash from string for key generation"""
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

    def _pack_f32(self, vec: Union[List[float], 'numpy.ndarray']) -> bytes:
        """Pack float list or numpy array to bytes for storage"""
        # Handle numpy arrays by converting to list
        if hasattr(vec, 'tolist'):
            # It's a numpy array, convert to Python list
            vec = vec.tolist()
        elif not isinstance(vec, list):
            # Try to convert other array-like objects to list
            try:
                vec = list(vec)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Cannot convert vector to list: {e}")

        if len(vec) != self.embedding_dim:
            raise ValueError(f"Embedding dimension {len(vec)} != {self.embedding_dim}")
        return array('f', vec).tobytes()

    def _generate_key(self, tenant: str, key_signature: str) -> str:
        """Generate cache key from tenant and signature"""
        return f"{self.key_prefix}{tenant}:{self._qhash(key_signature)}"

    def put_cache(self,
                  tenant: str,
                  user: str,
                  key_signature: str,
                  text: str,
                  ttl_seconds: Optional[int] = 86400) -> str:
        """Store cache entry with automatically generated embedding."""
        self._initialize()

        # Ensure text is a string
        if not isinstance(text, str):
            if isinstance(text, (list, dict)):
                text = json.dumps(text, ensure_ascii=False)
            else:
                text = str(text)

        key = self._generate_key(tenant, key_signature)
        ttl = ttl_seconds or self.default_ttl
        current_time = int(time.time())
        expires_at = current_time + ttl
        user_hash = self._hash_user_id(user)

        try:
            # Store main entry
            self._execute("""
                INSERT OR REPLACE INTO cache_entries
                (id, tenant, user_hash, text, created_at, expires_at, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (key, tenant, user_hash, text, current_time, expires_at, None))

            # Generate and store embedding if enabled and available
            if (self.config.cache_enable_embeddings and
                not getattr(self, '_embeddings_disabled', False) and
                self.llm_manager is not None):
                try:
                    embedding = self.llm_manager.embd_text(text)
                    # Check if embedding is valid (list, numpy array, or other array-like)
                    if embedding and (isinstance(embedding, list) or hasattr(embedding, 'tolist') or hasattr(embedding, '__iter__')):
                        embedding_bytes = self._pack_f32(embedding)
                        self._execute("""
                            UPDATE cache_entries SET embedding = ? WHERE id = ?
                        """, (embedding_bytes, key))

                        # Store in vector table
                        self._execute("""
                            INSERT OR REPLACE INTO cache_vectors (id, embedding)
                            VALUES (?, ?)
                        """, (key, embedding_bytes))

                        # Get dimension for logging (handle numpy arrays)
                        dim = len(embedding) if hasattr(embedding, '__len__') else len(list(embedding))
                        self.logger.debug("Generated embedding (dim: %d)", dim)
                except Exception as e:
                    self.logger.error("Failed to generate embedding: %s", e)

            self._commit()
            self.logger.debug("Cached entry for key %s", key)
            return key

        except Exception as e:
            self.logger.error("Failed to cache entry: %s", e)
            raise

    def get_cache(self,
                  key: str,
                  extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cache entry by key."""
        self._initialize()

        try:
            current_time = int(time.time())

            cursor = self._execute("""
                SELECT id, tenant, user_hash, text, created_at, expires_at, embedding
                FROM cache_entries
                WHERE id = ? AND expires_at > ?
            """, (key, current_time))

            row = cursor.fetchone()
            if not row:
                return None

            # Extend TTL if requested
            if extend_ttl_seconds:
                new_expires_at = current_time + extend_ttl_seconds
                self._execute("""
                    UPDATE cache_entries SET expires_at = ? WHERE id = ?
                """, (new_expires_at, key))
                self._commit()

            result = {
                "text": row["text"],
                "tenant": row["tenant"],
                "user": row["user_hash"],
                "created_at": row["created_at"]
            }

            if row["embedding"]:
                result["embedding"] = row["embedding"]

            return result

        except Exception as e:
            self.logger.error("Failed to retrieve cache entry: %s", e)
            return None

    def get_cache_by_signature(self,
                             tenant: str,
                             key_signature: str,
                             extend_ttl_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cache entry by tenant and signature."""
        key = self._generate_key(tenant, key_signature)
        return self.get_cache(key, extend_ttl_seconds)

    def delete_cache(self, key: str) -> bool:
        """Delete cache entry by key."""
        try:
            cursor = self._execute("DELETE FROM cache_entries WHERE id = ?", (key,))

            if (self.config.cache_enable_embeddings and
                not getattr(self, '_embeddings_disabled', False)):
                self._execute("DELETE FROM cache_vectors WHERE id = ?", (key,))

            self._commit()

            if cursor.rowcount > 0:
                self.logger.debug("Deleted cache entry %s", key)
                return True
            return False

        except Exception as e:
            self.logger.error("Failed to delete cache entry: %s", e)
            return False

    def knn_search(self,
                   tenant: str,
                   query_vector: Union[List[float], 'numpy.ndarray'],
                   k: int = 10,
                   user: Optional[str] = None,
                   additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """Perform KNN similarity search using embeddings."""
        if not self.config.cache_enable_embeddings or getattr(self, '_embeddings_disabled', False):
            self.logger.warning("Vector search not available: embeddings disabled or sqlite-vec unavailable")
            return {"total": 0, "hits": []}

        self._initialize()

        try:
            current_time = int(time.time())

            where_conditions = ["ce.expires_at > ?"]
            params = [current_time]

            where_conditions.append("ce.tenant = ?")
            params.append(tenant)

            if user:
                user_hash = self._hash_user_id(user)
                where_conditions.append("ce.user_hash = ?")
                params.append(user_hash)

            where_clause = " AND ".join(where_conditions)

            query = f"""
                SELECT cv.id, ce.text, ce.user_hash,
                       vec_distance_cosine(cv.embedding, ?) as score
                FROM cache_vectors cv
                JOIN cache_entries ce ON cv.id = ce.id
                WHERE {where_clause}
                ORDER BY score ASC
                LIMIT ?
            """

            # Pack the query vector
            query_vector_bytes = self._pack_f32(query_vector)
            params.insert(0, query_vector_bytes)
            params.append(k)

            cursor = self._execute(query, tuple(params))
            rows = cursor.fetchall()

            hits = []
            for row in rows:
                hit = {
                    "id": row["id"],
                    "text": row["text"],
                    "user": row["user_hash"],
                    "score": float(row["score"])
                }
                hits.append(hit)

            return {"total": len(hits), "hits": hits}

        except Exception as e:
            self.logger.error("KNN search failed: %s", e)
            return {"total": 0, "hits": []}

    def semantic_search(self,
                       tenant: str,
                       query_text: str,
                       k: int = 10,
                       user: Optional[str] = None,
                       additional_filters: Optional[str] = None) -> Dict[str, Any]:
        """Perform semantic similarity search using text query."""
        if not self.config.cache_enable_embeddings or getattr(self, '_embeddings_disabled', False):
            self.logger.warning("Semantic search not available: embeddings disabled or sqlite-vec unavailable")
            return {"total": 0, "hits": []}

        if not self.llm_manager:
            raise ValueError("LLM manager is required for semantic search")

        try:
            query_embedding = self.llm_manager.embd_text(query_text)
            # Check if embedding is valid (list, numpy array, or other array-like)
            if not query_embedding or not (isinstance(query_embedding, list) or hasattr(query_embedding, 'tolist') or hasattr(query_embedding, '__iter__')):
                self.logger.error("Failed to generate embedding for query text")
                return {"total": 0, "hits": []}

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
        """Perform full-text search on cached content."""
        try:
            self._initialize()

            if not self._initialized:
                return {"total": 0, "hits": []}

            # Validate parameters
            try:
                limit = max(1, min(int(limit), 1000))
                offset = max(0, int(offset))
            except (ValueError, TypeError):
                limit = 10
                offset = 0

            current_time = int(time.time())

            # Build WHERE clause
            where_conditions = ["ce.expires_at > ?"]
            params = [current_time]

            where_conditions.append("ce.tenant = ?")
            params.append(tenant)

            if user:
                user_hash = self._hash_user_id(user)
                where_conditions.append("ce.user_hash = ?")
                params.append(user_hash)

            where_clause = " AND ".join(where_conditions)

            # Escape query for FTS
            escaped_query = self.utils._escape_search_text(query.strip())
            if not escaped_query:
                return {"total": 0, "hits": []}

            # Use FTS for text search
            search_query = f"""
                SELECT ce.id, ce.text, ce.user_hash, ce.created_at,
                       rank as score
                FROM cache_fts
                JOIN cache_entries ce ON cache_fts.id = ce.id
                WHERE cache_fts MATCH ? AND {where_clause}
                ORDER BY score
                LIMIT ? OFFSET ?
            """

            fts_params = [escaped_query] + params + [limit, offset]
            cursor = self._execute(search_query, tuple(fts_params))
            rows = cursor.fetchall()

            hits = []
            for row in rows:
                hits.append({
                    "id": row["id"],
                    "text": row["text"],
                    "user": row["user_hash"],
                    "created_at": row["created_at"]
                })

            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM cache_fts
                JOIN cache_entries ce ON cache_fts.id = ce.id
                WHERE cache_fts MATCH ? AND {where_clause}
            """

            count_params = [escaped_query] + params
            cursor = self._execute(count_query, tuple(count_params))
            count_result = cursor.fetchone()
            total = count_result[0] if count_result else 0

            return {"total": total, "hits": hits}

        except Exception as e:
            self.logger.error("Text search failed: %s", e)
            if self._fault_tolerant:
                return {"total": 0, "hits": []}
            raise

    def clear_tenant_cache(self, tenant: str) -> int:
        """Clear all cache entries for a specific tenant."""
        try:
            self._initialize()

            if not self._initialized:
                return 0

            cursor = self._execute("DELETE FROM cache_entries WHERE tenant = ?", (tenant,))
            deleted_count = cursor.rowcount

            # Also delete from vector table if embeddings are enabled and available
            if (self.config.cache_enable_embeddings and
                not getattr(self, '_embeddings_disabled', False)):
                try:
                    self._execute("DELETE FROM cache_vectors WHERE id NOT IN (SELECT id FROM cache_entries)")
                    self.logger.debug("Cleaned up orphaned vector entries")
                except Exception as e:
                    self.logger.warning("Failed to clean up vector entries: %s", e)

            self._commit()

            if deleted_count > 0:
                self.logger.info("Cleared %d cache entries for tenant %s", deleted_count, tenant)
            return deleted_count

        except Exception as e:
            self.logger.error("Failed to clear tenant cache: %s", e)
            if self._fault_tolerant:
                return 0
            raise

    def get_cache_stats(self, tenant: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            self._initialize()

            if not self._initialized:
                return {"total_documents": 0, "index_size": 0}

            current_time = int(time.time())

            cursor = self._execute("""
                SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?
            """, (current_time,))
            result = cursor.fetchone()
            total_docs = result[0] if result else 0

            stats = {
                "total_documents": total_docs,
                "index_size": 0
            }

            if tenant:
                cursor = self._execute("""
                    SELECT COUNT(*) FROM cache_entries
                    WHERE tenant = ? AND expires_at > ?
                """, (tenant, current_time))
                result = cursor.fetchone()
                stats["tenant_documents"] = result[0] if result else 0

            try:
                db_path = Path(self.db_path)
                if db_path.exists():
                    stats["db_size_bytes"] = db_path.stat().st_size
            except Exception:
                pass

            return stats

        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            if self._fault_tolerant:
                return {"total_documents": 0, "index_size": 0}
            raise

    def get_index_info(self) -> Dict[str, Any]:
        """Get detailed information about the database schema."""
        try:
            self._initialize()

            if not self._initialized:
                return {"error": "Cache not initialized"}

            cursor = self._execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'cache_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            cursor = self._execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_cache_%'
            """)
            indexes = [row[0] for row in cursor.fetchall()]

            info = {
                "database_path": self.db_path,
                "tables": tables,
                "indexes": indexes,
                "sqlite_module": SQLITE_MODULE,
                "sqlite_version": getattr(apsw, 'sqlite_version', getattr(apsw, 'sqlitelibversion', lambda: 'unknown')()) if SQLITE_MODULE == 'apsw' else apsw.sqlite_version
            }

            # Check sqlite-vec version
            try:
                cursor = self._execute("SELECT vec_version()")
                result = cursor.fetchone()
                info["sqlite_vec_version"] = result[0] if result else None
            except Exception:
                info["sqlite_vec_version"] = None

            return info

        except Exception as e:
            return {"error": str(e)}

    def get_user_hash(self, user_id: Union[str, int, None]) -> str:
        """Get SHA1 hash of user ID for external use."""
        return self._hash_user_id(user_id)

    def health_check(self) -> Dict[str, Any]:
        """Perform cache health check."""
        try:
            # Test database connection
            conn = self._get_connection()

            # Test basic query
            try:
                if SQLITE_MODULE == 'apsw':
                    # APSW: execute and consume
                    cursor = conn.execute("SELECT 1")
                    list(cursor)  # Consume all results
                else:
                    # sqlite3: execute and fetch
                    conn.execute("SELECT 1").fetchone()
            except Exception as e:
                return {
                    "database_connected": False,
                    "tables_exist": False,
                    "sqlite_vec_available": False,
                    "sqlite_module": SQLITE_MODULE,
                    "error": str(e),
                    "database_path": self.db_path,
                    "fault_tolerant": self._fault_tolerant
                }

            # Test if tables exist
            try:
                cursor = self._execute("""
                    SELECT COUNT(*) FROM sqlite_master
                    WHERE type='table' AND name='cache_entries'
                """)
                result = cursor.fetchone()
                tables_exist = result[0] > 0 if result else False
            except Exception:
                tables_exist = False

            # Test sqlite-vec
            vec_available = False
            try:
                cursor = self._execute("SELECT vec_version()")
                result = cursor.fetchone()
                vec_available = result is not None
            except Exception:
                pass

            return {
                "database_connected": True,
                "tables_exist": tables_exist,
                "sqlite_vec_available": vec_available,
                "sqlite_module": SQLITE_MODULE,
                "database_path": self.db_path,
                "fault_tolerant": self._fault_tolerant
            }

        except Exception as e:
            result = {
                "database_connected": False,
                "tables_exist": False,
                "sqlite_vec_available": False,
                "sqlite_module": SQLITE_MODULE,
                "error": str(e),
                "database_path": self.db_path,
                "fault_tolerant": self._fault_tolerant
            }

            if self._fault_tolerant:
                return result
            else:
                raise

    def is_available(self) -> bool:
        """Check if cache is available and working."""
        try:
            health = self.health_check()
            return health.get("database_connected", False) and health.get("tables_exist", False)
        except Exception:
            return False
