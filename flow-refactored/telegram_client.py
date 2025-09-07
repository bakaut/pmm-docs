"""Telegram API client for the refactored bot.

This module encapsulates all interactions with the Telegram Bot API. Each
method performs a single, well‑named action, adhering to the Clean Code
rule that functions should do one thing and do it well. Special
characters for MarkdownV2 escaping are centralised in a constant.
"""

import json
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from requests import HTTPError
from urllib3.util.retry import Retry

from .config import Config


class TelegramClient:
    """Wrapper around the Telegram Bot API."""

    SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!\\"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = self._create_session()
        self.base_url = f"https://api.telegram.org/bot{self.config.bot_token}"

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=self.config.retry_total,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)
        return session

    def _post(self, method: str, payload: Dict[str, Any]) -> None:
        url = f"{self.base_url}/{method}"
        try:
            resp = self.session.post(url, json=payload, timeout=(self.config.connect_timeout, self.config.read_timeout))
            resp.raise_for_status()
        except HTTPError as e:
            # Log the error at the caller's discretion
            raise

    def escape(self, text: str) -> str:
        """Escape MarkdownV2 special characters."""
        return "".join("\\" + ch if ch in self.SPECIAL_CHARS else ch for ch in text)

    def send_message(self, chat_id: int, text: str, parse_mode: str = "MarkdownV2", disable_preview: bool = True) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        self._post("sendMessage", payload)

    def send_audio(self, chat_id: int, audio_url: str, title: str = "") -> None:
        payload: Dict[str, Any] = {"chat_id": chat_id, "audio": audio_url}
        if title:
            payload["caption"] = title
            payload["title"] = title
        self._post("sendAudio", payload)

    def send_markup(self, chat_id: int, text: str, markup: Dict[str, Any]) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps(markup),
            "parse_mode": "MarkdownV2",
        }
        self._post("sendMessage", payload)

    def answer_callback(self, callback_query_id: str, text: str, show_alert: bool = False) -> None:
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        self._post("answerCallbackQuery", payload)

    def send_chunks(self, chat_id: int, text: str, chunk_size: int = 4096) -> None:
        escaped = self.escape(text)
        for i in range(0, len(escaped), chunk_size):
            self.send_message(chat_id, escaped[i:i + chunk_size])