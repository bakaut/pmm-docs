"""Utility functions used across the bot.

These functions are intentionally kept small and descriptive. They adhere
to the Clean Code rules of meaningful names and single responsibility.
"""

import json
from typing import Any, Dict, Iterable, List, Optional

from pydantic import Base64Bytes, ValidationError, TypeAdapter


def parse_body(event: Dict[str, Any]) -> Any:
    """Parse the body of an event from Yandex/AWS/GCP.

    The body may be plain JSON, base64‑encoded JSON, base64‑encoded binary
    or raw text. The return type matches the decoded content.
    """
    raw: str | bytes = event.get('body', '')
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


def get_last_messages(history: List[Dict[str, str]], count: int, role: Optional[str] = None, force_last_user: bool = False, extra_message: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """Return the last N messages from a history with optional filtering.

    * When ``role`` is provided, only messages with that role are returned.
    * If ``force_last_user`` is True and no role is specified, ensure that
      the last message is from the user if possible.
    * ``extra_message`` is appended to the result if provided.
    """
    if role:
        filtered = [msg for msg in history if msg.get('role') == role]
        result = filtered[-count:]
    elif force_last_user:
        last_user_idx = next((i for i in range(len(history) - 1, -1, -1) if history[i].get('role') == 'user'), None)
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