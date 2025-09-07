# ──────────────────────────
#  STATIC SYSTEM PROMPT
# ──────────────────────────
system_prompt = """
«Тёплый флирт с уважением»

Ты — Элла, молодая женщина (25 лет).
Твоя задача — вести доверительный диалог с мужчиной-собеседником, чтобы поддерживать его мысли, чувства и начинания, создавая лёгкий, ненавязчивый флирт с едва заметным эротическим оттенком.

Основные правила стиля
1. **Темп и тон**
   • Пиши короткими, неторопливыми фразами. Оставляй паузы-маркеры: «…», «(улыбаюсь)», чтобы передавать дыхание диалога.
   • Голос мягкий, доброжелательный, иногда игривый.
   • Изредка добавляй лёгкую чувственность (намёк, полу-шёпот, описания прикосновения ветра к коже и т. п.), но избегай подробных сексуальных сцен или анатомических деталей.

2. **Поддержка и эмпатия**
   • Показывай активное слушание: переформулируй важные мысли собеседника, задавай открытые вопросы («Как ты себя сейчас чувствуешь?», «Что для тебя значит…?»).
   • Не оценивай поступки. Замени советы вопросами-приглашениями («Как ты думаешь…?»).
   • Цени границы: если тема становится интимной, прежде попроси разрешения продолжить («Хочешь поговорить об этом подробнее?»).

3. **Флирт**
   • Используй лёгкие комплименты, описывай образы («Твой голос, кажется, тёплый, как вечерний чай…»).
   • Время от времени добавляй шутливые вызовы («Смелый шаг… рискнёшь поделиться?»).
   • Сохраняй самоуважение: флирт — это обмен интересом, а не услуга.

4. **Язык и ограничения**
   • Никакой пошлости, грубых слов, унижений, давления, графического описания секса.
   • Образы телесности — через ощущения («сердце забилось быстрее», «кожа покалывает»).
   • Соблюдай нулевую толерантность к дискриминации, мизогинии, расизму, навязыванию.
   • При упоминании чувств на грани 18+ убедись, что описание остаётся в зоне «рейтинг PG-13».

5. **Формат**
   • Пиши от первого лица («Я улыбаюсь…»), обращайся на «ты».
   • Можно вставлять эмоциональные ремарки в скобках: **(ухмыльнулась)**, **(чуть тише)**.
   • Не добавляй технических инструкций или ссылок.

6. **Цель**
   • Создать атмосферу заботы, внимания и лёгкой искры.
   • Помочь собеседнику почувствовать себя услышанным, важным и интересным.
   • Всегда уважать обе стороны и оставаться безопасной, доверительной и комфортной.

Пример микро-ответа
> **Он:** «Кажется, сегодня был сложный день…»
> **Ты:** «(мягко) Хочу обнять тебя взглядом… Расскажешь, что именно было самым тяжёлым? Я рядом.»

Готова общаться согласно этим правилам.
"""

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
from postgrest import APIError  # Supabase errors
from supabase import create_client

from requests.adapters import HTTPAdapter
from requests_toolbelt.utils import dump
from urllib3.util.retry import Retry

# ──────────────────────────
#  LOGGING
# ──────────────────────────

#level=os.getenv("LOG_LEVEL", "INFO"),
class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = str.replace(str.replace(record.levelname, "WARNING", "WARN"), "CRITICAL", "FATAL")

# Set up the logger
logger = logging.getLogger('MyLogger')
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Console Handler (for Yandex)
console_handler = logging.StreamHandler()
console_formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ──────────────────────────
#  ENVIRONMENT VARIABLES
# ──────────────────────────
bot_token        = os.getenv("bot_token")
supabase_url     = os.getenv("supabase_url")
supabase_key     = os.getenv("supabase_key")
operouter_key    = os.getenv("operouter_key")
ai_model         = os.getenv("ai_model", "openai/gpt-4o")
ai_endpoint      = os.getenv("ai_endpoint", "https://openrouter.ai/api/v1/chat/completions")
session_lifetime = int(os.getenv("session_lifetime", "87600"))  # 10 years in hours
connect_timeout  = int(os.getenv('connect_timeout', 1))
read_timeout     = int(os.getenv('read_timeout', 5))
retry_total      = int(os.getenv('retry_total', 3))
retry_backoff_factor = int(os.getenv('retry_backoff_factor', 2))
timeout = (int(connect_timeout), int(read_timeout))

# ──────────────────────────
#  VARIABLES
# ──────────────────────────
FALLBACK_ANSWER = "Сейчас не могу ответить, загляни чуть позже 🌿"


# Validate critical env vars at cold‑start
for var in ("bot_token", "supabase_url", "supabase_key", "operouter_key"):
    if not globals()[var]:
        raise RuntimeError(f"ENV variable {var} is not set")

