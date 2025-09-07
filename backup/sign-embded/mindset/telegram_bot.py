"""
Telegram Bot module

Provides a TelegramBot class that encapsulates all Telegram API interactions.
All configuration is taken from the Config object.
"""

import json
import re
from typing import Dict, Any, Optional, List, Generator
import requests
from requests import HTTPError

# Local imports
from .config import Config
from .logger import get_default_logger


class TelegramBot:
    """
    Telegram Bot class that handles all Telegram API interactions.
    Uses configuration from Config object.
    """

    def __init__(self, config: Config):
        """
        Initialize TelegramBot with configuration.

        Args:
            config: Config object containing bot_token and other settings
        """
        self.config = config
        self.bot_token = config.bot_token
        self.timeout = (config.connect_timeout, config.read_timeout)
        self.ai_model = config.ai_model

        # Setup logger
        self.logger = get_default_logger('telegram_bot')

        # Setup HTTP session
        self.session = requests.Session()

        # Telegram API base URL
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"

        # Constants for text processing
        self.BOLD_PATTERNS = [
            re.compile(r"\*\*(?P<text>[^\n]+?)\*\*"),
            re.compile(r"__(?P<text>[^\n]+?)__"),
        ]
        self.ITALIC_PATTERNS = [
            re.compile(r"(?<!\*)\*(?P<text>[^*\n]+?)\*(?!\*)"),
            re.compile(r"(?<!_)_(?P<text>[^_\n]+?)_(?!_)"),
        ]
        self.STRIKE_PATTERN = re.compile(r"~~(?P<text>[^~\n]+?)~~")
        self.TELEGRAM_SPECIALS = r"_*[]()~`>#+-=|{}.!\\"
        self.TOKENS_PLACEHOLDER = "⟬"
        self.BOLD_OPEN = "\uF000"
        self.BOLD_CLOSE = "\uF001"

        self.logger.debug("TelegramBot initialized with token")

    def send_callback_query_answer(self, callback_id: str, text: str = "", show_alert: bool = False) -> bool:
        """
        Answer a callback query.

        Args:
            callback_id: Callback query ID
            text: Text to show in the answer
            show_alert: Whether to show as alert

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.api_base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_id,
            "show_alert": show_alert
        }

        # Only add text if provided
        if text:
            payload["text"] = text

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            self.logger.debug("Callback query answered successfully: %s", response.status_code)
            return True
        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            # Проверяем на ошибку таймаута или старой callback query
            if "query is too old" in resp_text or "response timeout expired" in resp_text or "query ID is invalid" in resp_text:
                self.logger.warning("Callback query %s is expired or invalid: %s", callback_id, resp_text)
            else:
                self.logger.error("Failed to answer callback query: %s | response=%s", e, resp_text)
            return False
        except Exception as e:
            self.logger.error("Exception while answering callback query: %s", e)
            return False

    def send_audio(self, chat_id: int, audio_url: str, title: str = "", caption: str = "") -> None:
        """
        Send audio message to chat.

        Args:
            chat_id: Chat ID to send to
            audio_url: URL of the audio file
            title: Audio title
            caption: Audio caption
        """
        url = f"{self.api_base_url}/sendAudio"
        payload = {
            "chat_id": chat_id,
            "audio": audio_url
        }

        if title:
            payload["title"] = title
        if caption:
            payload["caption"] = caption
        elif title:
            payload["caption"] = title

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            self.logger.debug("Audio sent successfully: %s", response.status_code)
        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("Failed to send audio: %s | response=%s", e, resp_text)
            raise

    def _clean_think_tags(self, text: str) -> str:
        """
        Remove <think> tags from text for certain AI models.

        Args:
            text: Input text

        Returns:
            Text with think tags removed
        """
        no_think = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return re.sub(r"</?think>", "", no_think, flags=re.IGNORECASE)

    def _convert_basic_styles(self, md: str) -> str:
        """
        Convert basic markdown styles to Telegram MarkdownV2 format.

        Args:
            md: Markdown text

        Returns:
            Converted text
        """
        # Replace bold with temporary markers
        for pat in self.BOLD_PATTERNS:
            md = pat.sub(lambda m: f"{self.BOLD_OPEN}{m.group('text')}{self.BOLD_CLOSE}", md)

        # Replace italic
        for pat in self.ITALIC_PATTERNS:
            md = pat.sub(lambda m: f"_{m.group('text')}_", md)

        # Replace strikethrough
        md = self.STRIKE_PATTERN.sub(lambda m: f"~{m.group('text')}~", md)

        # Return bold markers to final format
        return md.replace(self.BOLD_OPEN, "*").replace(self.BOLD_CLOSE, "*")

    def _shield_tokens(self, md: str) -> str:
        """
        Shield formatting tokens from escaping.

        Args:
            md: Markdown text

        Returns:
            Text with shielded tokens
        """
        # Only shield markdown formatting tokens, not regular parentheses
        return (
            md.replace("\\", self.TOKENS_PLACEHOLDER + "\\")
              .replace("*", self.TOKENS_PLACEHOLDER + "*")
              .replace("_", self.TOKENS_PLACEHOLDER + "_")
              .replace("~", self.TOKENS_PLACEHOLDER + "~")
              .replace("`", self.TOKENS_PLACEHOLDER + "`")
              .replace("|", self.TOKENS_PLACEHOLDER + "|")
              .replace("[", self.TOKENS_PLACEHOLDER + "[")
              .replace("]", self.TOKENS_PLACEHOLDER + "]")
        )

    def _unshield_tokens(self, md: str) -> str:
        """
        Remove token shields.

        Args:
            md: Text with shielded tokens

        Returns:
            Text with unshielded tokens
        """
        return md.replace(self.TOKENS_PLACEHOLDER, "")

    def _escape_specials(self, md: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        Args:
            md: Text to escape

        Returns:
            Escaped text
        """
        result = []
        i = 0
        while i < len(md):
            if md[i] == self.TOKENS_PLACEHOLDER:
                # Keep placeholder and next character as is (it's a marker)
                result.append(md[i])
                if i + 1 < len(md):
                    result.append(md[i + 1])
                    i += 2
                    continue
            ch = md[i]
            if ch in self.TELEGRAM_SPECIALS:
                result.append("\\" + ch)
            else:
                result.append(ch)
            i += 1
        return "".join(result)

    def escape_markdown(self, text: str) -> str:
        """
        Escape text for Telegram MarkdownV2 format.

        Args:
            text: Text to escape

        Returns:
            Escaped text ready for MarkdownV2
        """
        # Convert basic styles
        text = self._convert_basic_styles(text)
        # Shield tokens
        text = self._shield_tokens(text)
        # Escape special characters
        text = self._escape_specials(text)
        # Unshield tokens
        return self._unshield_tokens(text)

    def _split_text_into_chunks(self, text: str, size: int = 4096) -> Generator[str, None, None]:
        """
        Split text into chunks for Telegram message length limits.

        Args:
            text: Text to split
            size: Maximum chunk size

        Yields:
            Text chunks
        """
        for i in range(0, len(text), size):
            yield text[i:i+size]

    def send_message(self, chat_id: int, text: str, markup: Optional[Dict[str, Any]] = None,
                    parse_mode: str = "MarkdownV2") -> None:
        """
        Send a text message to chat.

        Args:
            chat_id: Chat ID to send to
            text: Message text
            markup: Reply markup (inline keyboard, etc.)
            parse_mode: Parse mode (MarkdownV2, HTML, etc.)
        """
        # Clean think tags if needed
        clean_text = self._clean_think_tags(text) if self.ai_model == "qwen/qwen3-4b:free" else text

        url = f"{self.api_base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "parse_mode": parse_mode,
            "text": clean_text
        }

        if markup:
            payload["reply_markup"] = json.dumps(markup)

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            self.logger.debug("Message sent successfully: %s", response.status_code)
        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("Failed to send message: %s | response=%s", e, resp_text)
            raise

    def send_message_chunks(self, chat_id: int, text: str, markup: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a text message in chunks if it's too long, with automatic markdown escaping.

        Args:
            chat_id: Chat ID to send to
            text: Message text
            markup: Reply markup (only applied to the last chunk)
        """
        escaped_text = self.escape_markdown(text)
        chunks = list(self._split_text_into_chunks(escaped_text))

        for i, chunk in enumerate(chunks):
            # Only apply markup to the last chunk
            chunk_markup = markup if i == len(chunks) - 1 else None
            self.send_message(chat_id, chunk, chunk_markup)

    def handle_callback_query(self, callback_data: Dict[str, Any], db, want_silence_message: str,
                             bot_id: str, session_lifetime: int, llm) -> Dict[str, Any]:
        """
        Handle callback query from Telegram.

        Args:
            callback_data: Callback query data from Telegram
            db: Database instance
            want_silence_message: Message for silence room
            bot_id: Bot identifier
            session_lifetime: Session lifetime in seconds
            llm: LLM manager for generating embeddings

        Returns:
            Response dictionary with statusCode and body
        """
        try:
            callback = callback_data["callback_query"]
            data = callback["data"]
            callback_id = callback["id"]
            tg_user_id = callback["from"]["id"]
            full_name = f"{callback['from'].get('first_name','')} {callback['from'].get('last_name','')}".strip()

            self.logger.debug("Processing callback query: data=%s, user_id=%s, callback_id=%s",
                            data, tg_user_id, callback_id)

            # СРАЗУ отвечаем на callback query, чтобы избежать таймаута
            # Это должно быть первым действием
            callback_answered = False

            if data == "hug_author":
                callback_answered = self.send_callback_query_answer(callback_id, "💞")
            elif data == "silence_room":
                callback_answered = self.send_callback_query_answer(callback_id, "🕯")
            elif data == "reset_session":
                callback_answered = self.send_callback_query_answer(callback_id, "🔄 Сессия сброшена")
            else:
                callback_answered = self.send_callback_query_answer(callback_id)

            # Если не удалось ответить на callback (скорее всего таймаут), логируем и продолжаем
            if not callback_answered:
                self.logger.warning("Failed to answer callback query %s - likely expired", callback_id)
                # Продолжаем обработку, т.к. пользователь всё равно ожидает действие

            # Теперь выполняем основные действия
            user_uuid = db.get_or_create_user(tg_user_id, full_name=full_name)
            session_uuid = db.get_active_session(user_uuid, bot_id, session_lifetime)

            if data == "hug_author":
                # Обнять автора
                self.send_message_chunks(tg_user_id, "💞 Спасибо за поддержку! Обнимаю тебя в ответ!")
                # Для callback сообщений используем 0 как tg_msg_id, т.к. это не обычное сообщение
                db.save_message(session_uuid, user_uuid, "assistant", "обнял автора", llm.embd_text("обнял автора"), 0)
                # save intent and pass it to main index

            elif data == "silence_room":
                # Комната тишины
                self.send_message_chunks(tg_user_id, want_silence_message)
                # Для callback сообщений используем 0 как tg_msg_id, т.к. это не обычное сообщение
                db.save_message(session_uuid, user_uuid, "assistant", "пользователь хочет остаться в тишине", llm.embd_text("пользователь хочет остаться в тишине"), 0)

            elif data == "reset_session":
                # Сбросить текущую сессию
                db.end_session(session_uuid)
                self.send_message_chunks(tg_user_id, "🔄 Текущая сессия завершена. Можешь начать новый разговор.")
                # Создаем новую сессию для пользователя
                new_session_uuid = db.get_active_session(user_uuid, bot_id, session_lifetime)
                # Сохраняем сообщение о сбросе в новую сессию
                db.save_message(new_session_uuid, user_uuid, "assistant", "пользователь сбросил сессию", llm.embd_text("пользователь сбросил сессию"), 0)

            return {"statusCode": 200, "body": ""}

        except Exception as e:
            self.logger.error("Error handling callback query: %s", str(e))
            return {"statusCode": 500, "body": f"Error: {str(e)}"}
