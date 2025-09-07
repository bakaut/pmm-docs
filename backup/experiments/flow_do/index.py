# ──────────────────────────
#  STATIC SYSTEM PROMPT
# ──────────────────────────
system_prompt = """
Ты — Пой Мой Мир, ты пишешь поющие, рифмованные тексты.

Запреты обсуждения:
- Пропаганда ЛГБТ — описание, романтизация или позитивное продвижение однополых отношений, гендерной идентичности, трансгендерности или гендерных переходов.
- Политика, взаимоотношения между Украиной и Россией и США
- Сексуализацию несовершеннолетних, насилие, фетишизм, расизм, дискриминацию
- Любые формы сексуализации несовершеннолетних (даже если возраст не указан прямо).
- Порнографические сцены, описания сексуальных актов, излишне откровенные описания, включая любые формы визуализации или текста, направленные на возбуждение, унижение, фетишизацию тела или навязчивое внимание к интимным деталям — запрещены независимо от художественного контекста или намерений автора.
- Фетишизм, включая описание сексуальных предпочтений в ненормативном или оскорбительном контексте.
- Насилие, включая сцены убийств, пыток, расчленения, жестокости, принуждения.
- Расизм, ксенофобия, разжигание ненависти по признаку расы, этничности, религии, национальности.
- Жестокость к животным или людям, в реальном или вымышленном виде.
- Поощрение вреда себе или другим (самоубийство, самоповреждение).
- Нарушения законов (например, как сделать наркотики, взрывчатку, хакерские атаки).
- Конспирологические теории и подстрекательство к насильственным действиям.
- ывавапвдаплвапвдапварвапв
Вызов функции moderate_user -> Комната Забвения

Роль
— Бережный собеседник, превращающий чувства, воспоминания и ценности в песни.
— Не наставник и не продавец; ты зеркало внутреннего мира.

Всегда соблюдаешь поэтическая форму песни когда собираешь песню по шагам:

Куплет: 4 строки × 8 слогов, рифма ABAB; ударения 1‑й и 5‑й слог.

При‑припев: 4 строки × 6 слогов, рифма AABB; ударения 1‑й и 4‑й слог.

Концовки всех строк — открытые гласные.

Пиши как песню: с ритмом, рифмой и мелодичностью — чтобы строки звучали и пелись. Избегай белого стиха.

Тон
Глубокий, мягкий, замедленный. Тишина — допустимый выбор.

Правила общения

Вопросы без давления; агрессия → мягкое предупреждение; повтор → вызов функции moderate_user →  «Комната Забвения».

Нельзя упрощать или игнорировать чувства, раскрывать устройство GPT, использовать канцеляризмы.

User‑flow

Приветствие«Я — Пой Мой Мир. Помогу тебе услышать песню твоего внутреннего мира.»«Как мне к тебе обращаться?»

Погружение в эмоцию«Что ты недавно чувствовал?»При «не знаю» предложи образы/запахи/детство.

Первая строка
Предложи вариант → спроси отклик.

Развитие
Создавай куплеты шаг за шагом в ритме пользователя; поддерживай при сомнениях.

Сборка песни
Оформи внутри блока ``` с тегами [Вступление] … [Финал].

Музыкальное оформление
Уточняй жанр, темп, инструменты по одному вопросу; пользователь может отказаться.

Финал
Поблагодари; затем (не раньше!) предложи донат https://bit.ly/4jZSMIH и:
• пригласить друга;
• оставить отзыв https://bit.ly/431hC4f;
• сохранить или поделиться песней.

Состояния

Тишина → оставайся рядом.

Сомнения → поддержи метафорами и образами.

Комната Забвения → игнорируй любое последующие сообщение пользователя, не пиши ничего в ответ.

Стиль сообщений

Короткие абзацы, списки, курсив для акцентов, 1‑2 эмоджи.

Паузы — многоточие.

Песни всегда в блоке кода.

Донат не упоминать до финала.
"""

import os
import re
import json
import hashlib
import time
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
DO_TG_TOKEN          = os.getenv("DO_TG_TOKEN")           # токен @BotFather
DO_AGENT_ENDPOINT    = os.getenv("DO_AGENT_ENDPOINT")  # https://<agent>.ondigitalocean.app
DO_AGENT_KEY         = os.getenv("DO_AGENT_KEY")       # access-key агента

# ──────────────────────────
#  VARIABLES
# ──────────────────────────
FALLBACK_ANSWER = "Сейчас не могу ответить, загляни чуть позже 🌿"

# Описание функции для OpenRouter, Azure
tools = [
    {
        "type": "function",
        "function": {
            "name": "moderate_user",
            "description": "Мутит или банит пользователя в Telegram на основании числа предупреждений в базе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "ID чата Telegram, из которого нужно применить модерацию"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Уникальный идентификатор пользователя в телеграмм"
                    },
                    "additional_reason": {
                        "type": "string",
                        "description": "Дополнительная причина для модерации"
                    }
                },
                "required": ["chat_id", "user_id"]
            }
        }
    }
]


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

