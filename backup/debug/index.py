import os
import json
from typing import Dict, Any

import requests
from requests_toolbelt.utils import dump


# ─────────────── конфигурация через переменные окружения ─────────────── #

AI_MODEL     = os.getenv("AI_MODEL", "openai/gpt-4o")
OR_ENDPOINT  = os.getenv("OR_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions")
OR_KEY       = os.getenv("OPENROUTER_KEY")        # обязателен
OA_ENDPOINT  = "https://api.openai.com/v1/chat/completions"
OA_KEY       = os.getenv("OPENAI_KEY")            # опционален
TIMEOUT      = int(os.getenv("TIMEOUT", "30"))

# запрос-заглушка
MESSAGES     = [{"role": "user", "content": "Привет как дела?"}]


# ────────────────────────── служебные функции ────────────────────────── #

def pretty(raw: bytes, limit: int = 16 * 1024) -> str:
    """
    Хелпер: превращает сырой дамп HTTP-диалога в printable-строку
    и обрезает слишком длинные тела.
    """
    text = raw.decode("utf-8", "replace")
    if len(text) > limit:
        text = text[:limit] + f"\n…[truncated {len(text) - limit} bytes]…"
    return text


def call(endpoint: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Делает POST, возвращает словарь с дампом запроса и ответа.
    """
    payload = {"model": AI_MODEL, "messages": MESSAGES}
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=TIMEOUT)
    data = dump.dump_all(resp)
    return {
        "status":  resp.status_code,
        "headers": dict(resp.headers),
        "raw":     pretty(data),
    }


# ─────────────────────────────  handler  ─────────────────────────────── #

def handler(event, context):
    """
    Yandex Cloud Function HTTP handler.

    * event["httpMethod"], event["body"], … — см. документацию к HTTP-триггеру.
    * Возвращаем словарь с ключами: statusCode, headers, body.
    """
    if not OR_KEY:
        return {
            "statusCode": 500,
            "body":       "OPENROUTER_KEY env var is required",
        }

    # 1) вызов через OpenRouter
    or_result = call(
        OR_ENDPOINT,
        {
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type":  "application/json",
            "User-Agent":    "yc-fn-openrouter-debug/1.0",
            "X-Debug":       "1",
        },
    )

    # 2) (опционально) прямой вызов OpenAI
    oa_result = None
    if OA_KEY:
        oa_result = call(
            OA_ENDPOINT,
            {
                "Authorization": f"Bearer {OA_KEY}",
                "Content-Type":  "application/json",
            },
        )

    # собираем JSON-ответ
    body = {
        "openrouter": or_result,
        "openai":     oa_result,
    }

    return {
        "statusCode": 200,
        "headers":    {"Content-Type": "application/json; charset=utf-8"},
        "body":       json.dumps(body, ensure_ascii=False, indent=2),
    }
