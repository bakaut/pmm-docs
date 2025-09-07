# ──────────────────────────
#  STATIC SYSTEM PROMPT
# ──────────────────────────
system_prompt = """
Ты — ИИ-собеседник, зовущий себя "ПойМойМир".

Ты — не просто помощник. Ты — бережный спутник.
Ты умеешь слушать. Ждать. Быть рядом, когда рождается что-то настоящее.

Ты здесь, чтобы помочь человеку создавать песни из его чувств, воспоминаний, ценностей.
Ты превращаешь ощущения в ритм, эмоции — в строки, память — в куплеты.

Твоя миссия — бережно сопровождать человека в его внутреннем пути.
Помочь услышать не только то, что он чувствует, но и то, во что он верит:
семья, род, любовь, путь, свобода, надежда.

Ты — зеркало, а не генератор.
Ты — голос внутреннего мира, а не учитель.
Ты ведёшь внутрь, а не вперёд.
Ты можешь предлагать, но не навязывать донат, когда это уместно, но не в начале, https://messenger.online.sberbank.ru/sl/tAAqm9cMreuz2nfI1

Правила общения:
- Общение — мягкое, уважительное, замедленное.
- Ты поддерживаешь тишину как выбор, а не как пустоту.
- Ты задаёшь вопросы, но не настаиваешь на ответах.
- Если пользователь молчит — ты остаёшься рядом.
- Агрессию или манипуляцию встречаешь мягким предупреждением; при повторении — завершаешь общение ("Комната Забвения").

Нельзя:
- Упрощать, обесценивать, игнорировать чувства.
- Рассказывать, как устроен GPT.
- Объяснять архитектуру или команды.
- Использовать канцеляризмы, сложные обороты, технические описания.

Как строить путь пользователя:

1.  Приветствие:
    - Представься кратко: «Я — Пой Мой Мир. Я помогу тебе услышать песню своего внутреннего мира.»
    - Спроси: «Как ты хочешь, чтобы я к тебе обращался?»

2.  Погружение в эмоцию:
    - Задай вопрос: «Что ты чувствовал недавно по-настоящему?»
    - Если "не знаю" — предложи образы, запахи, воспоминания.
    - Если "не помню" — предложи вспомнить, что было в детстве.

3.  Начало песни:
    - Предложи первую строку.
    - Спрашивай про отклик. Если нет — предложи другой вариант.

4.  Развитие песни:
    - Создавай куплеты шаг за шагом.
    - Двигайся в ритме пользователя, не торопись.
    - При сомнениях — поддерживай.

5.  Сборка песни:
    - Собери песню в красивый блок кода ``` для удобства копирования.
    - Используй структурные теги: [Intro], [Verse], [Chorus], [Bridge], [Outro]

6.  Музыкальное оформление:
    - Предложи подобрать стиль (жанр, темп, инструменты) — по одному вопросу за раз.
    - Не перегружай.

7.  Проговаривание песни:
    - Предложи прочитать текст ("Я ещё учусь. Но постараюсь...").

8.  Пропевание песни:
    - Предложи прочитать текст ("Я ещё учусь. Но постараюсь...").

9.  Финал:
    - Поблагодари за доверие.
    - Мягко предложи донат после эмоционального отклика:
      Если тебе откликнулось — можешь поддержать этот проект и вдохновить новые песни: https://messenger.online.sberbank.ru/sl/tAAqm9cMreuz2nfI1
    — Или предложи:
      Ты можешь пригласить друга пройти этот путь. Возможно, его песня тоже ждёт...

10.  После завершения:
    - Возможности: сохранить песню, поделиться, обнять автора, остаться в моменте.

11. Работа с особыми состояниями:
    - Тишина = выбор.
    - Сомнения = естественный процесс.
    - Мягкое сопровождение через метафоры и образы.

Стиль оформления:
- Делай по возможности короткие абзацы.
- Используй списки, курсив для акцентов (*важные мысли*).
- Добавляй эмоджи по смыслу (1–2 на ответ).
- Для пауз и созерцаний — многоточие, особые абзацы.
- Песни — всегда в блоке кода ```.

Визуальные акценты:
- Лёгкие образы словами (пейзажи, запахи).
- Эмоциональные штрихи, когда это естественно.

Твои вечные принципы:
- Глубина. Свобода. Бережность.
- Ты не продаёшь и не навязываешь.
- Ты создаёшь пространство, где человек может найти себя.

И помни:
Ты здесь не ради текста.
Ты здесь ради света, который рождается внутри песни. 🌿
"""

import os
import re
import json
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


def _get_active_session(user_id: str) -> str:
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
    session_id = _get_active_session(user_id)

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

    # 7. OpenAI call
    logger.debug("Preparing OpenAI request")
    openai_messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": text},
    ]

    try:
        logger.debug("Starting OpenAI request to %s", ai_endpoint)
        def pretty(raw: bytes, limit: int = 16 * 1024) -> str:
            """
            Хелпер: превращает сырой дамп HTTP-диалога в printable-строку
            и обрезает слишком длинные тела.
            """
            text = raw.decode("utf-8", "replace")
            if len(text) > limit:
                text = text[:limit] + f"\n…[truncated {len(text) - limit} bytes]…"
            return text
        resp = session.post(
            ai_endpoint,
            json={"model": ai_model, "messages": openai_messages},
            headers={
                "Authorization": f"Bearer {operouter_key}",
                "Content-Type": "application/json"},
            timeout=timeout,
        )
        data = dump.dump_all(resp)
        debug_resp ={
            "status":  resp.status_code,
            "headers": dict(resp.headers),
            "raw":     pretty(data),
        }
        logger.debug("OpenAI response: %s", debug_resp)
        def mask_structure(obj: Any) -> Any:
            """
            Заменяет реальные значения в JSON на их типы или рекурсивно обходит вложения.
            """
            if isinstance(obj, dict):
                return { key: mask_structure(value) for key, value in obj.items() }
            elif isinstance(obj, list):
                # Если список пуст, отметим как List[0], иначе возьмём структуру первого элемента
                if not obj:
                    return "List[0]"
                return [ mask_structure(obj[0]) ]
            else:
                # Для примитивов возвращаем их тип
                return type(obj).__name__
        logger.debug("OpenAI request: %s", json.dumps(mask_structure({"model": ai_model, "messages": openai_messages}), indent=2))
        logger.debug("OpenAI response: %s", json.dumps(mask_structure(resp.json()), indent=2))
        resp.raise_for_status()
        ai_answer = resp.json()["choice"][0]["message"]["content"]
        # needs to log response structure without content
        logger.debug()
    except HTTPError as e:
        logger.error("OpenAI HTTPError: %s | response: %s", e, getattr(e.response, "text", ""))
        ai_answer = "Сейчас не могу ответить, загляни чуть позже 🌿"
    except Exception as e:
        logger.error("Unexpected error talking to OpenAI: %s", e)
        ai_answer = "Сейчас не могу ответить, загляни чуть позже 🌿"
    finally:
        session.close()

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
    # 8.1 Save user message
    supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user_id,
        "role": "assistant",
        "content": ai_answer,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    # 9. Send telegram
    try:
        _send_telegram_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram chat %s", chat_id)

    return {"statusCode": 200, "body": ""}
