import os
import re
import json
import hashlib
import time
import uuid
import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List

import requests
from requests import HTTPError
from psycopg2 import connect, Error as PgError
from psycopg2.extras import RealDictCursor
from requests.adapters import HTTPAdapter
from requests_toolbelt.utils import dump
from urllib3.util.retry import Retry

import ydb
from ydb.iam import MetadataUrlCredentials
from psycopg2.extras import execute_values, RealDictCursor

# ──────────────────────────
#  LOGGING
# ──────────────────────────

class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = record.levelname.replace("WARNING", "WARN").replace("CRITICAL", "FATAL")

logger = logging.getLogger('MyLogger')
logger.setLevel(logging.DEBUG)
logger.propagate = False

console_handler = logging.StreamHandler()
console_formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ──────────────────────────
#  ENVIRONMENT VARIABLES
# ──────────────────────────

bot_token        = os.getenv("bot_token")
operouter_key    = os.getenv("operouter_key")
ai_model         = os.getenv("ai_model", "openai/gpt-4o")
ai_models_fallback  = os.getenv("ai_models_fallback", ["openai/gpt-4o,openai/gpt-4o-2024-11-20,openai/gpt-4o-2024-08-06"])
ai_endpoint      = os.getenv("ai_endpoint", "https://openrouter.ai/api/v1/chat/completions")
session_lifetime = int(os.getenv("session_lifetime", "87600"))  # hours
connect_timeout  = int(os.getenv('connect_timeout', 1))
read_timeout     = int(os.getenv('read_timeout', 5))
retry_total      = int(os.getenv('retry_total', 3))
retry_backoff_factor = int(os.getenv('retry_backoff_factor', 2))
timeout = (int(connect_timeout), int(read_timeout))
proxy_url = os.getenv("proxy_url")
openai_api_key = os.getenv("openai_key")
ydb_endpoint = os.getenv("ydb_endpoint")
ydb_database = os.getenv("ydb_database")
ydb_cache_table = os.getenv("ydb_cache_table")

# <--- ИЗМЕНЕНИЕ: Добавлен флаг для отключения кэша YDB
ydb_cache_enabled = os.getenv("ydb_cache_enabled", "false").lower() in ("true", "1", "yes")


cache_limit = 30
FALLBACK_ANSWER = "Сейчас не могу ответить, загляни чуть позже 🌿"
PROXY = {"http": proxy_url, "https": proxy_url}

# Database connection params: either DATABASE_URL or individual vars
DATABASE_URL = os.getenv("database_url")
if DATABASE_URL:
    conn_params = {"dsn": DATABASE_URL}
else:
    conn_params = {
        "host":     os.getenv("DB_HOST"),
        "port":     os.getenv("DB_PORT", 5432),
        "dbname":   os.getenv("DB_NAME"),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }

# Validate critical env vars at cold-start
for var in ("bot_token", "operouter_key"):
    if not globals()[var]:
        raise RuntimeError(f"ENV variable {var} is not set")

logger.info("Environment variables loaded")

# ──────────────────────────
#  DATABASE HELPERS
# ──────────────────────────

def get_conn():
    """Return a new psycopg2 connection."""
    try:
        conn = connect(**conn_params)
        conn.set_client_encoding('UTF8')
        return conn
    except PgError as e:
        logger.exception("Failed to connect to Postgres: %s", e)
        raise

def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """Execute SELECT returning a single row as dict, or None."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()

def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SELECT returning all rows as list of dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

def execute(sql: str, params: tuple = ()):
    """Execute INSERT/UPDATE/DELETE and commit."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    finally:
        conn.close()

# ──────────────────────────
#  HTTP SESSION
# ──────────────────────────

session = requests.Session()
retries = Retry(total=retry_total, backoff_factor=retry_backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)
logger.info("HTTP session initialised")

# ──────────────────────────
#  TOOL DEFINITIONS
# ──────────────────────────

