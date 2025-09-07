'''
Universal cache layer for Poy Мой Мир bot.
Switches between Redis / YDB / CSV seamlessly.
Expose:
    • cache  – selected backend instance
    • CacheBackend subclasses (CsvCache, RedisCache, YdbCache)
    • CacheUnavailable – exception to signal temporary outage
    • save_message_to_cache(session_id, user_id, role, content)
    • flush_cache_to_pg(session_id, pg_execute_fn)
https://chatgpt.com/g/g-p-6816171194d081919f737fdb4642dfa8-poymoymirtech/c/6838074f-85c8-8007-b19d-ad8db14f94ba
'''
from __future__ import annotations

import json
import uuid
import os
import csv
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CacheUnavailable(RuntimeError):
    """Raised by implementations when the storage is temporarily inaccessible."""


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class CacheBackend(ABC):
    @abstractmethod
    def insert(self, msg: Dict[str, Any]) -> None: ...

    @abstractmethod
    def count(self, session_id: str) -> int: ...

    @abstractmethod
    def fetch_all(self, session_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def delete_session(self, session_id: str) -> None: ...

    # ---------------- factory & selection ----------------
    @staticmethod
    def from_env() -> "CacheBackend":
        mapping = {
            "redis": RedisCache,
            "ydb": YdbCache,
            "csv": CsvCache,
        }
        choice = os.getenv("CACHE_BACKEND", "csv").lower()
        cls = mapping.get(choice, CsvCache)
        try:
            backend = cls.from_env()
            logger.info("Cache backend selected: %s", backend.__class__.__name__)
            return backend
        except CacheUnavailable as exc:
            logger.error("Cache '%s' unavailable – falling back to CsvCache: %s", choice, exc)
            return CsvCache.from_env()


# ---------------------------------------------------------------------------
# CSV implementation (always works, fallback)
# ---------------------------------------------------------------------------

class CsvCache(CacheBackend):
    def __init__(self, folder: str, prefix: str):
        self.folder = folder
        self.prefix = prefix
        os.makedirs(folder, exist_ok=True)
        logger.debug("CsvCache folder: %s", folder)

    @classmethod
    def from_env(cls):
        folder = os.getenv("csv_cache_dir", "/tmp/chat_cache")
        prefix = (
            os.getenv("yc_function_name")
            or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
            or os.getenv("FUNCTION_NAME")
            or "function"
        )
        return cls(folder, prefix)

    # utilities
    def _path(self, sid: str) -> str:
        return os.path.join(self.folder, f"{self.prefix}_{sid}.csv")

    def _ensure_header(self, path: str):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    ["id", "session_id", "user_id", "role", "content", "created_at"]
                )

    # interface impl
    def insert(self, msg: Dict[str, Any]) -> None:
        path = self._path(msg["session_id"])
        self._ensure_header(path)
        row = msg.copy()
        if isinstance(row["created_at"], datetime):
            row["created_at"] = (
                row["created_at"].astimezone(timezone.utc).replace(microsecond=0).isoformat() + "Z"
            )
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row.values())

    def count(self, session_id: str) -> int:
        path = self._path(session_id)
        if not os.path.exists(path):
            return 0
        with open(path, newline="", encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)

    def fetch_all(self, session_id: str) -> List[Dict[str, Any]]:
        path = self._path(session_id)
        if not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            out: List[Dict[str, Any]] = []
            for row in reader:
                ts = row.get("created_at")
                if ts:
                    row["created_at"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                out.append(row)
            return out

    def delete_session(self, session_id: str) -> None:
        try:
            os.remove(self._path(session_id))
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------

class RedisCache(CacheBackend):
    def __init__(self, client):
        self.r = client

    @classmethod
    def from_env(cls):
        try:
            import redis

            client = redis.Redis(
                host=os.getenv("redis_host", "localhost"),
                port=int(os.getenv("redis_port", 6379)),
                db=int(os.getenv("redis_db", 0)),
                password=os.getenv("redis_password"),
                decode_responses=True,
            )
            client.ping()
            return cls(client)
        except Exception as exc:
            raise CacheUnavailable(exc)

    def _key(self, sid: str) -> str:
        return f"session:{sid}:messages"

    def insert(self, msg: Dict[str, Any]) -> None:
        try:
            self.r.rpush(self._key(msg["session_id"]), json.dumps(msg, default=str))
        except Exception as exc:
            raise CacheUnavailable(exc)

    def count(self, session_id: str) -> int:
        try:
            return int(self.r.llen(self._key(session_id)))
        except Exception as exc:
            raise CacheUnavailable(exc)

    def fetch_all(self, session_id: str) -> List[Dict[str, Any]]:
        try:
            raw = self.r.lrange(self._key(session_id), 0, -1)
            return [json.loads(x) for x in raw]
        except Exception as exc:
            raise CacheUnavailable(exc)

    def delete_session(self, session_id: str) -> None:
        try:
            self.r.delete(self._key(session_id))
        except Exception as exc:
            raise CacheUnavailable(exc)


# ---------------------------------------------------------------------------
# YDB stub (extend later)
# ---------------------------------------------------------------------------

class YdbCache(CacheBackend):
    @classmethod
    def from_env(cls):
        raise CacheUnavailable("YDB cache not implemented yet")

    def insert(self, msg): ...
    def count(self, session_id): ...
    def fetch_all(self, session_id): ...
    def delete_session(self, session_id): ...


# ---------------------------------------------------------------------------
# Helper functions used by main bot code
# ---------------------------------------------------------------------------

cache: CacheBackend = CacheBackend.from_env()


def save_message_to_cache(session_id: str, user_id: str, role: str, content: str) -> None:
    """Insert message into selected cache backend, falling back to CSV on error."""
    global cache
    msg = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        cache.insert(msg)
    except CacheUnavailable as exc:
        logger.error("Cache insert failed, switching to CsvCache: %s", exc)
        cache = CsvCache.from_env()
        cache.insert(msg)


def flush_cache_to_pg(session_id: str, pg_execute_fn) -> None:
    """Flush cached messages to Postgres via provided execute_values wrapper.

    Parameters
    ----------
    session_id : str
        Session UUID
    pg_execute_fn : Callable[[List[tuple]], None]
        Function that receives list-of-tuples and writes into PG.
    """
    try:
        rows = cache.fetch_all(session_id)
    except CacheUnavailable as exc:
        logger.warning("Cache fetch failed, using CsvCache fallback: %s", exc)
        cache = CsvCache.from_env()
        rows = cache.fetch_all(session_id)

    if not rows:
        return

    pg_execute_fn([
        (
            r["id"],
            r["session_id"],
            r["user_id"],
            r["role"],
            r["content"],
            r["created_at"],
        )
        for r in rows
    ])
    cache.delete_session(session_id)
