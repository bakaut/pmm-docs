import os
import re
import json
import hashlib
import uuid
import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import requests
from requests import HTTPError
from psycopg2 import connect, Error as PgError
from psycopg2.extras import RealDictCursor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import tiktoken
import random
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import boto3
from pydantic import TypeAdapter, Base64Bytes, ValidationError

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

FALLBACK_ANSWER = "Сейчас не могу ответить, загляни чуть позже 🌿"
SONG_GENERATING_MESSAGE = "Твоя песня уже в пути.\nДай ей немного времени — она рождается 🌿\n\nПесня придёт отдельным сообщением через 2 минуты"
CONFUSED_INTENT_ANSWER_MP3 = "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/try.mp3"
FEEDBACK_INTENT_ANSWER_MP3 = "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/feedback.mp3"
AI_COMPOSER = "AI сгенерировано с помощью https://t.me/PoyMoyMirBot"

PROXY = {"http": proxy_url, "https": proxy_url}
test_url = "https://pmm-http-bin.website.yandexcloud.net"
song_path = "/function/storage/songs/"
song_bucket_name = os.getenv("song_bucket_name")

CONFUSED_INTENT_ANSWER = [
    "Ты можешь быть с собой честен здесь. Без страха. Даже если честность сейчас — это: \"Я не знаю, что чувствую\". Это уже начало песни...",
    "Чем точнее ты поделишься — тем точнее я смогу услышать тебя. А значит, и песня будет ближе к тебе самому...",
    "Иногда самая красивая строчка рождается из фразы \"я боюсь сказать, что думаю\"... Это не слабость. Это глубина.",
    "В этом месте можно говорить правду. Даже если она шепотом.",
    "💬 Отклики других людей — чтобы почувствовать, как звучит _ПойМойМир_ в чужих сердцах: https://poymoymir.ru/feedback/",
    "🎧 Подкасты о проекте — мягкое знакомство с тем, как здесь всё устроено: https://poymoymir.ru/feedback/"
]

song_received_markup = {
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

song_received_message = "Спасибо за доверие!\n🌿 - Поддержать проект, дать другим возможность услышать себя\n🔁 - Поделиться песней с другом\n🤗 - Обнять автора\n💬 - Оставить отзыв\n🔕 - Комната тишины, остаться с собой в моменте"


# Suno API settings
suno_api_url = os.getenv("suno_api_url", "https://apibox.erweima.ai/api/v1/generate")
suno_model = os.getenv("suno_model", "V4_5")
suno_callback_url = os.getenv("suno_callback_url")
suno_api_key = os.getenv("suno_api_key")

with open("knowledge_bases/prepare_suno.txt", "r", encoding="utf-8") as file_suno:
    system_prompt_prepare_suno = file_suno.read()

with open("system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()

with open("knowledge_bases/determinate_intent.txt", "r", encoding="utf-8") as file_intent:
    system_prompt_intent = file_intent.read()

with open("knowledge_bases/detect_emotional_state.txt", "r", encoding="utf-8") as file_emotion:
    system_prompt_detect_emotion = file_emotion.read()

# with open("knowledge_bases/detect_userflow_state.txt", "r", encoding="utf-8") as system_prompt_userflow_state:
#     system_prompt_detect_emotion = system_prompt_userflow_state.read()

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

def check_proxy(proxy_url, timeout=read_timeout, test_url=test_url):
    """
    Проверяет работоспособность HTTP/HTTPS прокси, отправляя запрос на test_url.
    Возвращает True, если прокси работает, иначе False.
    """
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.debug(f"Proxy check failed: {e}")
        return False

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

def _fetch_history(session_uuid: str, limit_count: int = None) -> list[Dict[str, str]]:
    if limit_count is not None:
        # Получаем количество всех сообщений для вычисления OFFSET
        total_count = query_one(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = %s",
            (session_uuid,)
        )["cnt"]
        offset = max(0, total_count - limit_count)
        rows = query_all(
            "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC OFFSET %s LIMIT %s",
            (session_uuid, offset, limit_count)
        )
    else:
        rows = query_all(
            "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC",
            (session_uuid,)
        )
    return [{"role": r["role"], "content": r["content"]} for r in rows]

# ──────────────────────────
#  TELEGRAM HELPERS
# ──────────────────────────

def send_telegram_callback(callback_id, text):
    r = session.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": False
    })
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendMessage failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram markup sent OK %s", r.status_code)

