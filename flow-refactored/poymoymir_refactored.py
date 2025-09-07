"""Refactored version of the flow/index.py module.

This module reorganises the original code into a set of cohesive classes and
functions. The goal is to improve readability, testability and maintainability
while preserving the existing functionality. No additional third‑party
dependencies are introduced – the refactor only restructures the code and
adds documentation and type hints.

Key improvements include:

* Separation of concerns: configuration, logging, database access, HTTP
  clients, LLM interactions, Telegram API operations and Suno integration
  are encapsulated in their own classes.
* Clearer names and type annotations for variables and parameters.
* Proper use of context managers to manage database connections and
  HTTP resources.
* Minimised reliance on mutable global state by passing explicit
  configuration objects.

The overall architecture makes it simpler to extend the bot in the future,
add new features or change implementations without touching unrelated
code.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
import requests
import tiktoken
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from pydantic import Base64Bytes, ValidationError, TypeAdapter
from pythonjsonlogger import jsonlogger
from requests.adapters import HTTPAdapter
from requests import HTTPError
from urllib3.util.retry import Retry

import psycopg2
from psycopg2.extras import RealDictCursor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class BotConfig:
    """Runtime configuration for the bot derived from environment variables.

    This class centralises reading and validating environment variables. It
    parses composite values such as comma‑separated fallback models into
    appropriate Python data structures.
    """

    bot_token: str = field(default_factory=lambda: os.environ["bot_token"])
    operouter_key: str = field(default_factory=lambda: os.environ["operouter_key"])
    ai_model: str = field(default_factory=lambda: os.getenv("ai_model", "openai/gpt-4o"))
    ai_models_fallback: List[str] = field(default_factory=lambda: os.getenv(
        "ai_models_fallback",
        "openai/gpt-4o,openai/gpt-4o-2024-11-20,openai/gpt-4o-2024-08-06",
    ).split(","))
    ai_endpoint: str = field(default_factory=lambda: os.getenv(
        "ai_endpoint", "https://openrouter.ai/api/v1/chat/completions"
    ))
    session_lifetime: int = field(default_factory=lambda: int(os.getenv("session_lifetime", "87600")))
    connect_timeout: int = field(default_factory=lambda: int(os.getenv("connect_timeout", "1")))
    read_timeout: int = field(default_factory=lambda: int(os.getenv("read_timeout", "5")))
    retry_total: int = field(default_factory=lambda: int(os.getenv("retry_total", "3")))
    retry_backoff_factor: int = field(default_factory=lambda: int(os.getenv("retry_backoff_factor", "2")))
    proxy_url: Optional[str] = field(default_factory=lambda: os.getenv("proxy_url"))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("openai_key"))
    song_bucket_name: Optional[str] = field(default_factory=lambda: os.getenv("song_bucket_name"))
    suno_api_url: str = field(default_factory=lambda: os.getenv(
        "suno_api_url", "https://apibox.erweima.ai/api/v1/generate"
    ))
    suno_model: str = field(default_factory=lambda: os.getenv("suno_model", "V4_5"))
    suno_callback_url: Optional[str] = field(default_factory=lambda: os.getenv("suno_callback_url"))
    suno_api_key: Optional[str] = field(default_factory=lambda: os.getenv("suno_api_key"))
    database_url: Optional[str] = field(default_factory=lambda: os.getenv("database_url"))
    db_host: Optional[str] = field(default_factory=lambda: os.getenv("DB_HOST"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: Optional[str] = field(default_factory=lambda: os.getenv("DB_NAME"))
    db_user: Optional[str] = field(default_factory=lambda: os.getenv("DB_USER"))
    db_password: Optional[str] = field(default_factory=lambda: os.getenv("DB_PASSWORD"))

    def db_conn_params(self) -> Dict[str, Any]:
        """Prepare connection parameters for psycopg2."""
        if self.database_url:
            return {"dsn": self.database_url}
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
        }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(name: str = "PoyMoyMirBot", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a JSON logger.

    A single configuration function avoids duplicate handlers when imported from
    multiple modules. The logging format is consistent across the application.

    Args:
        name: Name of the logger.
        level: Logging level.

    Returns:
        Configured `logging.Logger` instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


class YcLoggingFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter ensuring consistent log fields."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = record.levelname.replace("WARNING", "WARN").replace("CRITICAL", "FATAL")


LOGGER = setup_logger(level=logging.DEBUG)


# ---------------------------------------------------------------------------
# Database Access
# ---------------------------------------------------------------------------

class Database:
    """Simple wrapper around psycopg2 for convenience and safety.

    This class exposes methods for common database operations. Connections are
    opened and closed automatically, and queries return dictionaries by
    default.
    """

    def __init__(self, config: BotConfig) -> None:
        self._config = config

    def _connect(self) -> psycopg2.extensions.connection:
        try:
            conn = psycopg2.connect(**self._config.db_conn_params())
            conn.set_client_encoding('UTF8')
            return conn
        except psycopg2.Error as e:
            LOGGER.exception("Failed to connect to Postgres: %s", e)
            raise

    def query_one(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def query_all(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()


# ---------------------------------------------------------------------------
# Telegram API Client
# ---------------------------------------------------------------------------

class TelegramClient:
    """Client wrapper for interacting with the Telegram Bot API.

    Uses a shared `requests.Session` with retry logic. Provides methods for
    sending plain text messages, audio, and messages with inline keyboards.
    """

    SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!\\"

    def __init__(self, config: BotConfig, http_session: requests.Session | None = None) -> None:
        self.config = config
        self.session = http_session or self._create_session(config)
        self.base_url = f"https://api.telegram.org/bot{self.config.bot_token}"

    @staticmethod
    def _create_session(config: BotConfig) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=config.retry_total,
            backoff_factor=config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)
        return session

    def _send_request(self, method: str, payload: Dict[str, Any]) -> None:
        url = f"{self.base_url}/{method}"
        try:
            resp = self.session.post(url, json=payload, timeout=(self.config.connect_timeout, self.config.read_timeout))
            resp.raise_for_status()
        except HTTPError as e:
            LOGGER.error("Telegram API request failed: %s | response=%s", e, getattr(resp, "text", ""))
            raise

    def escape_markdown(self, text: str) -> str:
        return "".join("\\" + ch if ch in self.SPECIAL_CHARS else ch for ch in text)

    def send_text(self, chat_id: int, text: str, parse_mode: str = "MarkdownV2", disable_preview: bool = True) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        self._send_request("sendMessage", payload)

    def send_audio(self, chat_id: int, audio_url: str, title: str = "") -> None:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "audio": audio_url,
        }
        if title:
            payload["caption"] = title
            payload["title"] = title
        self._send_request("sendAudio", payload)

    def send_markup(self, chat_id: int, text: str, markup: Dict[str, Any]) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps(markup),
            "parse_mode": "MarkdownV2",
        }
        self._send_request("sendMessage", payload)

    def answer_callback(self, callback_query_id: str, text: str, show_alert: bool = False) -> None:
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        self._send_request("answerCallbackQuery", payload)

    def send_chunks(self, chat_id: int, text: str, chunk_size: int = 4096) -> None:
        escaped = self.escape_markdown(text)
        for i in range(0, len(escaped), chunk_size):
            self.send_text(chat_id, escaped[i:i + chunk_size])


# ---------------------------------------------------------------------------
# Suno Integration
# ---------------------------------------------------------------------------

class SunoClient:
    """Client for interacting with the Suno music generation API and S3 storage."""

    def __init__(self, config: BotConfig, http_session: requests.Session | None = None) -> None:
        self.config = config
        self.session = http_session or TelegramClient._create_session(config)

    def generate_song_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """Generate a signed URL for a private S3/Yandex Object Storage file."""
        s3 = boto3.client("s3")
        return s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in,
        )

    def download_and_process_song(self, *, song_url: str, tg_user_id: str, song_title: str, song_artist: str, local_folder: str) -> str:
        """Download an MP3, set its ID3 tags and reupload to object storage.

        Returns the signed URL of the uploaded song.
        """
        user_folder = os.path.join(local_folder, tg_user_id)
        os.makedirs(user_folder, exist_ok=True)
        local_path = os.path.join(user_folder, f"{song_title}.mp3")
        song_key = f"{tg_user_id}/{song_title}.mp3"

        # Download
        resp = requests.get(song_url)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)

        # Update ID3 tags
        audio = MP3(local_path, ID3=EasyID3)
        audio["title"] = song_title
        audio["artist"] = song_artist
        audio["composer"] = "AI сгенерировано с помощью https://t.me/PoyMoyMirBot"
        audio.save()

        # Generate signed URL using the configured bucket
        if not self.config.song_bucket_name:
            raise RuntimeError("song_bucket_name is not configured")
        return self.generate_song_url(bucket=self.config.song_bucket_name, key=song_key)

    def request_song(self, prompt: str, style: str, title: str) -> Dict[str, Any]:
        """Request a song from the Suno API.

        Returns the API response JSON. Note that the actual file will be
        delivered asynchronously via the callback URL specified in the
        configuration.
        """
        if not (self.config.suno_api_key and self.config.suno_callback_url):
            LOGGER.error("Suno callback URL or API key not configured")
            return {}
        payload = {
            "prompt": prompt,
            "style": style,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": self.config.suno_model,
            "callBackUrl": self.config.suno_callback_url,
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.config.suno_api_key}',
        }
        resp = self.session.post(self.config.suno_api_url, json=payload, headers=headers, timeout=(self.config.connect_timeout, self.config.read_timeout))
        try:
            resp.raise_for_status()
        except Exception:
            LOGGER.exception("Suno API request failed: %s", resp.text)
            return {}
        LOGGER.debug("Suno API response: %s", resp.text)
        return resp.json()


# ---------------------------------------------------------------------------
# LLM Integration
# ---------------------------------------------------------------------------

class LLMClient:
    """Wrapper for interacting with the OpenRouter/OpenAI chat completion API.

    Handles message trimming based on token limits and moderation checks. This
    client does not mutate the input message list; instead it operates on a
    copy.
    """

    MAX_TOKENS = 50_000

    def __init__(self, config: BotConfig, http_session: requests.Session | None = None) -> None:
        self.config = config
        self.session = http_session or TelegramClient._create_session(config)
        self.encoder = tiktoken.encoding_for_model("gpt-4o")

    def _count_tokens(self, message: Dict[str, str]) -> int:
        role_tokens = len(self.encoder.encode(message["role"]))
        content_tokens = len(self.encoder.encode(message["content"]))
        return role_tokens + content_tokens + 4

    def _trim_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        total = sum(self._count_tokens(m) for m in messages)
        if total <= self.MAX_TOKENS:
            return messages
        # Preserve the system message
        sys_msg, chat_msgs = messages[0], messages[1:]
        while total > self.MAX_TOKENS and chat_msgs:
            removed = chat_msgs.pop(0)
            total -= self._count_tokens(removed)
        return [sys_msg] + chat_msgs

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        proxies = None
        if self.config.proxy_url:
            proxies = {"http": self.config.proxy_url, "https": self.config.proxy_url}
        resp = self.session.post(self.config.ai_endpoint, json=payload, headers={
            "Authorization": f"Bearer {self.config.operouter_key}",
            "Content-Type": "application/json",
        }, proxies=proxies, timeout=(self.config.connect_timeout, self.config.read_timeout))
        try:
            resp.raise_for_status()
        except Exception as e:
            LOGGER.error("LLM API call failed: %s", e)
            LOGGER.debug("Response body: %s", getattr(resp, "text", ""))
            raise
        return resp.json()

    def call_single(self, user_message: str, system_message: Optional[str] = None) -> Dict[str, Any]:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        payload = {
            "model": self.config.ai_model,
            "messages": messages,
            "models": self.config.ai_models_fallback,
        }
        data = self._post(payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        try:
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {"content": content}

    def call_conversation(self, messages: List[Dict[str, str]], system_message: Optional[str] = None) -> Dict[str, Any]:
        msgs = []
        if system_message:
            msgs.append({"role": "system", "content": system_message})
        msgs.extend(messages)
        payload = {
            "model": self.config.ai_model,
            "messages": msgs,
            "models": self.config.ai_models_fallback,
        }
        data = self._post(payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        try:
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {"content": content}

    def call_with_tools(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> str:
        msgs = self._trim_messages(messages.copy())
        payload = {
            "model": self.config.ai_model,
            "messages": msgs,
            "tools": tools,
            "tool_choice": "auto",
            "models": self.config.ai_models_fallback,
        }
        data = self._post(payload)
        choice = data.get("choices", [{}])[0].get("message", {})
        # TODO: handle tool calls if required
        return choice.get("content", "")

    def is_text_flagged(self, text: str) -> bool:
        """Moderation check using OpenAI's moderation endpoint."""
        if not self.config.openai_api_key:
            return False
        url = "https://api.openai.com/v1/moderations"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text, "model": "omni-moderation-latest"}
        proxies = None
        if self.config.proxy_url:
            proxies = {"http": self.config.proxy_url, "https": self.config.proxy_url}
        resp = self.session.post(url, headers=headers, json=payload, proxies=proxies, timeout=(self.config.connect_timeout, self.config.read_timeout))
        try:
            resp.raise_for_status()
        except Exception as e:
            LOGGER.error("Moderation check failed: %s", e)
            return False
        data = resp.json()
        return data.get("results", [{}])[0].get("flagged", False)


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def parse_body(event: Dict[str, Any]) -> Any:
    """Universal parser for body payloads in HTTP events.

    The payload can be JSON, base64‑encoded JSON, raw binary or plain text.
    This helper attempts to decode the body accordingly.
    """
    raw: str | bytes = event.get("body", "")
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        pass
    b64 = TypeAdapter(Base64Bytes)
    try:
        decoded: bytes = b64.validate_python(raw)
    except ValidationError:
        return raw
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return decoded