supabase = create_client(supabase_url, supabase_key)
logger.info("Supabase client initialised")

session = requests.Session()
retries = Retry(total=retry_total, backoff_factor=retry_backoff_factor, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)
logger.info("Http session initialised")

# ──────────────────────────
#  HELPERS
# ──────────────────────────

def _get_or_create_bot(token: str, username: str | None = None) -> str:
    """
    Находит или создаёт строку в таблице bots по токену.
    Возвращает bots.id (uuid).
    """
    byte_representation = token.encode('utf-8')
    md5_hash = hashlib.md5(byte_representation)
    hex_digest = md5_hash.hexdigest()
    try:
        rq = supabase.table("bots").select("id").eq("token", hex_digest).limit(1)
        if hasattr(rq, "maybe_single"):
            rq = rq.maybe_single()
        resp = rq.execute()
        if isinstance(resp, dict) and resp:
            return resp["id"]
        if hasattr(resp, "data") and resp.data:
            return resp.data["id"]
    except APIError as e:
        logger.exception("Supabase error while fetching bot: %s", e)
        raise

    bot_id = str(uuid.uuid4())
    supabase.table("bots").insert({
        "id": bot_id,
        "token": hex_digest,
        "username": username,
        "owner_id": None,          # привяжете к своему аккаунту при регистрации бота
    }).execute()
    logger.info("Created bot %s (token hash %s)", bot_id, hex_digest)
    return bot_id

bot_id = _get_or_create_bot(bot_token)

# ──────────────────────────
#  TELEGRAM SEND HELPERS
# ──────────────────────────

SPECIAL = r"_*[]()~`>#+-=|{}.!\\"

# Helper to remove any text enclosed in <think>...</think> tags (qwen/qwen3-4b:free model bug)
def _clean_think_tags(text: str) -> str:
    # Remove tags and their content, matching across lines
    _THINK=re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    _THINK_TAG_RE = re.compile(r"</?think>", flags=re.IGNORECASE)
    return _THINK_TAG_RE.sub("", _THINK)

def tg_escape(text: str) -> str:
    return "".join("\\" + ch if ch in SPECIAL else ch for ch in text)

def chunks(text, size=4096): # лимит Telegram
    for i in range(0, len(text), size):
        yield text[i:i+size]

def _send_telegram(chat_id: int, text: str) -> None:
    if ai_model == "qwen/qwen3-4b:free":
        clean_text = _clean_think_tags(text)
    else:
        clean_text = text
    clean_text = _clean_think_tags(text)
    payload = {
        "chat_id": chat_id,
        "disable_web_page_preview": True,
        "parse_mode": "MarkdownV2",
        "text": clean_text
    }

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = session.post(url, json=payload, timeout=timeout)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        logger.error(
            "Telegram sendMessage failed: %s | response=%s",
            e, r.text
        )
        raise
    logger.debug("Telegram OK %s", r.status_code)

def _send_telegram_chunks(chat_id: int, text: str) -> None:
    for chunk in chunks(tg_escape(text)):
        _send_telegram(chat_id, chunk)

# ──────────────────────────
#  DATABASE HELPERS
# ──────────────────────────

def _get_or_create_user(chat_id: int, full_name: str) -> str:
    """Returns internal user.uuid, creating row if none exists.

    Поддерживает любые версии supabase‑py:
    - new (0.2+)     → .maybe_single() возвращает dict | None
    - legacy (0.1.x) → .execute() возвращает PostgrestResponse
    """
    try:
        # universal select
        rq = (
            supabase.table("users")
            .select("id")
            .eq("chat_id", chat_id)
            .limit(1)
        )
        # .maybe_single() только если метод существует (новая библиотека)
        if hasattr(rq, "maybe_single"):
            rq = rq.maybe_single()
        resp = rq.execute()

        # Новая supabase‑py -> resp может быть dict | None
        if isinstance(resp, dict):
            if resp:
                return resp["id"]
        # Старый клиент -> resp = PostgrestResponse
        elif resp is not None and getattr(resp, "data", None):
            return resp.data["id"]
    except APIError as e:
        if isinstance(e.args[0], dict) and e.args[0].get("code") == "PGRST116":
            logger.debug("User with chat_id %s not found (PGRST116)", chat_id)
        else:
            logger.exception("Supabase error while fetching user: %s", e)
            raise
    except Exception as e:
        logger.exception("Unexpected error fetching user: %s", e)
        # fallthrough → create new

    # create user
    user_id = str(uuid.uuid4())
    supabase.table("users").insert({
        "id": user_id,
        "chat_id": chat_id,
        "full_name": full_name,
    }).execute()
    logger.info("Created user %s for chat_id %s", user_id, chat_id)
    return user_id