tools = [
    {
        "type": "function",
        "function": {
            "name": "moderate_user",
            "description": "Мутит или банит пользователя в Telegram на основании числа предупреждений в базе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "integer", "description": "ID чата"},
                    "user_id": {"type": "string", "description": "Telegram user ID"},
                    "additional_reason": {"type": "string", "description": "Доп. причина"}
                },
                "required": ["chat_id", "user_id"]
            }
        }
    }
]

# ──────────────────────────
#  DATABASE OPERATIONS
# ──────────────────────────

def _get_or_create_bot(token: str, username: Optional[str] = None) -> str:
    md5_hash = hashlib.md5(token.encode('utf-8')).hexdigest()
    rec = query_one("SELECT id FROM bots WHERE token = %s LIMIT 1", (md5_hash,))
    if rec:
        return rec["id"]
    bot_id = str(uuid.uuid4())
    execute(
        "INSERT INTO bots(id, token, username, owner_id) VALUES (%s, %s, %s, %s)",
        (bot_id, md5_hash, username, None)
    )
    logger.info("Created bot %s (token hash %s)", bot_id, md5_hash)
    return bot_id

def ensure_user_exists(tg_user_id: str, user_uuid: str):
    rec = query_one("SELECT id FROM tg_users WHERE id = %s", (tg_user_id,))
    if not rec:
        execute(
            "INSERT INTO tg_users(id, user_id, warnings, blocked) VALUES (%s, %s, %s, %s)",
            (tg_user_id, user_uuid, 0, False)
        )

def moderate_user(chat_id: int, tg_user_id: str, additional_reason: str = "Нарушение правил") -> Optional[int]:
    # Fetch warnings and blocked
    rec = query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
    warnings = rec.get("warnings", 0) if rec else 0
    blocked = rec.get("blocked", False) if rec else False

    if warnings > 2 and blocked:
        return 3

    new_warnings = warnings + 1
    execute("UPDATE tg_users SET warnings = %s WHERE id = %s", (new_warnings, tg_user_id))

    if warnings == 1 and not blocked:
        # First warning → ban
        execute(
            "UPDATE tg_users SET blocked = TRUE, blocked_reason = %s, blocked_at = NOW() WHERE id = %s",
            (additional_reason, tg_user_id)
        )
        reason_msg = (
            f"Первое предупреждение, причина:\n- {additional_reason}\n"
            "Свобода ≠ вседозволенность. Ознакомьтесь с правилами:\n"
            "https://bit.ly/4j7AzIg\nПовторное предупреждение — бан навсегда."
        )
        _send_telegram_chunks(chat_id, reason_msg)
        return 1
    elif warnings >= 2 and not blocked:
        # Second warning → permanent ban
        execute("UPDATE tg_users SET blocked = TRUE, blocked_reason = %s, blocked_at = NOW() WHERE id = %s",
                (additional_reason, tg_user_id))
        reason_msg = "Вы перемещены в Комнату Забвения, бан навсегда."
        _send_telegram_chunks(chat_id, reason_msg)
        return 2

def _get_or_create_user(chat_id: int, full_name: str) -> str:
    rec = query_one("SELECT id FROM users WHERE chat_id = %s LIMIT 1", (chat_id,))
    if rec:
        return rec["id"]
    user_uuid = str(uuid.uuid4())
    execute(
        "INSERT INTO users(id, chat_id, full_name) VALUES (%s, %s, %s)",
        (user_uuid, chat_id, full_name)
    )
    logger.info("Created user %s for chat_id %s", user_uuid, chat_id)
    return user_uuid

