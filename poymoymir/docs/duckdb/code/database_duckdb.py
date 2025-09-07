"""
DuckDB Database operations module

DuckDB implementation of the DatabaseManager class with the same interface as the PostgreSQL version.
Provides all the same database operations but using DuckDB as the backend.

This module contains:
- DatabaseManagerDuckDB class that handles all database connections and operations
- Methods for managing bots, users, sessions, messages, songs, and moderation
- Clean separation of database logic from business logic
- Vector embeddings support through DuckDB extensions
- JSON support for analysis data

Key differences from PostgreSQL version:
- Uses DuckDB instead of PostgreSQL
- Embedded database (no separate server needed)
- JSON instead of JSONB (DuckDB has excellent JSON support)
- Vector support through vss extension
- File-based storage with excellent performance
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

import duckdb

from .config import Config


class DatabaseManagerDuckDB:
    """Manages all database operations for the bot using DuckDB."""

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None, db_path: Optional[str] = None):
        """
        Initialize DatabaseManagerDuckDB with configuration.

        Args:
            config: Configuration object containing database settings
            logger: Optional logger instance
            db_path: Optional path to DuckDB file (defaults to :memory: for in-memory)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Use provided path or extract from config, fallback to in-memory
        if db_path:
            self.db_path = db_path
        elif hasattr(config, 'db_connection_params') and 'database' in config.db_connection_params:
            self.db_path = config.db_connection_params['database']
        else:
            # For development/testing, use in-memory database
            self.db_path = ":memory:"

        # Validate database path for file-based storage
        if self.db_path != ":memory:":
            try:
                import os
                # Ensure directory exists and is writable
                db_dir = os.path.dirname(self.db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

                # Test write permissions by creating a temporary file
                test_path = self.db_path + ".test"
                try:
                    with open(test_path, 'w') as f:
                        f.write("test")
                    os.unlink(test_path)
                except (IOError, OSError) as e:
                    self.logger.warning(f"Cannot write to {self.db_path}: {e}. Falling back to in-memory database.")
                    self.db_path = ":memory:"
            except Exception as e:
                self.logger.warning(f"Database path validation failed: {e}. Using in-memory database.")
                self.db_path = ":memory:"

        self.logger.info(f"Initializing DuckDB at: {self.db_path}")

        # For in-memory databases, keep a persistent connection
        self._persistent_conn = None
        if self.db_path == ":memory:":
            self._persistent_conn = duckdb.connect(self.db_path)

        # Initialize database and schema
        self._init_database()

    def _init_database(self):
        """Initialize database schema and extensions."""
        try:
            conn = self.get_connection()

            # Set home directory for serverless environments using $TMPDIR or fallback
            import os
            tmp_dir = os.environ.get('TMPDIR', '/tmp')
            try:
                conn.execute(f"SET home_directory='{tmp_dir}';")
                self.logger.debug(f"Set DuckDB home directory to: {tmp_dir}")
            except Exception as e:
                self.logger.debug(f"Could not set home directory to {tmp_dir}: {e}")

            # Install required extensions (optional in serverless environments)
            try:
                conn.execute("INSTALL json;")
                conn.execute("LOAD json;")
            except Exception as e:
                self.logger.debug(f"JSON extension install/load: {e}")

            # Try to install vector extension for embeddings (optional)
            try:
                conn.execute("INSTALL vss;")
                conn.execute("LOAD vss;")
                self.vector_support = True
                self.logger.info("Vector support enabled via vss extension")
            except Exception as e:
                self.logger.warning(f"Vector extension not available: {e}")
                self.vector_support = False

            # Create schema
            self._create_schema(conn)

            # Commit changes
            conn.commit()

            # Only close if it's not the persistent connection
            if conn != self._persistent_conn:
                conn.close()

        except Exception as e:
            self.logger.error(f"Failed to initialize DuckDB: {e}")
            raise

    def _create_schema(self, conn):
        """Create all necessary tables and indexes."""

        # Create tables first, then add constraints later if needed

        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                chat_id BIGINT NOT NULL UNIQUE,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id VARCHAR PRIMARY KEY,
                token TEXT NOT NULL UNIQUE,
                username TEXT,
                owner_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Telegram users table for moderation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tg_users (
                id TEXT PRIMARY KEY,
                user_id VARCHAR,
                warnings INTEGER DEFAULT 0,
                blocked BOOLEAN DEFAULT false,
                blocked_reason TEXT,
                blocked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Conversation sessions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                bot_id VARCHAR,
                started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                model TEXT NOT NULL
            )
        """)

        # Messages table
        if self.vector_support:
            # With vector support - use flexible FLOAT[] instead of fixed size
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    user_id VARCHAR,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    analysis TEXT,
                    embedding FLOAT[],
                    tg_msg_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # Without vector support
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    user_id VARCHAR,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    analysis TEXT,
                    embedding TEXT,
                    tg_msg_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Songs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                session_id VARCHAR,
                task_id TEXT,
                title TEXT,
                prompt TEXT,
                style TEXT,
                path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Statuses table for intent and state tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS statuses (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                message_id VARCHAR NOT NULL,
                state TEXT,
                state_reason TEXT,
                intent TEXT,
                intent_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                -- Note: DuckDB has limited foreign key support, so constraints are not enforced
                -- Foreign key references (for documentation only):
                -- session_id -> conversation_sessions.id
                -- user_id -> users.id
                -- message_id -> messages.id
            )
        """)

        # Create indexes for performance
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tg_users_user_id ON tg_users(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_bot ON conversation_sessions(user_id, bot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON conversation_sessions(started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_songs_task_id ON songs(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_songs_user_id ON songs(user_id)")
            # Indexes for statuses table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_statuses_session_id ON statuses(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_statuses_user_id ON statuses(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_statuses_message_id ON statuses(message_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_statuses_created_at ON statuses(created_at)")
        except Exception as e:
            self.logger.warning(f"Could not create some indexes: {e}")

        self.logger.info("Database schema created successfully")

    def get_connection(self):
        """Return a DuckDB connection."""
        try:
            # For in-memory databases, reuse the persistent connection
            if self.db_path == ":memory:" and self._persistent_conn:
                return self._persistent_conn
            return duckdb.connect(self.db_path)
        except Exception as e:
            self.logger.exception("Failed to connect to DuckDB: %s", e)
            raise

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute SELECT returning a single row as dict, or None."""
        conn = self.get_connection()
        try:
            result = conn.execute(sql, params).fetchone()
            if result:
                # Get column names and create dict
                columns = [desc[0] for desc in conn.description]
                return dict(zip(columns, result))
            return None
        finally:
            # Only close if it's not the persistent connection
            if conn != self._persistent_conn:
                conn.close()

    def query_all(self, sql: str, params: tuple = ()) -> List[dict]:
        """Execute SELECT returning all rows as list of dicts."""
        conn = self.get_connection()
        try:
            result = conn.execute(sql, params).fetchall()
            if result:
                # Get column names and create list of dicts
                columns = [desc[0] for desc in conn.description]
                return [dict(zip(columns, row)) for row in result]
            return []
        finally:
            # Only close if it's not the persistent connection
            if conn != self._persistent_conn:
                conn.close()

    def execute(self, sql: str, params: tuple = ()):
        """Execute INSERT/UPDATE/DELETE and commit."""
        conn = self.get_connection()
        try:
            conn.execute(sql, params)
            # DuckDB commits automatically, but let's be explicit
            conn.commit()
        except Exception as e:
            self.logger.error("SQL execution failed: %s", e)
            raise
        finally:
            # Only close if it's not the persistent connection
            if conn != self._persistent_conn:
                conn.close()

    # ──────────────────────────
    #  BOT OPERATIONS
    # ──────────────────────────

    def get_or_create_bot(self, token: str, username: Optional[str] = None) -> str:
        """Get existing bot or create new one, return bot ID."""
        md5_hash = hashlib.md5(token.encode('utf-8')).hexdigest()
        rec = self.query_one("SELECT id FROM bots WHERE token = ? LIMIT 1", (md5_hash,))
        if rec:
            return rec["id"]

        bot_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO bots(id, token, username, owner_id) VALUES (?, ?, ?, ?)",
            (bot_id, md5_hash, username, None)
        )
        self.logger.debug("Created bot %s (token hash %s)", bot_id, md5_hash)
        return bot_id

    # ──────────────────────────
    #  USER OPERATIONS
    # ──────────────────────────

    def get_or_create_user(self, chat_id: int, full_name: str) -> str:
        """Get existing user or create new one, return user UUID."""
        rec = self.query_one("SELECT id FROM users WHERE chat_id = ? LIMIT 1", (chat_id,))
        if rec:
            return rec["id"]

        user_uuid = str(uuid.uuid4())
        self.execute(
            "INSERT INTO users(id, chat_id, full_name) VALUES (?, ?, ?)",
            (user_uuid, chat_id, full_name)
        )
        self.logger.debug("Created user %s for chat_id %s", user_uuid, chat_id)
        return user_uuid

    def ensure_user_exists(self, tg_user_id: str, user_uuid: str):
        """Ensure that telegram user record exists."""
        try:
            # Проверяем, что tg_user_id может быть преобразован в int
            int(tg_user_id)
            rec = self.query_one("SELECT id FROM tg_users WHERE id = ?", (tg_user_id,))
            if not rec:
                self.execute(
                    "INSERT INTO tg_users(id, user_id, warnings, blocked) VALUES (?, ?, ?, ?)",
                    (tg_user_id, user_uuid, 0, False)
                )
        except (ValueError, TypeError) as e:
            self.logger.error("Invalid tg_user_id format in ensure_user_exists: %s, error: %s", tg_user_id, e)

    def get_user_moderation_info(self, tg_user_id: str) -> Dict[str, Any]:
        """Get user warnings and blocked status."""
        try:
            # Проверяем, что tg_user_id может быть преобразован в int
            int(tg_user_id)
            rec = self.query_one("SELECT warnings, blocked FROM tg_users WHERE id = ?", (tg_user_id,))
            if rec:
                return {"warnings": rec.get("warnings", 0), "blocked": rec.get("blocked", False)}
            return {"warnings": 0, "blocked": False}
        except (ValueError, TypeError) as e:
            self.logger.error("Invalid tg_user_id format: %s, error: %s", tg_user_id, e)
            return {"warnings": 0, "blocked": False}

    def update_user_warnings(self, tg_user_id: str, warnings: int):
        """Update user warnings count."""
        self.execute("UPDATE tg_users SET warnings = ? WHERE id = ?", (warnings, tg_user_id))

    def block_user(self, tg_user_id: str, reason: str):
        """Block user with reason."""
        self.execute(
            "UPDATE tg_users SET blocked = true, blocked_reason = ?, blocked_at = CURRENT_TIMESTAMP WHERE id = ?",
            (reason, tg_user_id)
        )

    def get_user_by_tg_id(self, tg_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user record by telegram user ID."""
        return self.query_one(
            "SELECT u.full_name FROM tg_users tg JOIN users u ON tg.user_id = u.id WHERE tg.id = ?",
            (tg_user_id,)
        )

    # ──────────────────────────
    #  SESSION OPERATIONS
    # ──────────────────────────

    def get_active_session(self, user_uuid: str, bot_uuid: str, session_lifetime_seconds: int) -> str:
        """Get active session or create new one, return session UUID."""
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=session_lifetime_seconds)
        rec = self.query_one(
            "SELECT id, started_at FROM conversation_sessions "
            "WHERE user_id = ? AND bot_id = ? AND ended_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (user_uuid, bot_uuid)
        )

        if rec:
            started_at = rec["started_at"]
            if started_at:
                # Ensure both datetimes are timezone-aware for comparison
                if started_at.tzinfo is None:
                    # If database returns naive datetime, assume UTC
                    started_at = started_at.replace(tzinfo=timezone.utc)
                elif cutoff.tzinfo is None:
                    # If cutoff is naive, make it timezone-aware
                    cutoff = cutoff.replace(tzinfo=timezone.utc)

                if started_at > cutoff:
                    return rec["id"]

        session_uuid = str(uuid.uuid4())
        ai_model = getattr(self.config, 'ai_model', 'default-model')
        self.execute(
            "INSERT INTO conversation_sessions(id, user_id, bot_id, started_at, model) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (session_uuid, user_uuid, bot_uuid, ai_model)
        )
        self.logger.debug("Created session %s", session_uuid)
        return session_uuid

    # ──────────────────────────
    #  MESSAGE OPERATIONS
    # ──────────────────────────

    def fetch_history(self, session_uuid: str, limit_count: Optional[int] = None) -> List[Dict[str, str]]:
        """Fetch message history for a session."""
        if limit_count is not None:
            # Получаем количество всех сообщений для вычисления OFFSET
            total_count = self.query_one(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
                (session_uuid,)
            )["cnt"]
            offset = max(0, total_count - limit_count)
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC OFFSET ? LIMIT ?",
                (session_uuid, offset, limit_count)
            )
        else:
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_uuid,)
            )
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def save_message(self, session_uuid: str, user_uuid: str, role: str, content: str, embedding: List[float], tg_msg_id: int) -> str:
        """Save a message to the database and return message ID."""
        msg_id = str(uuid.uuid4())
        self.logger.debug("Saving message: session=%s, user=%s, role=%s, content_length=%d",
                         session_uuid, user_uuid, role, len(content))

        # Handle different embedding types (lists, numpy arrays, None)
        processed_embedding = None
        if embedding is not None:
            try:
                # Handle numpy arrays by converting to list
                if hasattr(embedding, 'tolist'):
                    processed_embedding = embedding.tolist()
                elif hasattr(embedding, '__iter__') and not isinstance(embedding, str):
                    processed_embedding = list(embedding)
                else:
                    processed_embedding = embedding
            except Exception as e:
                self.logger.warning(f"Failed to process embedding: {e}")
                processed_embedding = None

        try:
            # Always store embedding as JSON string for compatibility
            embedding_json = json.dumps(processed_embedding) if processed_embedding else None
            self.execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at, embedding, tg_msg_id) "
                "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)",
                (msg_id, session_uuid, user_uuid, role, content, embedding_json, tg_msg_id)
            )
            self.logger.debug("Message saved successfully with ID: %s", msg_id)
        except Exception as e:
            self.logger.error("Failed to save message: %s", e)
            raise
        return msg_id

    def update_message_analysis(self, msg_id: str, analysis: Dict[str, Any]):
        """Update message with analysis data (intent, emotion, etc.)."""
        self.execute(
            "UPDATE messages SET analysis = ? WHERE id = ?",
            (json.dumps(analysis), msg_id)
        )

    # ──────────────────────────
    #  STATUS OPERATIONS
    # ──────────────────────────

    def save_status(self, session_id: str, user_id: str, message_id: str,
                   state: Optional[str] = None, state_reason: Optional[str] = None,
                   intent: Optional[str] = None, intent_reason: Optional[str] = None) -> str:
        """Save intent and state information to the statuses table and return status ID."""
        status_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO statuses(id, session_id, user_id, message_id, state, state_reason, intent, intent_reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (status_id, session_id, user_id, message_id, state, state_reason, intent, intent_reason)
        )
        self.logger.debug("Status saved successfully with ID: %s", status_id)
        return status_id

    def get_status_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get status information by message ID."""
        return self.query_one(
            "SELECT * FROM statuses WHERE message_id = ? ORDER BY created_at DESC LIMIT 1",
            (message_id,)
        )

    def get_statuses_by_session(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all statuses for a session, ordered by creation time."""
        if limit:
            return self.query_all(
                "SELECT * FROM statuses WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            )
        return self.query_all(
            "SELECT * FROM statuses WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        )

    # ──────────────────────────
    #  SONG OPERATIONS
    # ──────────────────────────

    def save_song(self, user_uuid: str, session_uuid: str, task_id: str, title: str, prompt: str, style: str) -> str:
        """Save song generation request and return song ID."""
        song_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO songs(id, user_id, session_id, task_id, title, prompt, style, created_at)"
            "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (song_id, user_uuid, session_uuid, task_id, title, prompt, style)
        )
        return song_id

    def update_song_path(self, task_id: str, path: str):
        """Update song path after processing."""
        self.execute("UPDATE songs SET path = ? WHERE task_id = ?", (path, task_id))

    def get_user_by_song_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get telegram user ID by song task ID."""
        return self.query_one(
            "SELECT tg.id AS telegram_user_id FROM songs AS s "
            "JOIN tg_users AS tg ON s.user_id = tg.user_id "
            "WHERE s.task_id = ? LIMIT 1",
            (task_id,)
        )

    # ──────────────────────────
    #  MODERATION OPERATIONS
    # ──────────────────────────

    def moderate_user(self, tg_user_id: str, additional_reason: str = "Нарушение правил") -> Optional[int]:
        """
        Moderate user based on warnings count.

        Returns:
            None: User not found or no action taken
            1: First warning (ban temporarily)
            2: Second warning (permanent ban)
            3: User already has too many warnings and is blocked
        """
        # Fetch warnings and blocked status
        user_info = self.get_user_moderation_info(tg_user_id)
        warnings = user_info["warnings"]
        blocked = user_info["blocked"]

        if warnings > 2 and blocked:
            return 3

        new_warnings = warnings + 1
        self.update_user_warnings(tg_user_id, new_warnings)

        if warnings == 1 and not blocked:
            # First warning → ban
            self.block_user(tg_user_id, additional_reason)
            return 1
        elif warnings >= 2 and not blocked:
            # Second warning → permanent ban
            self.block_user(tg_user_id, additional_reason)
            return 2

        return None

    # ──────────────────────────
    #  UTILITY OPERATIONS
    # ──────────────────────────

    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        conn = self.get_connection()
        try:
            # Get table sizes
            tables_info = conn.execute("""
                SELECT table_name,
                       (SELECT COUNT(*) FROM information_schema.tables t2
                        WHERE t2.table_name = t.table_name) as row_count
                FROM information_schema.tables t
                WHERE table_schema = 'main'
                ORDER BY table_name
            """).fetchall()

            return {
                "database_type": "DuckDB",
                "database_path": self.db_path,
                "vector_support": self.vector_support,
                "tables": [dict(zip(['table_name', 'row_count'], row)) for row in tables_info]
            }
        finally:
            conn.close()

    def vacuum_database(self):
        """Optimize database storage (equivalent to PostgreSQL VACUUM)."""
        conn = self.get_connection()
        try:
            conn.execute("PRAGMA optimize;")
            self.logger.info("Database optimized successfully")
        finally:
            conn.close()

    def backup_database(self, backup_path: str):
        """Create a backup of the database."""
        if self.db_path == ":memory:":
            raise ValueError("Cannot backup in-memory database")

        conn = self.get_connection()
        try:
            conn.execute(f"EXPORT DATABASE '{backup_path}';")
            self.logger.info(f"Database backed up to: {backup_path}")
        finally:
            conn.close()

    def close(self):
        """Close any persistent connections."""
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
        self.logger.info("Database manager closed")


# Compatibility alias for easy switching
DatabaseManager = DatabaseManagerDuckDB