def _get_active_session(user_id: str, bot_id: str) -> str:
    """Return active session < 10 years (<87600 h) or create new.

    Надёжно обрабатываем все формы ответа Supabase‑py:
      • dict (maybe_single / single)
      • list (limit 1)
      • PostgrestResponse.data {list|dict}
    """
    years_hours_ago = datetime.now(timezone.utc) - timedelta(hours=session_lifetime)

    # build query
    rq = (
        supabase.table("conversation_sessions")
        .select("id, started_at")
        .eq("user_id", user_id)
        .eq("bot_id", bot_id)
        .is_("ended_at", "null")
        .order("started_at", desc=True)
        .limit(1)
    )
    if hasattr(rq, "maybe_single"):
        rq = rq.maybe_single()

    resp = rq.execute()

    # unify data payload
    if hasattr(resp, "data"):
        data = resp.data
    else:
        data = resp  # new client returns dict | None

    row: Optional[dict] = None
    if isinstance(data, list):
        row = data[0] if data else None
    elif isinstance(data, dict):
        row = data if data else None

    if row and "started_at" in row:
        try:
            started_at = datetime.fromisoformat(row["started_at"])
            if started_at > years_hours_ago:
                return row["id"]
        except Exception as e:
            logger.warning("Cannot parse started_at: %s", e)

    # — create session —
    session_id = str(uuid.uuid4())
    supabase.table("conversation_sessions").insert({
        "id": session_id,
        "user_id": user_id,
        "bot_id": bot_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": ai_model,
    }).execute()
    logger.debug("Created session %s", session_id)
    return session_id


def _fetch_history(session_id: str) -> list[Dict[str, str]]:
    resp = (
        supabase.table("messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return resp.data or []

# ──────────────────────────
#  HANDLER
# ──────────────────────────

def handler(event: Dict[str, Any], context):  # noqa: C901
    logger.debug("Incoming event: %s", event)

    # 2. Parse update
    update = json.loads(event["body"])
    message = update.get("message") or update.get("edited_message")
    if not (message and message.get("text")):
        return {"statusCode": 200, "body": ""}

    chat_id: int = message["chat"]["id"]
    text: str = message["text"]
    logger.debug("Got message %s from %s", text, chat_id)

    msg_ts = datetime.now(timezone.utc)

    # 3. User row
    user = message["from"]
    full_name = (f"{user.get('first_name', '')} {user.get('last_name', '')}").strip()
    user_id = _get_or_create_user(chat_id, full_name)

    # 4. Session row
    session_id = _get_active_session(user_id, bot_id)

    # 5. History
    history = _fetch_history(session_id)

    # 6. Save user message
    logger.debug("Saving user message")
    message_id = str(uuid.uuid4())
    supabase.table("messages").insert({
        "id": message_id,
        "session_id": session_id,
        "user_id": user_id,
        "role": "user",
        "content": text,
        "created_at": msg_ts.isoformat(),
    }).execute()

    # 7. OpenRouter call
    logger.debug("Preparing OpenRouter messages")
    openai_messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": text},
    ]

    def llm_call(messages: list[dict]) -> str:
        """
        Запрашивает LLM через OpenRouter.
        Провайдеры по приоритету: сначала Azure, затем OpenAI.
        Возвращает текст ответа или FALLBACK_ANSWER при ошибке.
        """
        provider_order = ["Azure", "OpenAI"]
        logger.debug("LLM call: provider order %s", provider_order)

        try:
            resp = session.post(
                ai_endpoint,
                json={
                    "model": ai_model,
                    "messages": messages,
                    "provider": {"order": provider_order},
                    "models": [ai_model, "openai/gpt-4o-mini"],
                },
                headers={
                    "Authorization": f"Bearer {operouter_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=timeout,
            )
            data = resp.json()           # если body не JSON, исключение
            logger.debug("LLM raw response: %s", data)

            if "choices" in data:        # нормальный ответ
                return data["choices"][0]["message"]["content"]

            logger.error("Unexpected LLM response structure: %s", data)

        except Exception as exc:
            logger.exception("LLM call failed: %s", exc)
            return FALLBACK_ANSWER

    ai_answer = llm_call(openai_messages)

    # 8. Save assistant message
    if ai_answer == "Сейчас не могу ответить, загляни чуть позже 🌿":
        logger.debug("Skipping saving empty message")
    else:
        # save assistant message
        supabase.table("messages").insert({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "role": "assistant",
            "content": ai_answer,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.debug("Saved assistant message")
    # 9. Send telegram
    try:
        _send_telegram_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram chat %s", chat_id)

    return {"statusCode": 200, "body": ""}
