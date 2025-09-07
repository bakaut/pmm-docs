
import os
import json
import logging
from pythonjsonlogger import jsonlogger
import requests
from typing import Any, Dict, Optional

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
DO_TG_TOKEN          = os.getenv("DO_TG_TOKEN")           # токен @BotFather
DO_AGENT_ENDPOINT    = os.getenv("DO_AGENT_ENDPOINT")  # https://<agent>.ondigitalocean.app
DO_AGENT_KEY         = os.getenv("DO_AGENT_KEY")       # access-key агента


# ──────────────────────────
SPECIAL = r"_*[]()~`>#+-=|{}.!\\"

# ---------- helpers ---------- #
def tg_escape(text: str) -> str:
    return "".join("\\" + ch if ch in SPECIAL else ch for ch in text)

def chunks(text, size=4096): # лимит Telegram
    for i in range(0, len(text), size):
        yield text[i:i+size]

def _send_telegram(chat_id: int, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "disable_web_page_preview": True,
        "parse_mode": "MarkdownV2",
        "text": text
    }

    url = f"https://api.telegram.org/bot{DO_TG_TOKEN}/sendMessage"
    r = requests.post(url, json=payload)
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


def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)

    """HTTP-обработчик Cloud Function."""
    try:
        update = json.loads(event["body"])
    except (KeyError, json.JSONDecodeError):
        logging.warning("bad request: %s", event)
        return _resp(400, "bad request")

    # вытаскиваем входящее сообщение
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        # Telegram может слать service-updates; игнорируем
        return _resp(200, "no text")

    chat_id = msg["chat"]["id"]
    user_text = msg["text"]

    # ----------------  запрос к DO Agent  ----------------
    try:
        ai_answer = _ask_do_agent(user_text)
    except Exception as exc:
        logging.exception("DO agent error: %s", exc)
        ai_answer = "Сейчас не могу ответить, загляни чуть позже 🌿"

    # ----------------  ответ Telegram-у  -----------------
    try:
        _send_telegram_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram chat %s", chat_id)
    return _resp(200, "ok")


# ---------- helpers ----------

def _ask_do_agent(text: str) -> str:
    """Отправляем юзерский текст агенту и возвращаем content первого choice."""
    payload = {
        "messages": [{"role": "user", "content": text}],
        "stream": False
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


def _resp(code: int, body: str):
    """YCF HTTP-ответ."""
    return {
        "statusCode": code,
        "headers": {"Content-Type": "text/plain; charset=utf-8"},
        "body": body
    }