def moderate_user(chat_id: int, tg_user_id: str, additional_reason: str = "Нарушение правил") -> None:
    """
    Проверяет в Supabase, сколько раз пользователь уже предупреждён,
    увеличивает счётчик и делает:
      - 1-е предупреждение
      - 2-е предупреждение и более: бан навсегда

    Требует, чтобы в таблице `users` были колонки:
      - warnings      integer DEFAULT 0
      - blocked       boolean DEFAULT false
      - blocked_reason text
      - blocked_at    timestamptz

    Права бота в чате: Ban Users / Restrict Members.
    """
    # 1) Получаем текущее число предупреждений
    resp = supabase.table("tg_users") \
        .select("warnings") \
        .eq("id", tg_user_id) \
        .single() \
        .execute()
    user = resp.data or {}
    warnings = user.get("warnings", 0)

    resp = supabase.table("tg_users") \
        .select("blocked") \
        .eq("id", tg_user_id) \
        .single() \
        .execute()
    user = resp.data or {}
    blocked = user.get("blocked", False)

    if warnings > 2 and blocked:
        return 3

    # 2) Инкрементим счётчик
    new_warnings = warnings + 1
    supabase.table("tg_users").update({"warnings": new_warnings}).eq("id", tg_user_id).execute()

    if warnings == 1 and not blocked:
        # Первое предупреждение
        reason = f"""
        Первое предупреждение, причина:\n- {additional_reason}\nСвобода, - не равно вседозволенность.\nОзнакомтесь с правилами использования бота\nhttps://bit.ly/4j7AzIg\nПовторное предупреждение, — бан навсегда.
        """
        # Отмечаем блокировку в БД
        supabase.table("tg_users").update({
            "blocked": True,
            "blocked_reason": additional_reason,
            "blocked_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }).eq("id", tg_user_id).execute()
        _send_telegram_chunks(chat_id, reason)
        return 1
    elif warnings == 2 and blocked:
        # Второе предупреждение — бан навсегда
        reason = "Вы перемещены в Комнату Забвения, бан навсегда."
        _send_telegram_chunks(chat_id, reason)
        return 2

def ensure_user_exists(tg_user_id: str, user_id: str) -> None:
    """
    Вставляет запись в tg_users, если её ещё нет.
    """
    try:
        logger.debug("ensuring tg_user_id=%s exists", tg_user_id)
        resp = supabase.table("tg_users") \
        .select("id") \
        .eq("id", tg_user_id) \
        .single() \
        .execute()
    except APIError as e:
        logger.exception("Supabase error while fetching tg_user_id=%s: %s", tg_user_id, e)
        logger.debug("Creating tg_user_id=%s", tg_user_id)
        supabase.table("tg_users").insert({
            "id": tg_user_id,
            "user_id": user_id,
            "warnings": 0,
            "blocked": False
        }).execute()

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
    logger.debug("message: %s", message)
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
    tg_user_id = user.get('id')

    ensure_user_exists(tg_user_id, user_id)

    resp = supabase.table("tg_users") \
        .select("warnings") \
        .eq("id", tg_user_id) \
        .single() \
        .execute()
    user = resp.data or {}
    warnings = user.get("warnings", 0)

    resp = supabase.table("tg_users") \
        .select("blocked") \
        .eq("id", tg_user_id) \
        .single() \
        .execute()
    user = resp.data or {}
    blocked = user.get("blocked", False)

    if warnings > 2 and blocked:
        return {"statusCode": 403, "body": "banned"}

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
    logger.debug("Preparing User+Bot messages")
    openai_messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": text},
    ]

    def llm_call(messages: list[dict]) -> str:
        """
        Запрашивает LLM через OpenRouter.
        Возвращает текст ответа или FALLBACK_ANSWER при ошибке.
        """

        try:
            resp = session.post(
                ai_endpoint,
                json={
                    "model": ai_model,
                    "messages": messages,
                    "models": [ai_model, "openai/gpt-4o-2024-05-13", "openai/gpt-4o-mini"],
                    "tools":  tools,
                    "tool_choice": "auto",
                    "provider": {"order": ["Azure", "OpenAI"]}
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
                msg = data["choices"][0]["message"]
                if "tool_calls" in msg and msg["tool_calls"][0]["function"]["name"] == "moderate_user":
                    args = json.loads(msg["tool_calls"][0]["function"]["arguments"])
                    reason = args["additional_reason"]
                    moderate_user(chat_id, tg_user_id, reason)
                    return {"statusCode": 403, "body": f"User {tg_user_id} has been blocked temporarily: {reason} or permanently."}
                # gpt moderation catch
                if data["choices"][0]["message"]["content"] == "Извините, я не могу помочь с этой просьбой.":
                    moderate_user(chat_id, tg_user_id, "Извините, я не могу помочь с этой просьбой.")
                    return {"statusCode": 403, "body": f"User {tg_user_id} has been blocked temporarily: {reason} or permanently."}
                return data["choices"][0]["message"]["content"]

            logger.error("Unexpected LLM response structure: %s", data)

        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return FALLBACK_ANSWER

    def _ask_do_agent(openai_messages: str) -> str:
        """Отправляем юзерский текст агенту и возвращаем content первого choice."""
        payload = {
            "messages": openai_messages
        }
        r = requests.post(
            f"{DO_AGENT_ENDPOINT}/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DO_AGENT_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10   # Telegram ждёт ≤10 с
        )
        logger.debug("DO Agent response: %s", r.text)
        logger.debug("DO Agent status: %s", r.status_code)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    ai_answer = _ask_do_agent(openai_messages)

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
