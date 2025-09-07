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

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None, cache_manager=None):
        """
        Initialize DatabaseManager with configuration.

        Args:
            config: Configuration object containing database settings
            logger: Optional logger instance
            cache_manager: Optional cache manager for incremental caching
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cache_manager = cache_manager
        
        # Initialize utils for helper functions
        from .utils import Utils
        self.utils = Utils(config, logger)
        
        # Incremental caching configuration
        self.HISTORY_CACHE_N = 76  # Total messages to consider for caching
        self.HISTORY_CACHE_TTL = 86400  # 24 hours in seconds
        self.HISTORY_DYNAMIC_COUNT = 2  # Last N messages that change frequently

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

    # ──────────────────────────
    #  MESSAGE OPERATIONS
    # ──────────────────────────

    def fetch_history(self, session_uuid: str, limit_count: Optional[int] = None) -> List[Dict[str, str]]:
        """Fetch message history for a session with incremental caching support."""
        
        # Debug: Log the incoming request with full context
        self.logger.info("[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST START =====")
        self.logger.info("[CACHE_DEBUG] fetch_history called: session=%s, limit=%s, cache_available=%s", 
                        session_uuid[:8] + "...", limit_count, self.cache_manager is not None)
        
        # Check cache conditions with detailed reasoning
        cache_conditions_met = (
            self.cache_manager is not None and 
            limit_count is not None and 
            limit_count == self.HISTORY_CACHE_N
        )
        
        self.logger.debug("[CACHE_DEBUG] Cache condition analysis:")
        self.logger.debug("[CACHE_DEBUG]   - cache_manager available: %s", self.cache_manager is not None)
        self.logger.debug("[CACHE_DEBUG]   - limit_count provided: %s (value: %s)", limit_count is not None, limit_count)
        self.logger.debug("[CACHE_DEBUG]   - limit matches CACHE_N: %s (expected: %d)", 
                         limit_count == self.HISTORY_CACHE_N if limit_count is not None else False, 
                         self.HISTORY_CACHE_N)
        self.logger.debug("[CACHE_DEBUG]   - all conditions met: %s", cache_conditions_met)
        
        # If cache conditions are met, try incremental caching
        if cache_conditions_met:
            try:
                self.logger.info("[CACHE_DEBUG] DECISION: Attempting incremental cache (all conditions satisfied)")
                self.logger.info("[CACHE_DEBUG] Cache strategy: N-2 incremental (N=%d, stable=%d, dynamic=%d)", 
                               self.HISTORY_CACHE_N, self.HISTORY_CACHE_N - self.HISTORY_DYNAMIC_COUNT, 
                               self.HISTORY_DYNAMIC_COUNT)
                
                start_time = datetime.now()
                result = self._fetch_history_with_incremental_cache(session_uuid, limit_count)
                cache_time = (datetime.now() - start_time).total_seconds() * 1000
                
                self.logger.info("[CACHE_DEBUG] RESULT: Incremental cache completed in %.2fms, returned %d messages", 
                               cache_time, len(result))
                self.logger.info("[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST END (CACHED) =====")
                return result
                
            except Exception as e:
                self.logger.error("[CACHE_DEBUG] FALLBACK: Incremental cache failed, falling back to database: %s", e)
                self.logger.warning("[CACHE_DEBUG] Exception type: %s", type(e).__name__)
                # Fall through to original implementation
        else:
            # Log specific reasons why cache was not used
            if self.cache_manager is None:
                self.logger.info("[CACHE_DEBUG] DECISION: Cache bypass - no cache manager configured")
            elif limit_count is None:
                self.logger.info("[CACHE_DEBUG] DECISION: Cache bypass - no limit specified (full history requested)")
            elif limit_count != self.HISTORY_CACHE_N:
                self.logger.info("[CACHE_DEBUG] DECISION: Cache bypass - limit mismatch (got %d, need %d for caching)", 
                               limit_count, self.HISTORY_CACHE_N)
                self.logger.debug("[CACHE_DEBUG] Cache only optimizes for specific message count patterns")
            else:
                self.logger.warning("[CACHE_DEBUG] DECISION: Cache bypass - unknown condition failure")
        
        # Original implementation (fallback or non-cached scenarios)
        self.logger.info("[CACHE_DEBUG] DECISION: Using direct database query for session %s", session_uuid[:8] + "...")
        self.logger.debug("[CACHE_DEBUG] Direct query parameters: limit=%s", limit_count)
        
        start_time = datetime.now()
        
        if limit_count is not None:
            self.logger.debug("[CACHE_DEBUG] Executing limited query with offset calculation")
            # Получаем количество всех сообщений для вычисления OFFSET
            count_start = datetime.now()
            total_count = self.query_one(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s",
                (session_uuid,)
            )["cnt"]
            count_time = (datetime.now() - count_start).total_seconds() * 1000
            
            offset = max(0, total_count - limit_count)
            self.logger.debug("[CACHE_DEBUG] Query parameters: total=%d, offset=%d, limit=%d (count query: %.2fms)", 
                            total_count, offset, limit_count, count_time)
            
            query_start = datetime.now()
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
                (session_uuid, offset, limit_count)
            )
            query_time = (datetime.now() - query_start).total_seconds() * 1000
            self.logger.debug("[CACHE_DEBUG] Main query completed in %.2fms, returned %d rows", query_time, len(rows))
        else:
            self.logger.debug("[CACHE_DEBUG] Executing unlimited query (full history)")
            query_start = datetime.now()
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_uuid,)
            )
            query_time = (datetime.now() - query_start).total_seconds() * 1000
            self.logger.debug("[CACHE_DEBUG] Full history query completed in %.2fms, returned %d rows", query_time, len(rows))
        
        # Transform results
        transform_start = datetime.now()
        result = [{"role": r["role"], "content": r["content"]} for r in rows]
        transform_time = (datetime.now() - transform_start).total_seconds() * 1000
        
        db_time = (datetime.now() - start_time).total_seconds() * 1000
        
        self.logger.info("[CACHE_DEBUG] RESULT: Direct DB query completed in %.2fms, returned %d messages", 
                       db_time, len(result))
        self.logger.debug("[CACHE_DEBUG] Performance breakdown: query=%.2fms, transform=%.2fms, total=%.2fms", 
                        query_time, transform_time, db_time)
        
        # Compare with cache performance estimate
        estimated_cache_time = 5.0  # Estimated cache operation time
        performance_impact = db_time / estimated_cache_time
        if performance_impact > 3.0:
            self.logger.info("[CACHE_DEBUG] Performance note: DB query %.1fx slower than estimated cache time", performance_impact)
        
        self.logger.info("[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST END (DIRECT) =====")
        return result

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
            
            # Invalidate cache for this session since we added a new message
            self.logger.info("[CACHE_DEBUG] New message saved, triggering cache invalidation for session %s", 
                           session_uuid)
            self.invalidate_history_cache(session_uuid)
            
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
    #  INCREMENTAL CACHING OPERATIONS
    # ──────────────────────────

    def _fetch_history_with_incremental_cache(self, session_uuid: str, limit_count: int) -> List[Dict[str, str]]:
        """Fetch history using incremental caching strategy (N-2 stable + 2 dynamic)."""
        
        self.logger.info("[CACHE_DEBUG] Starting incremental cache fetch for session %s", session_uuid)
        self.logger.debug("[CACHE_DEBUG] Input parameters: limit_count=%d, CACHE_N=%d, DYNAMIC_COUNT=%d, TTL=%d", 
                         limit_count, self.HISTORY_CACHE_N, self.HISTORY_DYNAMIC_COUNT, self.HISTORY_CACHE_TTL)
        
        # Get total message count
        count_start = datetime.now()
        total_count = self.query_one(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s",
            (session_uuid,)
        )["cnt"]
        count_time = (datetime.now() - count_start).total_seconds() * 1000
        
        self.logger.info("[CACHE_DEBUG] Total messages in session: %d (query took %.2fms)", 
                        total_count, count_time)
        
        # Case 1: Too few messages for caching strategy
        if total_count <= self.HISTORY_DYNAMIC_COUNT:
            self.logger.warning("[CACHE_DEBUG] CASE 1: Too few messages (%d <= %d) for caching, using direct fetch", 
                              total_count, self.HISTORY_DYNAMIC_COUNT)
            self.logger.debug("[CACHE_DEBUG] Reason: Cannot split into stable+dynamic when total <= dynamic count")
            return self._fetch_history_direct(session_uuid, limit_count)
        
        # Calculate stable count (all messages except the last N)
        stable_count = min(limit_count - self.HISTORY_DYNAMIC_COUNT, total_count - self.HISTORY_DYNAMIC_COUNT)
        
        self.logger.info("[CACHE_DEBUG] Cache strategy calculation: stable=%d, dynamic=%d, total_requested=%d", 
                        stable_count, self.HISTORY_DYNAMIC_COUNT, limit_count)
        self.logger.debug("[CACHE_DEBUG] Calculation details: min(%d - %d, %d - %d) = min(%d, %d) = %d", 
                         limit_count, self.HISTORY_DYNAMIC_COUNT, total_count, self.HISTORY_DYNAMIC_COUNT,
                         limit_count - self.HISTORY_DYNAMIC_COUNT, total_count - self.HISTORY_DYNAMIC_COUNT, stable_count)
        
        # Case 2: No stable messages to cache
        if stable_count <= 0:
            self.logger.warning("[CACHE_DEBUG] CASE 2: No stable messages (stable_count=%d <= 0), using direct fetch", stable_count)
            self.logger.debug("[CACHE_DEBUG] Reason: All messages would be in dynamic portion, no benefit from caching")
            return self._fetch_history_direct(session_uuid, limit_count)
        
        # Case 3: Valid caching scenario - proceed with incremental cache
        self.logger.info("[CACHE_DEBUG] CASE 3: Valid caching scenario - proceeding with incremental cache")
        self.logger.debug("[CACHE_DEBUG] Cache efficiency potential: %.1f%% (stable=%d, total=%d)", 
                         (stable_count / limit_count) * 100, stable_count, limit_count)
        
        # Try to get stable messages from cache
        cache_start = datetime.now()
        stable_messages = self._get_stable_messages_from_cache(session_uuid, stable_count, total_count)
        cache_time = (datetime.now() - cache_start).total_seconds() * 1000
        
        if stable_messages is None:
            # Case 3a: Cache miss - fetch and store
            self.logger.info("[CACHE_DEBUG] CASE 3a: Cache MISS for stable messages (took %.2fms to check)", cache_time)
            db_start = datetime.now()
            stable_messages = self._fetch_and_cache_stable_messages(session_uuid, stable_count, total_count)
            db_time = (datetime.now() - db_start).total_seconds() * 1000
            self.logger.info("[CACHE_DEBUG] Fetched and cached %d stable messages from DB (took %.2fms)", 
                           len(stable_messages), db_time)
        else:
            # Case 3b: Cache hit - use cached data
            self.logger.info("[CACHE_DEBUG] CASE 3b: Cache HIT for stable messages: %d messages (took %.2fms)", 
                           len(stable_messages), cache_time)
            self.logger.debug("[CACHE_DEBUG] Cache performance: %.2fx faster than typical DB query", 
                            15.0 / max(cache_time, 0.1))  # Assume ~15ms typical DB time
        
        # Get dynamic (latest) messages directly from database
        dynamic_start = datetime.now()
        dynamic_messages = self._fetch_dynamic_messages(session_uuid, self.HISTORY_DYNAMIC_COUNT)
        dynamic_time = (datetime.now() - dynamic_start).total_seconds() * 1000
        
        self.logger.info("[CACHE_DEBUG] Fetched %d dynamic messages from DB (took %.2fms)", 
                        len(dynamic_messages), dynamic_time)
        
        # Case 4: Validate message counts before merging
        if len(stable_messages) != stable_count:
            self.logger.warning("[CACHE_DEBUG] CASE 4a: Stable message count mismatch - expected %d, got %d", 
                              stable_count, len(stable_messages))
        
        if len(dynamic_messages) != self.HISTORY_DYNAMIC_COUNT and len(dynamic_messages) != total_count:
            self.logger.warning("[CACHE_DEBUG] CASE 4b: Dynamic message count unexpected - expected %d, got %d (total=%d)", 
                              self.HISTORY_DYNAMIC_COUNT, len(dynamic_messages), total_count)
        
        # Merge stable and dynamic messages
        final_result = stable_messages + dynamic_messages
        
        # Calculate and log final metrics
        cache_hit_rate = len(stable_messages) / len(final_result) * 100 if final_result else 0
        total_time = cache_time + dynamic_time + count_time
        
        self.logger.info("[CACHE_DEBUG] Final result: %d total messages, cache hit rate: %.1f%%, total time: %.2fms", 
                        len(final_result), cache_hit_rate, total_time)
        
        # Case 5: Validate final result integrity
        if len(final_result) > limit_count:
            self.logger.error("[CACHE_DEBUG] CASE 5a: Result overflow - returned %d messages, requested %d", 
                            len(final_result), limit_count)
        elif len(final_result) < min(limit_count, total_count):
            self.logger.warning("[CACHE_DEBUG] CASE 5b: Result underflow - returned %d messages, available %d, requested %d", 
                              len(final_result), total_count, limit_count)
        else:
            self.logger.debug("[CACHE_DEBUG] CASE 5c: Result integrity verified - correct message count")
        
        return final_result
    
    def _fetch_history_direct(self, session_uuid: str, limit_count: int) -> List[Dict[str, str]]:
        """Direct database fetch without caching."""
        
        self.logger.info("[CACHE_DEBUG] Direct fetch initiated: session=%s, limit=%d", 
                        session_uuid[:8] + "...", limit_count)
        self.logger.debug("[CACHE_DEBUG] Reason for direct fetch: cache bypass or not applicable")
        
        # Get total count for offset calculation
        count_start = datetime.now()
        total_count = self.query_one(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s",
            (session_uuid,)
        )["cnt"]
        count_time = (datetime.now() - count_start).total_seconds() * 1000
        
        self.logger.debug("[CACHE_DEBUG] Total messages available: %d (count query: %.2fms)", 
                        total_count, count_time)
        
        # Calculate offset and validate parameters
        offset = max(0, total_count - limit_count)
        effective_limit = min(limit_count, total_count)
        
        self.logger.debug("[CACHE_DEBUG] Query parameters: offset=%d, effective_limit=%d", 
                        offset, effective_limit)
        
        # Validate query logic
        if total_count == 0:
            self.logger.warning("[CACHE_DEBUG] CASE A: No messages in session - returning empty list")
            return []
        
        if limit_count > total_count:
            self.logger.info("[CACHE_DEBUG] CASE B: Requested more messages (%d) than available (%d)", 
                           limit_count, total_count)
        
        if offset > 0:
            self.logger.debug("[CACHE_DEBUG] CASE C: Using offset %d to get last %d of %d messages", 
                            offset, effective_limit, total_count)
        else:
            self.logger.debug("[CACHE_DEBUG] CASE D: Fetching all available messages (no offset needed)")
        
        # Execute main query
        query_start = datetime.now()
        try:
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
                (session_uuid, offset, effective_limit)
            )
            query_time = (datetime.now() - query_start).total_seconds() * 1000
            
            self.logger.info("[CACHE_DEBUG] Direct fetch completed: %d messages in %.2fms", 
                           len(rows), query_time)
            
            # Validate query results
            if len(rows) != effective_limit and total_count >= effective_limit:
                self.logger.warning("[CACHE_DEBUG] Query result mismatch: expected %d, got %d", 
                                  effective_limit, len(rows))
            
        except Exception as e:
            self.logger.error("[CACHE_DEBUG] CASE E: Direct fetch query failed - %s", e)
            raise
        
        # Transform results
        transform_start = datetime.now()
        messages = [{"role": r["role"], "content": r["content"]} for r in rows]
        transform_time = (datetime.now() - transform_start).total_seconds() * 1000
        
        # Validate message structure
        invalid_messages = 0
        for i, msg in enumerate(messages[:5]):  # Check first 5
            if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                invalid_messages += 1
                self.logger.error("[CACHE_DEBUG] Invalid message structure at index %d: %s", i, msg)
        
        if invalid_messages > 0:
            self.logger.error("[CACHE_DEBUG] Found %d invalid messages in direct fetch result", invalid_messages)
        
        # Log performance comparison
        total_time = count_time + query_time + transform_time
        estimated_cache_time = 2.0  # Estimated cache lookup time
        
        self.logger.debug("[CACHE_DEBUG] Direct fetch performance: %.2fms total (%.2fx slower than estimated cache)", 
                        total_time, total_time / estimated_cache_time)
        
        # Log content statistics
        if messages:
            total_content = sum(len(msg["content"]) for msg in messages)
            role_distribution = {}
            for msg in messages:
                role = msg.get("role", "unknown")
                role_distribution[role] = role_distribution.get(role, 0) + 1
            
            self.logger.debug("[CACHE_DEBUG] Direct fetch stats: %d chars total, roles: %s", 
                            total_content, role_distribution)
        
        return messages
    
    def _create_stable_signature(self, session_uuid: str, stable_count: int, total_count: int) -> str:
        """Create signature for stable messages cache key."""
        return self.utils.create_content_signature(
            session_uuid, stable_count, total_count,
            prefix="stable",
            length=16
        )
    
    def _get_stable_messages_from_cache(self, session_uuid: str, stable_count: int, total_count: int) -> Optional[List[Dict[str, str]]]:
        """Get stable messages from cache."""
        try:
            signature = self._create_stable_signature(session_uuid, stable_count, total_count)
            tenant = f"history_stable"
            
            self.logger.debug("[CACHE_DEBUG] Cache lookup: tenant=%s, signature=%s", tenant, signature)
            self.logger.debug("[CACHE_DEBUG] Signature components: session=%s, stable=%d, total=%d", 
                            session_uuid[:8] + "...", stable_count, total_count)
            
            cache_lookup_start = datetime.now()
            cached_data = self.cache_manager.get_cache_by_signature(tenant, signature)
            lookup_time = (datetime.now() - cache_lookup_start).total_seconds() * 1000
            
            # Case A: No cached data found
            if not cached_data:
                self.logger.info("[CACHE_DEBUG] CASE A: Cache miss - no data found for signature %s (lookup: %.2fms)", 
                               signature, lookup_time)
                return None
            
            # Case B: Cached data exists but missing text field
            if "text" not in cached_data:
                self.logger.warning("[CACHE_DEBUG] CASE B: Cache data corrupted - missing 'text' field in cached_data")
                self.logger.debug("[CACHE_DEBUG] Available fields: %s", list(cached_data.keys()))
                return None
            
            # Case C: Cached data with text field - attempt to parse
            try:
                parse_start = datetime.now()
                messages = json.loads(cached_data["text"])
                parse_time = (datetime.now() - parse_start).total_seconds() * 1000
                
                # Validate parsed data structure
                if not isinstance(messages, list):
                    self.logger.error("[CACHE_DEBUG] CASE C1: Cache data invalid - text field is not a list, got %s", 
                                    type(messages).__name__)
                    return None
                
                # Validate message count
                if len(messages) != stable_count:
                    self.logger.warning("[CACHE_DEBUG] CASE C2: Cache data stale - expected %d messages, got %d", 
                                      stable_count, len(messages))
                    self.logger.debug("[CACHE_DEBUG] This might indicate the cache boundary has shifted")
                    return None
                
                # Validate message structure
                for i, msg in enumerate(messages[:3]):  # Check first 3 messages
                    if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                        self.logger.error("[CACHE_DEBUG] CASE C3: Cache data malformed - message %d missing required fields", i)
                        self.logger.debug("[CACHE_DEBUG] Message structure: %s", msg)
                        return None
                
                # Case C4: Valid cached data
                cache_age = datetime.now().timestamp() - cached_data.get("created_at", 0)
                self.logger.info("[CACHE_DEBUG] CASE C4: Cache hit! Retrieved %d valid messages (age: %.1f hours, parse: %.2fms)", 
                               len(messages), cache_age / 3600, parse_time)
                
                # Log cache freshness status
                ttl_remaining = self.HISTORY_CACHE_TTL - cache_age
                if ttl_remaining < 3600:  # Less than 1 hour remaining
                    self.logger.warning("[CACHE_DEBUG] Cache entry expires soon: %.1f hours remaining", ttl_remaining / 3600)
                else:
                    self.logger.debug("[CACHE_DEBUG] Cache entry is fresh: %.1f hours remaining", ttl_remaining / 3600)
                
                return messages
                
            except json.JSONDecodeError as e:
                self.logger.error("[CACHE_DEBUG] CASE C5: Cache data corrupted - JSON decode error: %s", e)
                self.logger.debug("[CACHE_DEBUG] Raw cached text: %s", cached_data["text"][:200] + "...")
                return None
            
        except Exception as e:
            self.logger.error("[CACHE_DEBUG] CASE D: Cache retrieval failed with exception: %s", e)
            self.logger.debug("[CACHE_DEBUG] Exception type: %s", type(e).__name__)
            return None
    
    def _fetch_and_cache_stable_messages(self, session_uuid: str, stable_count: int, total_count: int) -> List[Dict[str, str]]:
        """Fetch stable messages from database and cache them."""
        
        self.logger.info("[CACHE_DEBUG] Fetching stable messages from DB: stable_count=%d, total_count=%d", 
                        stable_count, total_count)
        
        # Calculate database query parameters
        offset = max(0, total_count - stable_count - self.HISTORY_DYNAMIC_COUNT)
        
        self.logger.debug("[CACHE_DEBUG] DB query parameters: OFFSET=%d, LIMIT=%d", offset, stable_count)
        self.logger.debug("[CACHE_DEBUG] Query logic: offset = max(0, %d - %d - %d) = max(0, %d) = %d", 
                         total_count, stable_count, self.HISTORY_DYNAMIC_COUNT, 
                         total_count - stable_count - self.HISTORY_DYNAMIC_COUNT, offset)
        
        # Execute database query
        db_start = datetime.now()
        try:
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
                (session_uuid, offset, stable_count)
            )
            db_time = (datetime.now() - db_start).total_seconds() * 1000
            
            # Case A: Successful database query
            self.logger.info("[CACHE_DEBUG] CASE A: DB query successful - fetched %d rows in %.2fms", 
                           len(rows), db_time)
            
            # Validate database results
            if len(rows) != stable_count and len(rows) < total_count:
                self.logger.warning("[CACHE_DEBUG] DB result count mismatch - expected %d, got %d (total available: %d)", 
                                  stable_count, len(rows), total_count)
                
        except Exception as e:
            self.logger.error("[CACHE_DEBUG] CASE B: DB query failed - %s", e)
            raise  # Re-raise to maintain original error handling
        
        # Transform database rows to message format
        transform_start = datetime.now()
        messages = [{"role": r["role"], "content": r["content"]} for r in rows]
        transform_time = (datetime.now() - transform_start).total_seconds() * 1000
        
        self.logger.debug("[CACHE_DEBUG] Transformed %d DB rows to message format in %.2fms", 
                        len(messages), transform_time)
        
        # Validate message content
        for i, msg in enumerate(messages[:3]):  # Check first 3 messages
            if not msg["content"] or len(msg["content"]) == 0:
                self.logger.warning("[CACHE_DEBUG] Message %d has empty content", i)
        
        # Calculate total content size for caching metrics
        total_content_size = sum(len(msg["content"]) for msg in messages)
        self.logger.debug("[CACHE_DEBUG] Total content size: %d characters (avg: %.1f per message)", 
                        total_content_size, total_content_size / len(messages) if messages else 0)
        
        # Cache the stable messages
        try:
            signature = self._create_stable_signature(session_uuid, stable_count, total_count)
            tenant = f"history_stable"
            user = session_uuid  # Use session as user for cache isolation
            
            self.logger.debug("[CACHE_DEBUG] Preparing cache storage: tenant=%s, user=%s, signature=%s, ttl=%ds", 
                            tenant, user[:8] + "...", signature, self.HISTORY_CACHE_TTL)
            
            # Serialize message data
            serialize_start = datetime.now()
            serialized_data = json.dumps(messages, ensure_ascii=False)
            serialize_time = (datetime.now() - serialize_start).total_seconds() * 1000
            
            self.logger.debug("[CACHE_DEBUG] Serialized %d messages to JSON (%d bytes) in %.2fms", 
                            len(messages), len(serialized_data), serialize_time)
            
            # Store in cache
            cache_start = datetime.now()
            cache_key = self.cache_manager.put_cache(
                tenant=tenant,
                user=user,
                key_signature=signature,
                text=serialized_data,
                ttl_seconds=self.HISTORY_CACHE_TTL
            )
            cache_time = (datetime.now() - cache_start).total_seconds() * 1000
            
            # Case C: Successful cache storage
            self.logger.info("[CACHE_DEBUG] CASE C: Successfully cached %d stable messages in %.2fms (key: %s)", 
                           len(messages), cache_time, cache_key)
            
            # Log cache efficiency metrics
            total_operation_time = db_time + transform_time + serialize_time + cache_time
            self.logger.debug("[CACHE_DEBUG] Operation breakdown: DB=%.2fms, transform=%.2fms, serialize=%.2fms, cache=%.2fms, total=%.2fms", 
                            db_time, transform_time, serialize_time, cache_time, total_operation_time)
            
        except Exception as e:
            # Case D: Cache storage failed
            self.logger.error("[CACHE_DEBUG] CASE D: Failed to cache stable messages: %s", e)
            self.logger.warning("[CACHE_DEBUG] Continuing without caching - system will work but without performance benefits")
            # Continue without caching - this is fault-tolerant behavior
        
        return messages
    
    def _fetch_dynamic_messages(self, session_uuid: str, count: int) -> List[Dict[str, str]]:
        """Fetch the most recent messages (dynamic part)."""
        
        self.logger.debug("[CACHE_DEBUG] Fetching dynamic messages: session=%s, count=%d", 
                        session_uuid[:8] + "...", count)
        
        # Execute query for most recent messages
        query_start = datetime.now()
        try:
            rows = self.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
                (session_uuid, count)
            )
            query_time = (datetime.now() - query_start).total_seconds() * 1000
            
            # Case A: Successful query
            self.logger.debug("[CACHE_DEBUG] CASE A: Dynamic query successful - fetched %d rows in %.2fms", 
                            len(rows), query_time)
            
            # Validate result count
            if len(rows) < count:
                self.logger.info("[CACHE_DEBUG] Fewer dynamic messages available - requested %d, got %d", 
                               count, len(rows))
                if len(rows) == 0:
                    self.logger.warning("[CACHE_DEBUG] No dynamic messages found - session might be empty")
            elif len(rows) == count:
                self.logger.debug("[CACHE_DEBUG] Exact dynamic message count retrieved")
            
        except Exception as e:
            self.logger.error("[CACHE_DEBUG] CASE B: Dynamic query failed - %s", e)
            raise  # Re-raise to maintain error handling
        
        # Reverse to maintain chronological order (query was DESC for recent messages)
        reverse_start = datetime.now()
        messages = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        reverse_time = (datetime.now() - reverse_start).total_seconds() * 1000
        
        self.logger.debug("[CACHE_DEBUG] Reversed %d messages to chronological order in %.2fms", 
                        len(messages), reverse_time)
        
        # Validate message content and structure
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                self.logger.error("[CACHE_DEBUG] CASE C1: Dynamic message %d is not a dict: %s", i, type(msg))
            elif "role" not in msg or "content" not in msg:
                self.logger.error("[CACHE_DEBUG] CASE C2: Dynamic message %d missing required fields: %s", i, list(msg.keys()))
            elif not msg["content"]:
                self.logger.warning("[CACHE_DEBUG] CASE C3: Dynamic message %d has empty content", i)
        
        # Log content statistics
        if messages:
            total_chars = sum(len(msg["content"]) for msg in messages)
            avg_chars = total_chars / len(messages)
            self.logger.debug("[CACHE_DEBUG] Dynamic messages stats: %d messages, %d total chars, %.1f avg chars", 
                            len(messages), total_chars, avg_chars)
            
            # Log role distribution
            role_counts = {}
            for msg in messages:
                role = msg.get("role", "unknown")
                role_counts[role] = role_counts.get(role, 0) + 1
            self.logger.debug("[CACHE_DEBUG] Dynamic message roles: %s", role_counts)
        
        return messages
    
    def invalidate_history_cache(self, session_uuid: str):
        """Invalidate history cache for a session when new messages are added."""
        if not self.cache_manager:
            self.logger.debug("[CACHE_DEBUG] CASE A: No cache manager available, skipping cache invalidation")
            return
            
        try:
            # Clear all stable cache entries for this session
            tenant = f"history_stable"
            
            self.logger.info("[CACHE_DEBUG] Starting cache invalidation for session %s (tenant: %s)", 
                           session_uuid[:8] + "...", tenant)
            
            # Check cache status before invalidation
            pre_invalidation_start = datetime.now()
            try:
                cache_stats = self.cache_manager.get_cache_stats(tenant)
                pre_entries = cache_stats.get("tenant_documents", "unknown")
                self.logger.debug("[CACHE_DEBUG] Pre-invalidation: %s cache entries exist", pre_entries)
            except Exception as e:
                self.logger.warning("[CACHE_DEBUG] Could not get pre-invalidation stats: %s", e)
                pre_entries = "unknown"
            
            # Perform cache invalidation
            invalidation_start = datetime.now()
            cleared = self.cache_manager.clear_tenant_cache(tenant)
            invalidation_time = (datetime.now() - invalidation_start).total_seconds() * 1000
            
            # Analyze invalidation results
            if cleared > 0:
                self.logger.info("[CACHE_DEBUG] CASE B: Cache invalidation successful - cleared %d entries in %.2fms", 
                               cleared, invalidation_time)
                
                # Calculate invalidation efficiency
                if isinstance(pre_entries, int) and pre_entries > 0:
                    efficiency = (cleared / pre_entries) * 100
                    self.logger.debug("[CACHE_DEBUG] Invalidation efficiency: %.1f%% (%d/%d entries)", 
                                    efficiency, cleared, pre_entries)
                
                # Log cache impact assessment
                if cleared >= 10:
                    self.logger.warning("[CACHE_DEBUG] Large cache invalidation - %d entries cleared, may impact performance temporarily", cleared)
                elif cleared >= 5:
                    self.logger.info("[CACHE_DEBUG] Moderate cache invalidation - %d entries cleared", cleared)
                else:
                    self.logger.debug("[CACHE_DEBUG] Small cache invalidation - %d entries cleared", cleared)
                    
            elif cleared == 0:
                self.logger.info("[CACHE_DEBUG] CASE C: No cache entries to clear (%.2fms) - cache was already empty or clean", 
                               invalidation_time)
                self.logger.debug("[CACHE_DEBUG] This is normal for new sessions or after previous invalidations")
            else:
                self.logger.warning("[CACHE_DEBUG] CASE D: Unexpected invalidation result - cleared=%s", cleared)
            
            # Verify post-invalidation state
            try:
                post_stats = self.cache_manager.get_cache_stats(tenant)
                post_entries = post_stats.get("tenant_documents", "unknown")
                self.logger.debug("[CACHE_DEBUG] Post-invalidation: %s cache entries remain", post_entries)
                
                if isinstance(post_entries, int) and post_entries > 0:
                    self.logger.info("[CACHE_DEBUG] Cache not fully cleared - %d entries remain (other sessions)", post_entries)
            except Exception as e:
                self.logger.debug("[CACHE_DEBUG] Could not verify post-invalidation state: %s", e)
            
            # Log invalidation frequency insight
            current_time = datetime.now().timestamp()
            last_invalidation_key = f"_last_invalidation_{session_uuid[:8]}"
            
            if hasattr(self, '_last_invalidations'):
                last_time = getattr(self, '_last_invalidations', {}).get(last_invalidation_key, 0)
                if last_time > 0:
                    time_since_last = current_time - last_time
                    self.logger.debug("[CACHE_DEBUG] Time since last invalidation: %.1f seconds", time_since_last)
                    
                    if time_since_last < 60:  # Less than 1 minute
                        self.logger.warning("[CACHE_DEBUG] Frequent invalidation detected - %.1f seconds since last", time_since_last)
                    elif time_since_last > 3600:  # More than 1 hour
                        self.logger.debug("[CACHE_DEBUG] Infrequent invalidation - good cache utilization")
            else:
                self._last_invalidations = {}
            
            # Record this invalidation
            self._last_invalidations[last_invalidation_key] = current_time
                
        except Exception as e:
            self.logger.error("[CACHE_DEBUG] CASE E: Cache invalidation failed with exception: %s", e)
            self.logger.debug("[CACHE_DEBUG] Exception type: %s", type(e).__name__)
            self.logger.warning("[CACHE_DEBUG] Cache may be in inconsistent state - monitor for cache misses")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get detailed cache status for debugging purposes."""
        status = {
            "cache_manager_available": self.cache_manager is not None,
            "cache_config": {
                "history_cache_n": self.HISTORY_CACHE_N,
                "history_cache_ttl": self.HISTORY_CACHE_TTL,
                "dynamic_count": self.HISTORY_DYNAMIC_COUNT
            },
            "cache_health": None,
            "cache_stats": None
        }
        
        if self.cache_manager:
            try:
                # Check cache health
                status["cache_health"] = self.cache_manager.health_check()
                
                # Get cache statistics
                status["cache_stats"] = self.cache_manager.get_cache_stats("history_stable")
                
                self.logger.info("[CACHE_DEBUG] Cache status retrieved successfully")
                
            except Exception as e:
                status["error"] = str(e)
                self.logger.error("[CACHE_DEBUG] Failed to get cache status: %s", e)
        
        return status
    
    def log_cache_summary(self, session_uuid: str = None):
        """Log a summary of cache status and performance for debugging."""
        if not self.cache_manager:
            self.logger.info("[CACHE_SUMMARY] Cache not available - running without cache")
            return
        
        try:
            status = self.get_cache_status()
            
            self.logger.info("[CACHE_SUMMARY] " + "="*50)
            self.logger.info("[CACHE_SUMMARY] Incremental Cache Status Report")
            self.logger.info("[CACHE_SUMMARY] Configuration: N=%d, TTL=%dh, Dynamic=%d", 
                           self.HISTORY_CACHE_N, self.HISTORY_CACHE_TTL // 3600, self.HISTORY_DYNAMIC_COUNT)
            
            if status.get("cache_health"):
                health = status["cache_health"]
                self.logger.info("[CACHE_SUMMARY] Redis Connected: %s", health.get("redis_connected", False))
                self.logger.info("[CACHE_SUMMARY] Index Exists: %s", health.get("index_exists", False))
            
            if status.get("cache_stats"):
                stats = status["cache_stats"]
                self.logger.info("[CACHE_SUMMARY] Cache Entries: %s", stats.get("total_documents", "N/A"))
                if "tenant_documents" in stats:
                    self.logger.info("[CACHE_SUMMARY] History Cache Entries: %s", stats["tenant_documents"])
            
            # Calculate expected performance benefits
            stable_ratio = (self.HISTORY_CACHE_N - self.HISTORY_DYNAMIC_COUNT) / self.HISTORY_CACHE_N
            self.logger.info("[CACHE_SUMMARY] Expected Cache Hit Rate: %.1f%%", stable_ratio * 100)
            
            if session_uuid:
                self.logger.info("[CACHE_SUMMARY] Monitoring session: %s", session_uuid)
            
            self.logger.info("[CACHE_SUMMARY] " + "="*50)
            
        except Exception as e:
            self.logger.error("[CACHE_SUMMARY] Failed to generate cache summary: %s", e)