def send_telegram_markup(chat_id: int, text: str, markup: dict) -> None:
    """
    Отправляет пользователю Telegram с кнопками для оплаты, поделиться и обнять автора.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": json.dumps(markup),
        "parse_mode": "MarkdownV2"
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = session.post(url, json=payload, timeout=timeout)
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendMessage failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram markup sent OK %s", r.status_code)


def _send_audio(chat_id: int, audio_url: str, title: str = "") -> None:
    payload = {
        "chat_id": chat_id,
        "audio": audio_url,
        "title": title
    }
    if title:
        payload["caption"] = title
    url = f"https://api.telegram.org/bot{bot_token}/sendAudio"
    r = session.post(url, json=payload, timeout=timeout)
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendAudio failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram audio OK %s", r.status_code)

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
#  SUNO HELPER
# ──────────────────────────
def generate_song_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """
    Генерирует временную (signed) ссылку на файл в приватном S3/Yandex Object Storage бакете.
    :param bucket: имя бакета
    :param key: путь к файлу внутри бакета
    :param expires_in: время жизни ссылки в секундах (по умолчанию 1 час)
    :return: временная ссылка (signed url)
    """
    s3 = boto3.client("s3")
    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=expires_in
    )
    return url

def download_and_process_song(song_url, tg_user_id, song_title, song_artist, local_folder, song_bucket_name):
    # 1. Скачать mp3
    local_path = os.path.join(f"{local_folder}/{tg_user_id}/", f"{song_title}.mp3")
    song_key = f"{tg_user_id}/{song_title}.mp3"
    os.makedirs(f"{local_folder}/{tg_user_id}", exist_ok=True)
    r = requests.get(song_url)
    with open(local_path, "wb") as f:
        f.write(r.content)

    # 2. Изменить ID3 теги
    audio = MP3(local_path, ID3=EasyID3)
    audio["title"] = song_title
    audio["artist"] = song_artist
    audio["composer"] = AI_COMPOSER
    audio.save()

    # 3. Generate signed url
    signed_url = generate_song_url(bucket = song_bucket_name, key = song_key)
    return signed_url


def request_suno(prompt: str, style: str, title: str, suno_model: str, suno_api_key: str) -> None:
    """
    Request a Suno AI audio generation for the given prompt, style, and title.
    The result will be sent to the Telegram chat with the given chat_id via the
    callback URL set in environment variable suno_callback_url.

    Args:
        prompt (str): The text prompt to generate audio for.
        chat_id (int): The Telegram chat ID to send the result to.
        style (str): The style of the generated audio.
        title (str): The title of the generated audio.

    Returns:
       {"code": 200,"msg": "success","data": {"taskId": "5c79****be8e"}}
    """
    if not suno_callback_url:
        logger.error("suno_callback_url is not set")
        return
    callback = f"{suno_callback_url}"
    headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': f'Bearer {suno_api_key}'
    }

    payload = {
        "prompt": prompt,
        "style": style,
        "title": title,
        "customMode": True,
        "instrumental": False,
        "model": suno_model,
        "callBackUrl": callback,
    }
    try:
        r = session.post(suno_api_url, json=payload, timeout=timeout, headers=headers)
        data = r.json()
        r.raise_for_status()
        logger.debug("Suno request OK: %s", r.text)
        return data
    except Exception as e:
        logger.exception("Suno generation failed: %s", e)

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

# ────────LLM CALL---------------
def llm_response(user_message: str, system_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})
    try:
        resp = session.post(
            ai_endpoint,
            json={"model": ai_model, "messages": messages, "models": ai_models_fallback},
            headers={"Authorization": f"Bearer {operouter_key}", "Content-Type": "application/json"},
            proxies=(None if not check_proxy(proxy_url, read_timeout) else PROXY),
            timeout=timeout
        )
        data = resp.json()
        logger.debug("LLM one response: %s", data)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        logger.error("LLM one call failed: %s", e)
        return  {"error": str(e)}

def llm_conversation(messages: list[dict], system_message: str) -> str:
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})
    try:
        resp = session.post(
            ai_endpoint,
            json={"model": ai_model, "messages": messages, "models": ai_models_fallback},
            headers={"Authorization": f"Bearer {operouter_key}", "Content-Type": "application/json"},
            proxies=(None if not check_proxy(proxy_url, read_timeout) else PROXY),
            timeout=timeout
        )
        data = resp.json()
        logger.debug("LLM conversation response: %s", data)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        logger.error("LLM conversation call failed: %s", e)
        return  {"error": str(e)}

def llm_call(messages: list[dict], chat_id: str, tg_user_id: str) -> str:
    MAX_TOKENS = 50_000 # 51962 ~ 128k эмпиричеси
    encoder = tiktoken.encoding_for_model("gpt-4o")

    # Функция для подсчёта токенов в одном сообщении
    def count_tokens(msg: dict) -> int:
        # Суммируем токены ролей и контента
        role_tokens = len(encoder.encode(msg["role"]))
        content_tokens = len(encoder.encode(msg["content"]))
        return role_tokens + content_tokens + 4  # +4 — служебные токены системы

    # Подсчитываем и обрезаем
    total = sum(count_tokens(m) for m in messages)
    logger.debug("Total tokens: %s", total)
    # Всегда оставляем первый системный prompt
    sys_msg = messages[0]
    chat_msgs = messages[1:]
    # Обрезаем oldest-first, пока не уложимся
    while total > MAX_TOKENS and chat_msgs:
        removed = chat_msgs.pop(0)
        total -= count_tokens(removed)
    messages = [sys_msg] + chat_msgs
    total = sum(count_tokens(m) for m in messages)
    logger.debug("Total tokens after trim: %s", total)

    try:
        resp = session.post(
            ai_endpoint,
            json={"model": ai_model, "messages": messages, "tools": tools, "tool_choice": "auto", "models": ai_models_fallback},
            headers={"Authorization": f"Bearer {operouter_key}", "Content-Type": "application/json"},
            proxies=(None if not check_proxy(proxy_url, read_timeout) else PROXY),
            timeout=timeout
        )
        data = resp.json()
        logger.debug("LLM response: %s", data)
        choice = data["choices"][0]["message"]
        # Tool call moderation
        if "tool_calls" in choice and choice["tool_calls"][0]["function"]["name"] == "moderate_user":
            args = json.loads(choice["tool_calls"][0]["function"]["arguments"])
            moderate_user(args["chat_id"], str(args["user_id"]), args.get("additional_reason",""))
        content = choice.get("content", "")
        logger.debug("LLM content: %s", content)
        if content == "Извините, я не могу помочь с этой просьбой." or is_text_flagged(content, openai_api_key):
            moderate_user(chat_id, tg_user_id, "LLM or moderation flagged message")
        return content
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return FALLBACK_ANSWER

# ──────────────────────────
#  UTILS
# ──────────────────────────

def parse_body(event: Dict[str, Any]) -> Any:
    """
    Универсально разбирает event['body'] из Yandex Cloud (или AWS / GCP):
      • JSON  → dict / list
      • Base-64(JSON) → dict / list
      • Base-64(binary) → bytes
      • голый текст → str
    """
    raw: str | bytes = event.get("body", "")
    b64 = TypeAdapter(Base64Bytes)

    # 1. Пытаемся сразу прочитать JSON
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        pass          # не JSON — едем дальше

    # 2. Пытаемся декодировать Base-64
    #    (неважно, что говорит isBase64Encoded)
    try:
        decoded: bytes = b64.validate_python(raw)
    except ValidationError:
        return raw    # совсем не Base-64 → отдаём как есть (str)

    # 3. Декодировали Base-64 → возможно, внутри JSON?
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return decoded  # бинарные данные

def get_last_messages(history, count=2, role=None, force_last_user=False, extra_message=None):
    """
    Возвращает последние count сообщений из истории.
    Если задан role ("user" или "assistant"), фильтрует только по этой роли.
    Если force_last_user=True и роль не задана, то последнее сообщение обязательно от пользователя (если есть такие).
    Если extra_message передан, добавляет его в конец списка.
    """
    if role:
        filtered = [msg for msg in history if msg["role"] == role]
        result = filtered[-count:]
    elif force_last_user:
        last_user_idx = next((i for i in range(len(history)-1, -1, -1) if history[i]["role"] == "user"), None)
        if last_user_idx is None:
            result = history[-count:]
        else:
            start_idx = max(0, last_user_idx - count + 1)
            result = history[start_idx:last_user_idx+1]
    else:
        result = history[-count:]
    if extra_message:
        result = result + [extra_message]
    return result

# ──────────────────────────
#  INITIALIZATION
# ──────────────────────────

bot_id = _get_or_create_bot(bot_token)
logger.info("Bot initialized with ID %s", bot_id)

# ──────────────────────────
#  HANDLER
# ──────────────────────────

def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = parse_body(event)
    logger.debug("Incoming body: %s", body)

    if "callback_query" in body:
        callback = body["callback_query"]
        data = callback["data"]
        user = callback["from"]
        callback_id = callback["id"]

        if data == "hug_author":
            # отправляем визуальный отклик
            send_telegram_callback(callback_id, "💞 Автору переданы объятия!")

    # Parse suno api callback
    if body.get("data") and body["data"].get("callbackType") and body["data"]["callbackType"] == "complete":
        task_id = body["data"]["task_id"]
        song_url = body["data"]["data"][0]["audio_url"]
        song_title = body["data"]["data"][0]["title"]
        song_artist = "ПойМойМир"
        logger.debug("Suno song generated: %s", song_url)
        rec = query_one("SELECT tg.id AS telegram_user_id FROM public.songs AS s JOIN public.tg_users AS tg ON s.user_id = tg.user_id WHERE s.task_id = %s LIMIT 1", (task_id,))
        tg_user_id = rec["telegram_user_id"]
        logger.debug("Telegram user found: %s", rec)
        song_url = download_and_process_song(song_url = song_url, song_title = song_title, tg_user_id = tg_user_id, song_artist = song_artist, local_folder = song_path, song_bucket_name = song_bucket_name)
        path_prefix = f"{tg_user_id}/{song_title}.mp3"
        execute("UPDATE songs SET path = %s WHERE task_id = %s", (path_prefix, task_id))
        # Send final version
        user_uuid = _get_or_create_user(tg_user_id, full_name="Dummy")
        session_uuid = _get_active_session(user_uuid, bot_id)
        _send_audio(chat_id=tg_user_id, audio_url=song_url, title=song_title)
        execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "финальная версия песни получена пользователем")
        )
        return {"statusCode": 200, "body": ""}

    message = body.get("message") or body.get("edited_message")
    if not message or not message.get("text"):
        return {"statusCode": 200, "body": ""}

    chat_id = message["chat"]["id"]
    text = message["text"]

    user = message["from"]
    full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
    user_uuid = _get_or_create_user(chat_id, full_name)
    tg_user_id = str(user.get("id"))

    # Session & history
    session_uuid = _get_active_session(user_uuid, bot_id)
    history = _fetch_history(session_uuid)

    ensure_user_exists(tg_user_id, user_uuid)

    # Check warnings/block
    urec = query_one("SELECT warnings, blocked FROM tg_users WHERE id = %s", (tg_user_id,))
    if urec and urec.get("warnings",0) > 2 and urec.get("blocked", False):
        return {"statusCode": 200, "body": "banned"}

    # Save user message
    msg_id = str(uuid.uuid4())
    execute(
        "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
        "VALUES (%s, %s, %s, %s, %s, NOW())",
        (msg_id, session_uuid, user_uuid, "user", text)
    )

    # Получаем последние сообщения
    last_50_messages = get_last_messages(history, count=50)
    last_8_messages = get_last_messages(last_50_messages, count=8, force_last_user=True)
    last_20_assistant_messages = get_last_messages(last_50_messages, count=20, role="assistant")
    last_5_assistant_messages = get_last_messages(last_50_messages, count=5, role="assistant")
    last_3_assistant_messages = get_last_messages(last_50_messages, count=3, role="assistant")
    last_8_user_messages = get_last_messages(last_50_messages, count=8, role="user")

    # Ищем последнее вхождение фразы среди всех сообщений
    start_idx = None
    for i in range(len(last_50_messages)-1, -1, -1):
        if "Давай начнём всё с начала" in last_50_messages[i]["content"]:
            start_idx = i
            break

    # Если нашли — берём сообщения начиная с этой фразы (включительно)
    if start_idx is not None:
        msgs_from_phrase = last_50_messages[start_idx:]
    else:
        msgs_from_phrase = []  # если не нашли — пустой список

    # Теперь msgs_from_phrase — это список сообщений начиная с нужной фразы (или пустой)

    # Prepare LLM call
    if msgs_from_phrase:
        last_8_messages = get_last_messages(msgs_from_phrase, count=8, force_last_user=True)
        last_20_assistant_messages = get_last_messages(msgs_from_phrase, count=20, role="assistant")
        last_5_assistant_messages = get_last_messages(msgs_from_phrase, count=5, role="assistant")
        last_3_assistant_messages = get_last_messages(msgs_from_phrase, count=3, role="assistant")
        last_8_user_messages = get_last_messages(msgs_from_phrase, count=8, role="user")
        openai_msgs = [{"role": "system", "content": system_prompt}, *msgs_from_phrase, {"role": "user", "content": text}]
    else:
        openai_msgs = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": text}]

    # Detect intent and emotion
    detect_intent = llm_conversation(last_8_messages, system_prompt_intent)
    detect_emotion = llm_conversation(last_8_user_messages, system_prompt_detect_emotion)
    # detect_userflow_state = llm_conversation(last_8_messages, system_prompt_userflow_state)
    # if detect_userflow_state == "assembly":
    #     adopt system promt, add ai-song-song_v3.md
    logger.debug("User emotion: %s", detect_emotion)
    logger.debug("User intent: %s", detect_intent)
    # Save intent and emotion analysis to DB
    analysis = {"intent": detect_intent, "emotion": detect_emotion}
    execute(
        "UPDATE messages SET analysis = %s WHERE id = %s",
        (json.dumps(analysis), msg_id)
    )
    # MVP_2_2 final можно назвать по semever 0.6.1
    # Сделать пересохранение песня на yandex s3 и редактирование id3 тегов Done + тест suno-generating регресс
    # Сделать прежний формат песню последоватьено пишет строка строка + куплет  куплет + куплет чтобы пользовател видел процесс а не только текущий куплет
    # сохранить intent emotion в базу jsonb messages - done
    # Сделать регресс? проверить что все предыдущие функции работают как ожидалось
    # Не переносить сделай сначала
    # Тесты сделать, все с начала 2 песни flow
    # Написать задачи в трекер задач
    ######################
    # Next steps
    # Добавить очистку истории пользователя
    # Добавить суммаризацию и вектор для суппаризации каждый 10 сообщение но чтобы не перекрывались
    # Подумать где хранить intent emotion в базе и как jsonb done
    # здесь json формируем большой который всю суммарную инфо собдержит и его сохраняем только или отдельно?
    # здесь же определить дополнительную информацию
    # сохранить имя пользователя
    # Созранить статус на котором находиимся и краткий самери что сделали и что осталось
    # Определить состочние пользователя замещательства и так далее и помочь ему -  done
    # Векторный поиск по сессии если пользователь похожее спрашивал и подгружать самери ответа что он уже давал
    # Отдельная таблица session/user short memory контекст пользователя имя самери и так далее
    # добавить проверку что предыдущая песня > 20 минут false positive два раза если благодарить после песни done 20 сообщений
    # Векторный поиск похожую песню уже делали не делать
    # Пока через - "feedback": Пользователь уже получил финальную версию песни и аудио песню считает песню готовой. решил
    # Микро промт или regexp [Verse 1] Белый змей в небе парит, и добавляем перепиши как будто ты песенник всего мира и сохраняем как
    # сообщение ассистента которыи не видт пользователь говорим используй этот текст
    # Развернутый промт про ии композитора и модель gpt turbo или o3 попробовать она дешевле стала 2е 8е
    # Или меняем место, ставим после ответа основной ИИ доработка перед отправкой текста

    # Проверить что финальная версия песни отправлена/получена пользователю
    # Сделать два условия отдельных
    is_final_song_received = any(
        msg["content"] == "финальная версия песни получена пользователем"
        for msg in last_5_assistant_messages
    )

    is_final_song_sent = any(
        msg["content"] == "финальная версия песни отправлена пользователю"
        for msg in last_5_assistant_messages
    )

    # Проверяем наличие 'Растерянность' среди эмоций нового формата
    is_confused = any(
        e.get("name") == "Растерянность" and e.get("intensity", 0) > 90
        for e in detect_emotion.get("emotions", [])
    )
    if is_confused:
        if not any(msg["content"] == "confused_send" for msg in last_20_assistant_messages):
            if random.choice([True, False]):
                # Отправляем текст
                ANSWER = random.choice(CONFUSED_INTENT_ANSWER)
                execute(
                    "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, NOW())",
                    (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", f"{ANSWER}")
                )
                _send_telegram_chunks(chat_id, ANSWER)
            else:
                # Отправляем аудио
                _send_audio(chat_id, audio_url=CONFUSED_INTENT_ANSWER_MP3, title="Ты можешь...")
            execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "confused_send")
            )
            return {"statusCode": 200, "body": ""}

    if detect_intent["intent"] == "finalize_song" and not (is_final_song_received or is_final_song_sent):
        logger.debug("Song request detected")
        logger.debug("Parse song from history")
        get_song = llm_conversation(last_3_assistant_messages, system_prompt_prepare_suno)
        lyrics = get_song["lyrics"]
        style = get_song["style"]
        title = get_song["name"]
        logger.debug("Generate song with Suno API")
        song = request_suno(lyrics, style, title, suno_model, suno_api_key)
        task_id = song["data"]["taskId"]
        song_id = str(uuid.uuid4())
        _send_telegram_chunks(chat_id, SONG_GENERATING_MESSAGE)
        execute(
            "INSERT INTO songs(id, user_id, session_id, task_id, title, prompt, style, created_at)"
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())",
            (song_id, user_uuid, session_uuid, task_id, title, lyrics, style)
        )
        execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", SONG_GENERATING_MESSAGE)
        )
        execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "финальная версия песни отправлена пользователю")
        )
        logger.debug("Suno task ID: %s", task_id)
        return {"statusCode": 200, "body": ""}

    if detect_intent["intent"] == "feedback" and is_final_song_received:
        if not any(msg["content"] == "feedback_audio_send" for msg in last_5_assistant_messages):
            logger.debug("Feedback intent detected, user emotion: %s", detect_emotion)
            send_telegram_markup(chat_id=tg_user_id, text="Ты можешь...", markup=song_received_markup)
            _send_audio(chat_id, audio_url=FEEDBACK_INTENT_ANSWER_MP3, title="Береги своё вдохновение...")
            execute(
                "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", "feedback_audio_send")
            )
            return {"statusCode": 200, "body": ""}

    ai_answer = llm_call(openai_msgs)

    if ai_answer and ai_answer != FALLBACK_ANSWER:
        # Save assistant response
        execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), session_uuid, user_uuid, "assistant", ai_answer)
        )

    # Send back to Telegram
    try:
        _send_telegram_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram %s", chat_id)

    return {"statusCode": 200, "body": ""}
