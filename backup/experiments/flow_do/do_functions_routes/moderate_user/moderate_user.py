
# requirements.txt
requests
supabase

"""moderate_user.py – DigitalOcean Function (Python 3.11)
=======================================================
Маршрут‑функция для GenAI‑агента / REST клиентов: проверяет, сколько
предупреждений у пользователя в Supabase, выдаёт *первое предупреждение* или
*бан навсегда*, отправляет уведомление в Telegram и возвращает JSON‑ответ,
который агент может сразу передать модели.

✉️ Вход (JSON‑body)  ─────────────────────────────────────────────────────────
{
  "chat_id":          <int>,   // ID Telegram‑чата, где модерация
  "user_id":          <str>,   // Telegram user_id
  "additional_reason":<str>    // опц. причина
}

📤 Выход  ────────────────────────────────────────────────────────────────────
HTTP 200 +
{
  "action_taken": "warn" | "ban" | "noop",  // что сделали
  "warnings":     <int>,                    // итоговое число предупреждений
  "until":        null                      // для совместимости
}

🌿 Окружение (env)  ──────────────────────────────────────────────────────────
BOT_TOKEN       – *обязательно*  – токен Telegram‑бота.
SUPABASE_URL    – *обязательно*  – URL проекта Supabase.
SUPABASE_KEY    – *обязательно*  – service‑role ключ Supabase.
TIMEOUT         – (int) таймаут HTTPS‑запросов, сек (5 по умолчанию).

project.yml (пример)  ───────────────────────────────────────────────────────
name: moderate-user
runtimes:
  python: "3.11"
web: raw    # нужно для event["http"]["body"] без доп. обработки
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import requests
from postgrest import APIError  # type: ignore
from supabase import create_client  # type: ignore

# ──────────────────────────
#  ЛОГИРОВАНИЕ
# ──────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("moderate-user")

# ──────────────────────────
#  ENV VARS & CONSTANTS
# ──────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TIMEOUT = int(os.getenv("TIMEOUT", "5"))

if not all((BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY)):
    raise RuntimeError("Set BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY env vars")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TG_ESCAPE = r"_*[]()~`>#+-=|{}.!\\"
TG_LIMIT = 4096

# ──────────────────────────
#  TELEGRAM HELPERS
# ──────────────────────────

def _tg_escape(text: str) -> str:
    return "".join("\\" + ch if ch in TG_ESCAPE else ch for ch in text)

def _tg_send(chat_id: int, text: str) -> None:
    for i in range(0, len(text), TG_LIMIT):
        chunk = _tg_escape(text[i:i + TG_LIMIT])
        r = requests.post(
            TG_API,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()

# ──────────────────────────
#  CORE LOGIC
# ──────────────────────────

def _get_user_row(tg_user_id: str) -> dict:
    """Возвращает {warnings:int, blocked:bool}. Создаёт строку при отсутствии."""
    try:
        row = (
            supabase.table("tg_users")
            .select("warnings, blocked")
            .eq("id", tg_user_id)
            .maybe_single()
            .execute()
        ) or {}
    except APIError as exc:
        log.error("Supabase error: %s", exc)
        row = {}

    if not row:
        row = {"warnings": 0, "blocked": False}
        supabase.table("tg_users").insert({"id": tg_user_id, **row}).execute()
    return row


def _update_user(tg_user_id: str, **fields):
    try:
        supabase.table("tg_users").update(fields).eq("id", tg_user_id).execute()
    except APIError as exc:
        log.error("Supabase update error: %s", exc)


def moderate_user(chat_id: int, tg_user_id: str, reason: str = "Нарушение правил") -> Tuple[str, int]:
    """Возвращает (action, warnings_after)."""
    row = _get_user_row(tg_user_id)
    warnings, blocked = row["warnings"], row["blocked"]

    if blocked and warnings >= 1:
        return "noop", warnings

    warnings += 1
    action = "warn" if warnings == 1 else "ban"

    if action == "warn":
        msg = (
            "*Первое предупреждение*\n"
            f"- {reason}\n\n"
            "Свобода ≠ вседозволенность.\n"
            "[Правила бота](https://bit.ly/4j7AzIg)\n\n"
            "Повторное нарушение ➜ бан навсегда."
        )
        _update_user(tg_user_id, warnings=warnings)
    else:  # ban
        msg = "Вы перемещены в *Комнату Забвения*. Бан навсегда."
        _update_user(
            tg_user_id,
            warnings=warnings,
            blocked=True,
            blocked_reason=reason,
            blocked_at=datetime.now(timezone.utc).isoformat(),
        )

    _tg_send(chat_id, msg)
    return action, warnings

# ──────────────────────────
#  EVENT PARSING (web: raw)
# ──────────────────────────

def _parse_body(event: Dict[str, Any]) -> Tuple[dict | None, str | None]:
    """Возвращает (payload, err)."""
    body = event.get("http", {}).get("body") or event.get("body")
    if body is None:
        return None, "missing request body"

    if event.get("http", {}).get("isBase64Encoded") or event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body)
        except Exception as exc:  # noqa: BLE001
            return None, f"cannot base64‑decode: {exc}"
    if isinstance(body, bytes):
        body = body.decode()

    try:
        return json.loads(body or "{}"), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"

# ──────────────────────────
#  HANDLER (DigitalOcean Functions)
# ──────────────────────────

def handler(event: Dict[str, Any] | None = None, context: Any | None = None):  # noqa: D401
    """Entrypoint required by DigitalOcean Functions."""
    event = event or {}

    payload, err = _parse_body(event)
    if err:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": err}),
        }

    chat_id = payload.get("chat_id")
    tg_user_id = payload.get("user_id")
    reason = payload.get("additional_reason", "Нарушение правил")

    if not all((chat_id, tg_user_id)):
        return {
            "statusCode": 422,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "chat_id and user_id are required"}),
        }

    try:
        action, warnings = moderate_user(int(chat_id), str(tg_user_id), str(reason))
    except Exception as exc:  # noqa: BLE001
        log.exception("moderate_user failed: %s", exc)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "internal error"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"action_taken": action, "warnings": warnings, "until": None}),
    }

# ──────────────────────────
#  LOCAL DEMO (python moderate_user.py)
# ──────────────────────────
if __name__ == "__main__":  # pragma: no cover
    CHAT_ID = int(os.getenv("TEST_CHAT", "0"))
    TEST_USER = os.getenv("TEST_USER", str(uuid.uuid4()))
    if not CHAT_ID:
        print("Set TEST_CHAT env var with Telegram chat ID for demo run")
    else:
        a, w = moderate_user(CHAT_ID, TEST_USER, "demo run")
        print("action:", a, "warnings:", w)
