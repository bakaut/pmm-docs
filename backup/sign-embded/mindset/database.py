"""
Database operations module

Centralises all database operations in a single DatabaseManager class.

This module contains:
- DatabaseManager class that handles all database connections and operations
- Methods for managing bots, users, sessions, messages, songs, and moderation
- Clean separation of database logic from business logic
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from psycopg2 import connect, Error as PgError
from psycopg2.extras import RealDictCursor

from .config import Config


class DatabaseManager:
    """Manages all database operations for the bot."""

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """
        Initialize DatabaseManager with configuration.

        Args:
            config: Configuration object containing database settings
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def get_connection(self):
        """Return a new psycopg2 connection."""
        try:
            conn = connect(**self.config.db_connection_params)
            conn.set_client_encoding('UTF8')
            return conn
        except PgError as e:
            self.logger.exception("Failed to connect to Postgres: %s", e)
            raise

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute SELECT returning a single row as dict, or None."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            conn.close()

    def query_all(self, sql: str, params: tuple = ()) -> List[dict]:
        """Execute SELECT returning all rows as list of dicts."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()):
        """Execute INSERT/UPDATE/DELETE and commit."""
        # self.logger.debug("Executing SQL: %s with params: %s", sql, params)
        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    # self.logger.debug("SQL executed successfully, rowcount: %s", cur.rowcount)
        except Exception as e:
            self.logger.error("SQL execution failed: %s", e)
            raise
        finally:
            conn.close()

    # ──────────────────────────
    #  BOT OPERATIONS
    # ──────────────────────────

    def get_or_create_bot(self, token: str, username: Optional[str] = None) -> str:
        """Get existing bot or create new one, return bot ID."""
        md5_hash = hashlib.md5(token.encode('utf-8')).hexdigest()
        rec = self.query_one("SELECT id FROM bots WHERE token = %s LIMIT 1", (md5_hash,))
        if rec:
            return rec["id"]

        bot_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO bots(id, token, username, owner_id) VALUES (%s, %s, %s, %s)",
            (bot_id, md5_hash, username, None)
        )
        self.logger.debug("Created bot %s (token hash %s)", bot_id, md5_hash)
        return bot_id

    # ──────────────────────────
    #  USER OPERATIONS
    # ──────────────────────────

    def get_or_create_user(self, chat_id: int, full_name: str) -> str:
        """Get existing user or create new one, return user UUID."""
        rec = self.query_one("SELECT id FROM users WHERE chat_id = %s LIMIT 1", (chat_id,))
        if rec:
            return rec["id"]

        user_uuid = str(uuid.uuid4())
        self.execute(
            "INSERT INTO users(id, chat_id, full_name) VALUES (%s, %s, %s)",
            (user_uuid, chat_id, full_name)
        )
        self.logger.debug("Created user %s for chat_id %s", user_uuid, chat_id)
        return user_uuid

    def ensure_user_exists(self, tg_user_id: str, user_uuid: str):
        """Ensure that telegram user record exists."""
        try:
            # Проверяем, что tg_user_id может быть преобразован в int
            int(tg_user_id)
            rec = self.query_one("SELECT id FROM tg_users WHERE id = %s", (tg_user_id,))
            if not rec:
                self.execute(
                    "INSERT INTO tg_users(id, user_id, warnings, blocked) VALUES (%s, %s, %s, %s)",
                    (tg_user_id, user_uuid, 0, False)
                )
        except (ValueError, TypeError) as e:
            self.logger.error("Invalid tg_user_id format in ensure_user_exists: %s, error: %s", tg_user_id, e)

    def get_user_moderation_info(self, tg_user_id: str) -> Dict[str, Any]:
        """Get user warnings and blocked status."""
        try:
            # Проверяем, что tg_user_id может быть преобразован в int
            int(tg_user_id)
            rec = self.query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
            if rec:
                return {"warnings": rec.get("warnings", 0), "blocked": rec.get("blocked", False)}
            return {"warnings": 0, "blocked": False}
        except (ValueError, TypeError) as e:
            self.logger.error("Invalid tg_user_id format: %s, error: %s", tg_user_id, e)
            return {"warnings": 0, "blocked": False}

    def update_user_warnings(self, tg_user_id: str, warnings: int):
        """Update user warnings count."""
        self.execute("UPDATE tg_users SET warnings = %s WHERE id = %s", (warnings, tg_user_id))

    def block_user(self, tg_user_id: str, reason: str):
        """Block user with reason."""
        self.execute(
            "UPDATE tg_users SET blocked = TRUE, blocked_reason = %s, blocked_at = NOW() WHERE id = %s",
            (reason, tg_user_id)
        )

    def get_user_by_tg_id(self, tg_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user record by telegram user ID."""
        return self.query_one(
            "SELECT u.full_name FROM tg_users tg JOIN users u ON tg.user_id = u.id WHERE tg.id = %s",
            (tg_user_id,)
        )

    # ──────────────────────────
    #  SESSION OPERATIONS
    # ──────────────────────────

    def get_active_session(self, user_uuid: str, bot_uuid: str, session_lifetime_seconds: int) -> str:
        """Get active session or create new one, return session UUID."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=session_lifetime_seconds)
        rec = self.query_one(
            "SELECT id, started_at FROM conversation_sessions "
            "WHERE user_id = %s AND bot_id = %s AND ended_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (user_uuid, bot_uuid)
        )

        if rec:
            started_at = rec["started_at"]
            if started_at and started_at > cutoff:
                return rec["id"]

        session_uuid = str(uuid.uuid4())
        ai_model = self.config.ai_model
        self.execute(
            "INSERT INTO conversation_sessions(id, user_id, bot_id, started_at, model) "
            "VALUES (%s, %s, %s, NOW(), %s)",
            (session_uuid, user_uuid, bot_uuid, ai_model)
        )
        self.logger.debug("Created session %s", session_uuid)
        return session_uuid

    def end_session(self, session_uuid: str) -> None:
        """End the current session by setting ended_at timestamp."""
        try:
            self.execute(
                "UPDATE conversation_sessions SET ended_at = NOW() WHERE id = %s",
                (session_uuid,)
            )
            self.logger.debug("Ended session %s", session_uuid)
        except Exception as e:
            self.logger.error("Failed to end session %s: %s", session_uuid, e)
            raise

    # ──────────────────────────
    #  MESSAGE OPERATIONS
    # ──────────────────────────

    def fetch_history(self, session_uuid: str, limit_count: Optional[int] = None) -> List[Dict[str, str]]:
        """Fetch message history for a session."""
        if limit_count is not None:
            # Получаем количество всех сообщений для вычисления OFFSET
            total_count = self.query_one(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s",
                (session_uuid,)
            )["cnt"]
            offset = max(0, total_count - limit_count)
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
                (session_uuid, offset, limit_count)
            )
        else:
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_uuid,)
            )
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def save_message(self, session_uuid: str, user_uuid: str, role: str, content: str, embedding: List[float], tg_msg_id: int) -> str:
        """Save a message to the database and return message ID."""
        msg_id = str(uuid.uuid4())
        self.logger.debug("Saving message: session=%s, user=%s, role=%s, content_length=%d",
                         session_uuid, user_uuid, role, len(content))
        try:
            self.execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at, embedding, tg_msg_id) "
                "VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)",
                (msg_id, session_uuid, user_uuid, role, content, embedding, tg_msg_id)
            )
            self.logger.debug("Message saved successfully with ID: %s", msg_id)
        except Exception as e:
            self.logger.error("Failed to save message: %s", e)
            raise
        return msg_id

    def update_message_analysis(self, msg_id: str, analysis: Dict[str, Any]):
        """Update message with analysis data (intent, emotion, etc.)."""
        self.execute(
            "UPDATE messages SET analysis = %s WHERE id = %s",
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())",
            (status_id, session_id, user_id, message_id, state, state_reason, intent, intent_reason)
        )
        self.logger.debug("Status saved successfully with ID: %s", status_id)
        return status_id

    def get_status_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get status information by message ID."""
        return self.query_one(
            "SELECT * FROM statuses WHERE message_id = %s ORDER BY created_at DESC LIMIT 1",
            (message_id,)
        )

    def get_statuses_by_session(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all statuses for a session, ordered by creation time."""
        if limit:
            return self.query_all(
                "SELECT * FROM statuses WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
                (session_id, limit)
            )
        return self.query_all(
            "SELECT * FROM statuses WHERE session_id = %s ORDER BY created_at DESC",
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
            (song_id, user_uuid, session_uuid, task_id, title, prompt, style)
        )
        return song_id

    def update_song_path(self, task_id: str, path: str):
        """Update song path after processing."""
        self.execute("UPDATE songs SET path = %s WHERE task_id = %s", (path, task_id))

    def get_user_by_song_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get telegram user ID by song task ID."""
        return self.query_one(
            "SELECT tg.id AS telegram_user_id FROM public.songs AS s "
            "JOIN public.tg_users AS tg ON s.user_id = tg.user_id "
            "WHERE s.task_id = %s LIMIT 1",
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
    #  SUMMARYIZATION OPERATIONS
    # ──────────────────────────

    def save_memory(self, session_id: str, msg_id: str, m_type: str,
                    text: str, trigger: str,
                    metadata: Optional[Dict[str, Any]] = {}) -> str:
        """Save a conversation summary and return summary ID."""
        summary_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO memories(id, session_id, msg_id, m_type, text, trigger, metadata, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
            (summary_id, session_id, msg_id, m_type, text, trigger, json.dumps(metadata))
        )
        self.logger.debug("Memory saved successfully with ID: %s", summary_id)
        return summary_id

    # ──────────────────────────
    #  PHRASES OPERATIONS
    # ──────────────────────────

    def save_phrase(self, key: str, phrase: str, phrase_embd: List[float], processed: bool = False, force_processed: bool = False) -> str:
        """Save a phrase and its embedding to the database and return phrase ID."""
        phrase_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO phrases(id, key, phrase, phrase_embd, processed, force_processed, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            (phrase_id, key, phrase, phrase_embd, processed, force_processed)
        )
        self.logger.debug("Phrase saved successfully with ID: %s", phrase_id)
        return phrase_id

    def get_phrase_by_id(self, phrase_id: str) -> Optional[Dict[str, Any]]:
        """Get phrase information by phrase ID."""
        return self.query_one(
            "SELECT * FROM phrases WHERE id = %s",
            (phrase_id,)
        )

    def get_phrases_by_key(self, key: str, include_processed: bool = True) -> List[Dict[str, Any]]:
        """Get all phrases for a specific key.

        Args:
            key: The phrase key to search for
            include_processed: If False, only return unprocessed phrases
        """
        if include_processed:
            return self.query_all(
                "SELECT * FROM phrases WHERE key = %s",
                (key,)
            )
        else:
            return self.query_all(
                "SELECT * FROM phrases WHERE key = %s AND processed = FALSE",
                (key,)
            )

    def get_unprocessed_phrases(self) -> List[Dict[str, Any]]:
        """Get all unprocessed phrases."""
        return self.query_all(
            "SELECT * FROM phrases WHERE processed = FALSE"
        )

    def update_phrase_processed_status(self, phrase_id: str, processed: bool = True) -> bool:
        """Update the processed status of a phrase.

        Args:
            phrase_id: The ID of the phrase to update
            processed: The new processed status

        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                "UPDATE phrases SET processed = %s WHERE id = %s",
                (processed, phrase_id)
            )
            return True
        except Exception as e:
            self.logger.error(f"Error updating phrase processed status: {e}")
            return False

    def semantic_search_phrases(self, query_embd: List[float], key: str = None, limit: int = 5, include_processed: bool = True) -> List[Dict[str, Any]]:
        """Perform semantic search on phrases using cosine similarity.

        Args:
            query_embd: The embedding vector to search with
            key: Optional key to filter by
            limit: Maximum number of results to return
            include_processed: If False, only search unprocessed phrases
        """
        if key:
            if include_processed:
                return self.query_all(
                    "SELECT *, 1 - (phrase_embd <=> %s::vector) as similarity FROM phrases WHERE key = %s ORDER BY phrase_embd <=> %s::vector LIMIT %s",
                    (query_embd, key, query_embd, limit)
                )
            else:
                return self.query_all(
                    "SELECT *, 1 - (phrase_embd <=> %s::vector) as similarity FROM phrases WHERE key = %s AND processed = FALSE ORDER BY phrase_embd <=> %s::vector LIMIT %s",
                    (query_embd, key, query_embd, limit)
                )
        else:
            if include_processed:
                return self.query_all(
                    "SELECT *, 1 - (phrase_embd <=> %s::vector) as similarity FROM phrases ORDER BY phrase_embd <=> %s::vector LIMIT %s",
                    (query_embd, query_embd, limit)
                )
            else:
                return self.query_all(
                    "SELECT *, 1 - (phrase_embd <=> %s::vector) as similarity FROM phrases WHERE processed = FALSE ORDER BY phrase_embd <=> %s::vector LIMIT %s",
                    (query_embd, query_embd, limit)
                )

    def full_text_search_phrases(self, query_text: str, key: str = None, limit: int = 5, include_processed: bool = True) -> List[Dict[str, Any]]:
        """Perform full-text search on phrases.

        Args:
            query_text: The text to search for
            key: Optional key to filter by
            limit: Maximum number of results to return
            include_processed: If False, only search unprocessed phrases
        """
        if key:
            if include_processed:
                return self.query_all(
                    "SELECT *, ts_rank_cd(to_tsvector('russian', phrase), plainto_tsquery('russian', %s)) as rank "
                    "FROM phrases WHERE key = %s AND to_tsvector('russian', phrase) @@ plainto_tsquery('russian', %s) "
                    "ORDER BY rank DESC LIMIT %s",
                    (query_text, key, query_text, limit)
                )
            else:
                return self.query_all(
                    "SELECT *, ts_rank_cd(to_tsvector('russian', phrase), plainto_tsquery('russian', %s)) as rank "
                    "FROM phrases WHERE key = %s AND processed = FALSE AND to_tsvector('russian', phrase) @@ plainto_tsquery('russian', %s) "
                    "ORDER BY rank DESC LIMIT %s",
                    (query_text, key, query_text, limit)
                )
        else:
            if include_processed:
                return self.query_all(
                    "SELECT *, ts_rank_cd(to_tsvector('russian', phrase), plainto_tsquery('russian', %s)) as rank "
                    "FROM phrases WHERE to_tsvector('russian', phrase) @@ plainto_tsquery('russian', %s) "
                    "ORDER BY rank DESC LIMIT %s",
                    (query_text, query_text, limit)
                )
            else:
                return self.query_all(
                    "SELECT *, ts_rank_cd(to_tsvector('russian', phrase), plainto_tsquery('russian', %s)) as rank "
                    "FROM phrases WHERE processed = FALSE AND to_tsvector('russian', phrase) @@ plainto_tsquery('russian', %s) "
                    "ORDER BY rank DESC LIMIT %s",
                    (query_text, query_text, limit)
                )
