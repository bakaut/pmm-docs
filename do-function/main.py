# __main__.py – DigitalOcean Function‑прокси к OpenAI
"""OpenAI Proxy (DigitalOcean Functions, Python 3.11)
====================================================

► **Назначение**  
Прозрачная прокси‑функция: принимает payload, совместимый с
`POST /v1/chat/completions`, и отдаёт клиенту неизменённый ответ OpenAI.

► **Почему так**  
* Реализовано строго по официальной документации DigitalOcean Functions
  (Python runtime, обновл. 17 апреля 2025) – handler `main(event, context)`
  должен возвращать словарь с полями `body / statusCode / headers`. ([docs.digitalocean.com](https://docs.digitalocean.com/products/functions/reference/runtimes/python/))
* Для гарантированного доступа к оригинальному JSON‑телу укажите в
  `project.yml` опцию `web: raw`; тогда тело доступно как
  `event["http"]["body"]`. citeturn6view0
* Используем `requests`, уже встроенный в runtime 3.11, поэтому дополнительных
  зависимостей не нужно.

-----------------------------------------------------
Требования окружения
-----------------------------------------------------
`OPENAI_API_KEY` (обязательно) — секретный ключ OpenAI.
`OPENAI_ORG_ID`       (опц.) — если нужен заголовок `OpenAI-Organization`.
`OPENAI_BASE_URL`     (опц.) — альтернативный хост, по умолчанию
                         `https://api.openai.com/v1`.
`HTTPS_PROXY`          (опц.) — стандартная переменная для исходящего прокси,
                         например `https://user:pass@proxy:3128`.

-----------------------------------------------------
Код функции
-----------------------------------------------------
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Tuple

import requests

# ---------------------------------------------------------------------------
# Константы и валидация окружения
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Environment variable OPENAI_API_KEY is required")

OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
CHAT_COMPLETIONS_ENDPOINT = f"{BASE_URL.rstrip('/')}/chat/completions"

REQUEST_TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _extract_json_payload(event: Dict[str, Any]) -> Tuple[Dict[str, Any] | None, str | None]:
    """Возвращает (payload_dict, err_msg). Если err_msg не None – ошибка."""

    # web: raw — тело лежит в event["http"]["body"], может быть base64
    http = event.get("http")
    if http and "body" in http:
        raw_body = http["body"]
        if http.get("isBase64Encoded"):
            try:
                raw_body = base64.b64decode(raw_body).decode()
            except Exception as exc:  # eslint‑disable‑line broad‑except
                return None, f"failed to base64‑decode body: {exc}"
        try:
            return json.loads(raw_body or "{}"), None
        except json.JSONDecodeError as exc:
            return None, f"body is not valid JSON: {exc}"

    # web: true (parsed). Ищем стандартные ключи ChatCompletion.
    CANDIDATE_KEYS = {
        "model",
        "messages",
        "temperature",
        "top_p",
        "n",
        "stream",
        "stop",
        "max_tokens",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "user",
        "functions",
        "function_call",
    }
    payload = {k: event[k] for k in CANDIDATE_KEYS if k in event}
    if payload:
        return payload, None

    return None, "request body not found; ensure project.yml has `web: raw` or send JSON fields at top level"


def _proxy_to_openai(payload: Dict[str, Any]) -> requests.Response:
    """Собирает и выполняет POST в OpenAI."""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = OPENAI_ORG_ID

    response = requests.post(
        CHAT_COMPLETIONS_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    return response


# ---------------------------------------------------------------------------
# Handler DigitalOcean Functions
# ---------------------------------------------------------------------------

def main(event: Dict[str, Any] | None = None, context: Any | None = None) -> Dict[str, Any]:
    """Entry‑point, вызываемый платформой.

    Parameters
    ----------
    event : dict | None
        HTTP‑событие (см. docs), либо пустой словарь.
    context : object | None
        Контекст выполнения (не используется).
    """
    event = event or {}

    payload, err = _extract_json_payload(event)
    if err:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": err}),
            "headers": {"Content-Type": "application/json"},
        }

    try:
        resp = _proxy_to_openai(payload)
    except requests.Timeout:
        return {
            "statusCode": 504,
            "body": json.dumps({"error": "OpenAI request timed out"}),
            "headers": {"Content-Type": "application/json"},
        }
    except requests.RequestException as exc:
        return {
            "statusCode": 502,
            "body": json.dumps({"error": str(exc)}),
            "headers": {"Content-Type": "application/json"},
        }

    # Пробрасываем ответ OpenAI клиенту
    return {
        "statusCode": resp.status_code,
        "headers": {
            "Content-Type": resp.headers.get("Content-Type", "application/json"),
        },
        "body": resp.text,  # DO не сериализует строку повторно
    }


# ---------------------------------------------------------------------------
# Локальный запуск (python __main__.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover – удобство отладки
    import uvicorn  # type: ignore
    from fastapi import FastAPI, Request  # type: ignore
    from fastapi.responses import JSONResponse, Response  # type: ignore

    app = FastAPI()

    @app.post("/")
    async def root(req: Request):
        body = await req.body()
        event = {
            "http": {
                "body": body.decode(),
                "method": "POST",
            }
        }
        result = main(event)
        return Response(
            content=result.get("body", ""),
            status_code=int(result.get("statusCode", 200)),
            media_type=result.get("headers", {}).get("Content-Type", "application/json"),
        )

    uvicorn.run(app, host="0.0.0.0", port=8000)