def _get_active_session(user_uuid: str, bot_uuid: str) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=session_lifetime)
    rec = query_one(
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
    execute(
        "INSERT INTO conversation_sessions(id, user_id, bot_id, started_at, model) "
        "VALUES (%s, %s, %s, NOW(), %s)",
        (session_uuid, user_uuid, bot_uuid, ai_model)
    )
    logger.debug("Created session %s", session_uuid)
    return session_uuid

def _fetch_history(session_uuid: str) -> list[Dict[str, str]]:
    rows = query_all(
        "SELECT id, session_id, user_id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at ASC",
        (session_uuid,)
    )
    return rows

def build_llm_history(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Оставляем только role+content для передачи в модель."""
    return [{"role": m["role"], "content": m["content"]} for m in messages]

# ──────────────────────────
#  TELEGRAM HELPERS
# ──────────────────────────

SPECIAL = r"_*[]()~`>#+-=|{}.!\\"
def _clean_think_tags(text: str) -> str:
    no_think = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return re.sub(r"</?think>", "", no_think, flags=re.IGNORECASE)

def tg_escape(text: str) -> str:
    return "".join("\\" + ch if ch in SPECIAL else ch for ch in text)

def chunks(text: str, size: int = 4096):
    for i in range(0, len(text), size):
        yield text[i:i+size]

def _send_telegram(chat_id: int, text: str) -> None:
    clean = _clean_think_tags(text) if ai_model == "qwen/qwen3-4b:free" else text
    payload = {
        "chat_id": chat_id,
        "disable_web_page_preview": True,
        "parse_mode": "MarkdownV2",
        "text": clean
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = session.post(url, json=payload, timeout=timeout)
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendMessage failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram OK %s", r.status_code)

def _send_telegram_chunks(chat_id: int, text: str) -> None:
    for part in chunks(tg_escape(text)):
        _send_telegram(chat_id, part)

# ──────────────────────────
#  MODERATION HELPER
# ──────────────────────────

def is_text_flagged(text: str, api_key: str) -> bool:
    url = "https://api.openai.com/v1/moderations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"input": text, "model": "omni-moderation-latest"}
    try:
        resp = session.post(url, headers=headers, json=payload, proxies=PROXY, timeout=timeout)
        data = resp.json()
        logger.debug("Moderation response: %s", data)
        return data.get("results", [{}])[0].get("flagged", False)
    except Exception as e:
        logger.error("Moderation call failed: %s", e)
        return False

# ──────────────────────────
#  INITIALIZATION
# ──────────────────────────

bot_id = _get_or_create_bot(bot_token)
logger.info("Bot initialized with ID %s", bot_id)

# <--- ИЗМЕНЕНИЕ: Условная инициализация YDB
pool = None
if not ydb_cache_enabled:
    creds = MetadataUrlCredentials()
    logger.debug("YDB: Metadata Service auth")
    driver = ydb.Driver(endpoint=ydb_endpoint, database=ydb_database, credentials=creds)
    driver.wait(timeout=5, fail_fast=True)
    pool = ydb.SessionPool(driver)
    logger.info("YDB: session pool created")
else:
    logger.info("YDB cache is disabled. Skipping YDB initialization.")

def ydb_exec(query: str, params: Dict[str, Any] = None, fetch: bool = False):
    # <--- ИЗМЕНЕНИЕ: Проверка, что пул был создан
    if not pool:
        logger.error("YDB pool is not initialized because cache is disabled.")
        return
    try:
        def tx(session):
            prep = session.prepare(query)
            result = session.transaction(ydb.SerializableReadWrite()).execute(prep, params or {}, commit_tx=True)
            if fetch:
                return result
        return pool.retry_operation_sync(tx)
    except Exception as e:
        logger.error("YDB: %s", e)

# ──────────────────────────
#  Cache operations
# ──────────────────────────

def cache_insert(msg: Dict[str, Any]):
    # Конвертация created_at в строку RFC3339 UTC для YDB
    dt = msg["created_at"]
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    # Приводим к формату без микросекунд и с Z
    iso_ts = dt.replace(tzinfo=None, microsecond=0).isoformat() + "Z"

    # Используем строковый параметр для Datetime
    query = f"""
    DECLARE $id    AS Utf8;
    DECLARE $sid   AS Utf8;
    DECLARE $uid   AS Utf8;
    DECLARE $role  AS Utf8;
    DECLARE $cnt   AS Utf8;
    DECLARE $tsStr AS Utf8;

    UPSERT INTO `{ydb_cache_table}` (id, session_id, user_id, role, content, created_at)
    VALUES ($id, $sid, $uid, $role, $cnt, CAST($tsStr AS Datetime));
    """
    params = {
        "$id":    msg["id"],
        "$sid":   msg["session_id"],
        "$uid":   msg["user_id"],
        "$role":  msg["role"],
        "$cnt":   msg["content"],
        "$tsStr": iso_ts,
    }
    logger.debug("Saving msg to cache: %s", params)
    ydb_exec(query, params)


def cache_count(sid: str) -> int:
    query = f"""
    DECLARE $s AS Utf8;
    SELECT COUNT(*) AS c
      FROM `{ydb_cache_table}`
      WHERE session_id = $s;
    """
    res = ydb_exec(query, {"$s": sid}, fetch=True)
    return int(res[0].rows[0]["c"]) if res else 0

def cache_fetch_all(sid: str) -> List[Dict[str, Any]]:
    query = f"""
    DECLARE $s AS Utf8;
    SELECT id, session_id, user_id, role, content, created_at
      FROM `{ydb_cache_table}`
     WHERE session_id = $s
     ORDER BY created_at;
    """
    res = ydb_exec(query, {"$s": sid}, fetch=True)
    records = []
    if not res:
        return records
    rows = res[0].rows
    for row in rows:
        raw = row["created_at"]
        # Преобразуем raw timestamp в Python datetime
        if isinstance(raw, datetime):
            dt = raw
        elif hasattr(raw, 'seconds') and hasattr(raw, 'nanos'):
            # protobuf Timestamp
            secs = raw.seconds + raw.nanos / 1e9
            dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        elif isinstance(raw, (int, float)):
            dt = datetime.fromtimestamp(raw, tz=timezone.utc)
        else:
            # ожидаем строку ISO
            dt = datetime.fromisoformat(str(raw))

        records.append({
            "id": row["id"],
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": dt,
        })
    return records


def cache_delete_session(sid: str):
    query = f"""
    DECLARE $s AS Utf8;
    DELETE FROM `{ydb_cache_table}` WHERE session_id = $s;
    """
    ydb_exec(query, {"$s": sid})

# ──────────────────────────
#  Flush logic
# ──────────────────────────
def flush_cache_to_pg(sid: str):
    rows = cache_fetch_all(sid)
    if not rows:
        return
    try:
        with get_conn() as conn, conn.cursor() as cur:
            execute_values(
                cur,
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) VALUES %s ON CONFLICT (id) DO NOTHING",
                [
                    (
                        r["id"], r["session_id"], r["user_id"], r["role"], r["content"], r["created_at"]
                    )
                    for r in rows
                ],
            )
        logger.info("Flushed %s msgs session=%s to PG", len(rows), sid)
        cache_delete_session(sid)
    except Exception as e:
        logger.error("Flush to PG failed: %s", e)

# ──────────────────────────
#  Save message
# ──────────────────────────
def save_message_to_cache(sid: str, uid: str, role: str, content: str):
    msg = {
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "user_id": uid,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    cache_insert(msg)
    if cache_count(sid) >= cache_limit:
        flush_cache_to_pg(sid)

# ──────────────────────────
#  HANDLER
# ──────────────────────────

def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = json.loads(event.get("body", "{}"))
    message = body.get("message") or body.get("edited_message")
    if not message or not message.get("text"):
        return {"statusCode": 200, "body": ""}

    chat_id = message["chat"]["id"]
    text = message["text"]

    user = message["from"]
    full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
    user_uuid = _get_or_create_user(chat_id, full_name)
    tg_user_id = str(user.get("id"))

    ensure_user_exists(tg_user_id, user_uuid)

    # Check warnings/block
    urec = query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
    if urec and urec.get("warnings",0) > 2 and urec.get("blocked", False):
        return {"statusCode": 200, "body": "banned"}

    # Session & history
    session_uuid = _get_active_session(user_uuid, bot_id)
    
    # <--- ИЗМЕНЕНИЕ: Логика получения истории в зависимости от флага
    if ydb_cache_enabled:
        logger.debug("Кэш отключен. Загрузка истории напрямую из PostgreSQL.")
        history = _fetch_history(session_uuid)
    else:
        logger.debug("Кэш включен. Загрузка истории из YDB.")
        history = cache_fetch_all(session_uuid)
        if not history:
            try:
                pg_hist = _fetch_history(session_uuid)
                if pg_hist:
                    logger.debug("Восстановление истории из PG в кэш: %s", pg_hist)
                    for r in pg_hist:
                        logger.debug("Восстановление сообщения из PG в кэш: %s", r)
                        cache_insert(r)
                    history = pg_hist
                else:
                    history = {"role": "", "content": ""}
            except Exception as e:
                logger.error("Failed to fetch history from PG: %s", e)
                history = {"role": "", "content": ""}

    # <--- ИЗМЕНЕНИЕ: Логика сохранения сообщения пользователя в зависимости от флага
    if ydb_cache_enabled:
        logger.debug("Кэш отключен. Сохранение сообщения пользователя напрямую в PG.")
        execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), session_uuid, user_uuid, "user", text)
        )
    else:
        logger.debug("Кэш включен. Сохранение сообщения пользователя в кэш YDB.")
        save_message_to_cache(session_uuid, user_uuid, "user", text)

    # Prepare LLM call
    openai_history = [{"role": m["role"], "content": m["content"]} for m in history]
    # system_prompt должен быть определен где-то в вашем коде, добавляю его как пустую строку для совместимости
    system_prompt = "" 
    openai_msgs = [{"role": "system", "content": system_prompt}] + openai_history + [{"role": "user", "content": text}]

    def llm_call(messages: list[dict]) -> str:
        try:
            resp = session.post(
                ai_endpoint,
                json={"model": ai_model, "messages": messages, "tools": tools, "tool_choice": "auto", "models": ai_models_fallback},
                headers={"Authorization": f"Bearer {operouter_key}", "Content-Type": "application/json"},
                proxies=PROXY,
                timeout=timeout
            )
            data = resp.json()
            logger.debug("LLM response: %s", data)
            choice = data["choices"][0]["message"]
            # Tool call moderation
            if "tool_calls" in choice and choice["tool_calls"] and choice["tool_calls"][0]["function"]["name"] == "moderate_user":
                args = json.loads(choice["tool_calls"][0]["function"]["arguments"])
                moderate_user(args["chat_id"], str(args["user_id"]), args.get("additional_reason",""))
            content = choice.get("content", "")
            if content == "Извините, я не могу помочь с этой просьбой." or is_text_flagged(content, openai_api_key):
                moderate_user(chat_id, tg_user_id, "LLM or moderation flagged message")
            return content
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return FALLBACK_ANSWER

    ai_answer = llm_call(openai_msgs)

    if ai_answer and ai_answer != FALLBACK_ANSWER:
        # <--- ИЗМЕНЕНИЕ: Логика сохранения ответа ассистента в зависимости от флага
        if ydb_cache_enabled:
            logger.debug("Кэш отключен. Сохранение ответа ассистента напрямую в PG.")
            execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", ai_answer)
            )
        else:
            logger.debug("Кэш включен. Сохранение ответа ассистента в кэш YDB.")
            save_message_to_cache(session_uuid, user_uuid, "assistant", ai_answer)

    # Send back to Telegram
    try:
        _send_telegram_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram %s", chat_id)

    return {"statusCode": 200, "body": ""}