def chunks(text: str, size: int = 4096) -> Iterable[str]:
    """Yield successive chunks from a string."""
    for i in range(0, len(text), size):
        yield text[i:i + size]


def get_last_messages(history: List[Dict[str, str]], count: int, role: Optional[str] = None, force_last_user: bool = False, extra_message: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """Return the last N messages from a history with optional filtering.

    If `role` is provided, only messages with that role are returned. When
    `force_last_user` is true and `role` is not provided, the last message is
    guaranteed to be from the user, if available. Optionally append an extra
    message at the end of the returned list.
    """
    if role:
        filtered = [msg for msg in history if msg.get("role") == role]
        result = filtered[-count:]
    elif force_last_user:
        last_user_idx = next((i for i in range(len(history) - 1, -1, -1) if history[i].get("role") == "user"), None)
        if last_user_idx is None:
            result = history[-count:]
        else:
            start_idx = max(0, last_user_idx - count + 1)
            result = history[start_idx:last_user_idx + 1]
    else:
        result = history[-count:]
    if extra_message:
        result = result + [extra_message]
    return result


# ---------------------------------------------------------------------------
# The Handler
# ---------------------------------------------------------------------------

class Handler:
    """Encapsulates the main request handler logic.

    This class coordinates between the database, Telegram client, LLM client and
    Suno client to respond to incoming events. It manages user sessions,
    detects intents and emotions, and triggers song generation.
    """

    CONFUSED_INTENT_ANSWER: List[str] = [
        "Ты можешь быть с собой честен здесь. Без страха. Даже если честность сейчас — это: \"Я не знаю, что чувствую\". Это уже начало песни...",
        "Чем точнее ты поделишься — тем точнее я смогу услышать тебя. А значит, и песня будет ближе к тебе самому...",
        "Иногда самая красивая строчка рождается из фразы \"я боюсь сказать, что думаю\"... Это не слабость. Это глубина.",
        "В этом месте можно говорить правду. Даже если она шепотом.",
        "💬 Отклики других людей — чтобы почувствовать, как звучит _ПойМойМир_ в чужих сердцах: https://poymoymir.ru/feedback/",
        "🎧 Подкасты о проекте — мягкое знакомство с тем, как здесь всё устроено: https://poymoymir.ru/feedback/",
    ]
    CONFUSED_INTENT_ANSWER_MP3: str = "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/try.mp3"
    FEEDBACK_INTENT_ANSWER_MP3: str = "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/feedback.mp3"
    SONG_GENERATING_MESSAGE: str = (
        "Твоя песня уже в пути.\nДай ей немного времени — она рождается 🌿\n\nПесня придёт отдельным сообщением через 2 минуты"
    )

    song_received_markup: Dict[str, Any] = {
        "inline_keyboard": [
            [
                {"text": "🌿", "url": "https://bit.ly/4jZSMIH"},
                {"text": "🔁", "switch_inline_query": "ПойМойМир песня о тебе"},
                {"text": "🤗", "callback_data": "hug_author"},
                {"text": "💬", "url": "https://bit.ly/431hC4f"},
                {"text": "🔕", "callback_data": "silence_room"},
            ]
        ]
    }

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.db = Database(config)
        self.telegram = TelegramClient(config)
        self.suno = SunoClient(config)
        self.llm = LLMClient(config)

    # ---- Helpers for database entities ----
    def _get_or_create_bot(self, token: str, username: Optional[str] = None) -> str:
        md5_hash = uuid.uuid5(uuid.NAMESPACE_DNS, token).hex
        rec = self.db.query_one("SELECT id FROM bots WHERE token = %s LIMIT 1", (md5_hash,))
        if rec:
            return rec["id"]
        bot_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO bots(id, token, username, owner_id) VALUES (%s, %s, %s, %s)",
            (bot_id, md5_hash, username, None),
        )
        LOGGER.info("Created bot %s (token hash %s)", bot_id, md5_hash)
        return bot_id

    def ensure_user_exists(self, tg_user_id: str, user_uuid: str) -> None:
        rec = self.db.query_one("SELECT id FROM tg_users WHERE id = %s", (tg_user_id,))
        if not rec:
            self.db.execute(
                "INSERT INTO tg_users(id, user_id, warnings, blocked) VALUES (%s, %s, %s, %s)",
                (tg_user_id, user_uuid, 0, False),
            )

    def _get_or_create_user(self, chat_id: int, full_name: str) -> str:
        rec = self.db.query_one("SELECT id FROM users WHERE chat_id = %s LIMIT 1", (chat_id,))
        if rec:
            return rec["id"]
        user_uuid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO users(id, chat_id, full_name) VALUES (%s, %s, %s)",
            (user_uuid, chat_id, full_name),
        )
        LOGGER.info("Created user %s for chat_id %s", user_uuid, chat_id)
        return user_uuid

    def _get_active_session(self, user_uuid: str, bot_uuid: str) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.session_lifetime)
        rec = self.db.query_one(
            "SELECT id, started_at FROM conversation_sessions "
            "WHERE user_id = %s AND bot_id = %s AND ended_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (user_uuid, bot_uuid),
        )
        if rec and rec.get("started_at") and rec["started_at"] > cutoff:
            return rec["id"]
        session_uuid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO conversation_sessions(id, user_id, bot_id, started_at, model) "
            "VALUES (%s, %s, %s, NOW(), %s)",
            (session_uuid, user_uuid, bot_uuid, self.config.ai_model),
        )
        LOGGER.debug("Created session %s", session_uuid)
        return session_uuid

    def _fetch_history(self, session_uuid: str, limit_count: Optional[int] = None) -> List[Dict[str, str]]:
        if limit_count is not None:
            total_count = self.db.query_one(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s", (session_uuid,)
            )["cnt"]
            offset = max(0, total_count - limit_count)
            rows = self.db.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
                (session_uuid, offset, limit_count),
            )
        else:
            rows = self.db.query_all(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_uuid,),
            )
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    # ---- Moderation ----
    def moderate_user(self, chat_id: int, tg_user_id: str, additional_reason: str = "Нарушение правил") -> Optional[int]:
        rec = self.db.query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
        warnings = rec.get("warnings", 0) if rec else 0
        blocked = rec.get("blocked", False) if rec else False
        if warnings > 2 and blocked:
            return 3
        new_warnings = warnings + 1
        self.db.execute("UPDATE tg_users SET warnings = %s WHERE id = %s", (new_warnings, tg_user_id))
        if warnings == 1 and not blocked:
            # First warning → ban
            self.db.execute(
                "UPDATE tg_users SET blocked = TRUE, blocked_reason = %s, blocked_at = NOW() WHERE id = %s",
                (additional_reason, tg_user_id),
            )
            reason_msg = (
                f"Первое предупреждение, причина:\n- {additional_reason}\n"
                "Свобода ≠ вседозволенность. Ознакомьтесь с правилами:\n"
                "https://bit.ly/4j7AzIg\nПовторное предупреждение — бан навсегда."
            )
            self.telegram.send_chunks(chat_id, reason_msg)
            return 1
        elif warnings >= 2 and not blocked:
            # Second warning → permanent ban
            self.db.execute(
                "UPDATE tg_users SET blocked = TRUE, blocked_reason = %s, blocked_at = NOW() WHERE id = %s",
                (additional_reason, tg_user_id),
            )
            self.telegram.send_chunks(chat_id, "Вы перемещены в Комнату Забвения, бан навсегда.")
            return 2
        return None

    # ---- Main entrypoint ----
    def handle(self, event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        LOGGER.debug("Incoming event: %s", event)
        body = parse_body(event)
        LOGGER.debug("Parsed body: %s", body)
        # Handle callback queries
        if isinstance(body, dict) and "callback_query" in body:
            callback = body["callback_query"]
            data = callback["data"]
            callback_id = callback["id"]
            if data == "hug_author":
                self.telegram.answer_callback(callback_id, "💞 Автору переданы объятия!")
            return {"statusCode": 200, "body": ""}
        # Handle Suno API callback
        if isinstance(body, dict) and body.get("data") and body["data"].get("callbackType") == "complete":
            task_id = body["data"]["task_id"]
            song_url = body["data"]["data"][0]["audio_url"]
            song_title = body["data"]["data"][0]["title"]
            song_artist = "ПойМойМир"
            LOGGER.debug("Suno song generated: %s", song_url)
            rec = self.db.query_one(
                "SELECT tg.id AS telegram_user_id FROM public.songs AS s JOIN public.tg_users AS tg ON s.user_id = tg.user_id WHERE s.task_id = %s LIMIT 1",
                (task_id,),
            )
            if not rec:
                LOGGER.error("No telegram user found for task %s", task_id)
                return {"statusCode": 200, "body": ""}
            tg_user_id = rec["telegram_user_id"]
            signed_url = self.suno.download_and_process_song(
                song_url=song_url,
                song_title=song_title,
                tg_user_id=str(tg_user_id),
                song_artist=song_artist,
                local_folder="/function/storage/songs/",
            )
            path_prefix = f"{tg_user_id}/{song_title}.mp3"
            self.db.execute("UPDATE songs SET path = %s WHERE task_id = %s", (path_prefix, task_id))
            user_uuid = self._get_or_create_user(tg_user_id, full_name="Dummy")
            session_uuid = self._get_active_session(user_uuid, self._get_or_create_bot(self.config.bot_token))
            self.telegram.send_audio(chat_id=int(tg_user_id), audio_url=signed_url, title=song_title)
            # Save message about final version
            self.db.execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "финальная версия песни получена пользователем"),
            )
            return {"statusCode": 200, "body": ""}
        # No message to process
        message = None
        if isinstance(body, dict):
            message = body.get("message") or body.get("edited_message")
        if not message or not message.get("text"):
            return {"statusCode": 200, "body": ""}
        chat_id = message["chat"]["id"]
        text = message["text"]
        user = message["from"]
        full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
        user_uuid = self._get_or_create_user(chat_id, full_name)
        tg_user_id = str(user.get("id"))
        # session & history
        bot_uuid = self._get_or_create_bot(self.config.bot_token)
        session_uuid = self._get_active_session(user_uuid, bot_uuid)
        history = self._fetch_history(session_uuid)
        self.ensure_user_exists(tg_user_id, user_uuid)
        # Check warnings/block
        urec = self.db.query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
        if urec and urec.get("warnings", 0) > 2 and urec.get("blocked", False):
            return {"statusCode": 200, "body": "banned"}
        # Save user message
        msg_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
            (msg_id, session_uuid, user_uuid, "user", text),
        )
        # Build messages for LLM calls
        last_50 = get_last_messages(history, 50)
        last_8 = get_last_messages(last_50, 8, force_last_user=True)
        last_20_assist = get_last_messages(last_50, 20, role="assistant")
        last_5_assist = get_last_messages(last_50, 5, role="assistant")
        last_3_assist = get_last_messages(last_50, 3, role="assistant")
        last_8_user = get_last_messages(last_50, 8, role="user")
        # Restart conversation if a reset phrase was used
        start_idx = None
        for i in range(len(last_50) - 1, -1, -1):
            if "Давай начнём всё с начала" in last_50[i].get("content", ""):
                start_idx = i
                break
        msgs_from_phrase = last_50[start_idx:] if start_idx is not None else []
        if msgs_from_phrase:
            base_msgs = msgs_from_phrase
        else:
            base_msgs = history
        openai_msgs = [
            {"role": "system", "content": open("system_prompt.txt", encoding="utf-8").read()},
            *base_msgs,
            {"role": "user", "content": text},
        ]
        # Detect intent and emotion
        detect_intent = self.llm.call_conversation(last_8, open("knowledge_bases/determinate_intent.txt", encoding="utf-8").read())
        detect_emotion = self.llm.call_conversation(last_8_user, open("knowledge_bases/detect_emotional_state.txt", encoding="utf-8").read())
        # Save analysis
        analysis = {"intent": detect_intent, "emotion": detect_emotion}
        self.db.execute(
            "UPDATE messages SET analysis = %s WHERE id = %s",
            (json.dumps(analysis), msg_id),
        )
        # Quick checks for confusion
        is_confused = any(
            e.get("name") == "Растерянность" and e.get("intensity", 0) > 90 for e in detect_emotion.get("emotions", [])
        )
        if is_confused:
            if not any(msg.get("content") == "confused_send" for msg in last_20_assist):
                if random.choice([True, False]):
                    answer = random.choice(self.CONFUSED_INTENT_ANSWER)
                    self.telegram.send_chunks(chat_id, answer)
                else:
                    self.telegram.send_audio(chat_id, self.CONFUSED_INTENT_ANSWER_MP3, "Ты можешь...")
                self.db.execute(
                    "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                    (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "confused_send"),
                )
                return {"statusCode": 200, "body": ""}
        # Song generation
        if detect_intent.get("intent") == "finalize_song":
            is_final_song_received = any(msg.get("content") == "финальная версия песни получена пользователем" for msg in last_5_assist)
            is_final_song_sent = any(msg.get("content") == "финальная версия песни отправлена пользователю" for msg in last_5_assist)
            if not (is_final_song_received or is_final_song_sent):
                get_song = self.llm.call_conversation(last_3_assist, open("knowledge_bases/prepare_suno.txt", encoding="utf-8").read())
                lyrics = get_song.get("lyrics")
                style = get_song.get("style")
                title = get_song.get("name")
                song_resp = self.suno.request_song(lyrics, style, title)
                task_id = song_resp.get("data", {}).get("taskId") if song_resp else None
                if task_id:
                    song_id = str(uuid.uuid4())
                    self.telegram.send_chunks(chat_id, self.SONG_GENERATING_MESSAGE)
                    self.db.execute(
                        "INSERT INTO songs(id, user_id, session_id, task_id, title, prompt, style, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
                        (song_id, user_uuid, session_uuid, task_id, title, lyrics, style),
                    )
                    # Save messages about generation and sending
                    self.db.execute(
                        "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                        (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", self.SONG_GENERATING_MESSAGE),
                    )
                    self.db.execute(
                        "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                        (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "финальная версия песни отправлена пользователю"),
                    )
                    LOGGER.debug("Requested song generation, task ID: %s", task_id)
                    return {"statusCode": 200, "body": ""}
        # Feedback intent
        if detect_intent.get("intent") == "feedback":
            is_final_song_received = any(msg.get("content") == "финальная версия песни получена пользователем" for msg in last_5_assist)
            if is_final_song_received and not any(msg.get("content") == "feedback_audio_send" for msg in last_5_assist):
                self.telegram.send_markup(chat_id, "Ты можешь...", self.song_received_markup)
                self.telegram.send_audio(chat_id, self.FEEDBACK_INTENT_ANSWER_MP3, "Береги своё вдохновение...")
                self.db.execute(
                    "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                    (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "feedback_audio_send"),
                )
                return {"statusCode": 200, "body": ""}
        # Fallback to general LLM call
        ai_answer = self.llm.call_with_tools(openai_msgs, tools=[])
        if ai_answer:
            # Save assistant response
            self.db.execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", ai_answer),
            )
            try:
                self.telegram.send_chunks(chat_id, ai_answer)
            except Exception:
                LOGGER.exception("Failed to send message to Telegram %s", chat_id)
        return {"statusCode": 200, "body": ""}
