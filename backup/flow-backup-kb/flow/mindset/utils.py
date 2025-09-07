# Standard library imports
import base64
import json
import logging
import string
from typing import Any, Dict, Optional, List

# Third-party imports
import requests
from pydantic import TypeAdapter, Base64Bytes, ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Utils:
    """Класс с вспомогательными утилитами для HTTP сессий, парсинга и работы с сообщениями."""

    def __init__(self, config, logger: Optional[logging.Logger] = None):
        """
        Инициализация Utils.

        Args:
            config: Объект конфигурации с настройками для HTTP сессии
            logger: Логгер для записи отладочной информации
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.session = self._create_http_session()

    def _create_http_session(self) -> requests.Session:
        """
        Создает HTTP сессию с настройками retry и адаптерами.

        Returns:
            requests.Session: Настроенная HTTP сессия
        """
        session = requests.Session()
        retries = Retry(
            total=self.config.retry_total,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        self.logger.debug("HTTP session initialised")
        return session

    def get_session(self) -> requests.Session:
        """
        Возвращает настроенную HTTP сессию.

        Returns:
            requests.Session: HTTP сессия
        """
        return self.session

    def parse_body(self, event: Dict[str, Any]) -> Any:
        """
        Универсально разбирает event['body'] из Yandex Cloud (или AWS / GCP):
          • JSON  → dict / list
          • Base-64(JSON) → dict / list
          • Base-64(binary) → bytes
          • голый текст → str

        Args:
            event: Событие с полем 'body'

        Returns:
            Any: Разобранные данные в соответствующем формате
        """
        raw: str | bytes = event.get("body", "")
        b64 = TypeAdapter(Base64Bytes)

        # 1. Пытаемся сразу прочитать JSON
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            pass          # не JSON — едем дальше

        # 2. Пытаемся декодировать Base-64
        #    (неважно, что говорит isBase64Encoded)
        try:
            decoded: bytes = b64.validate_python(raw)
        except ValidationError:
            return raw    # совсем не Base-64 → отдаём как есть (str)

        # 3. Декодировали Base-64 → возможно, внутри JSON?
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            return decoded  # бинарные данные

    def get_last_messages(self, history: List[Dict], count: int = 2, role: Optional[str] = None,
                         force_last_user: bool = False, force_last_assistant: bool = False, 
                         extra_message: Optional[Dict] = None) -> List[Dict]:
        """
        Возвращает последние count сообщений из истории.

        Args:
            history: История сообщений
            count: Количество сообщений для получения
            role: Фильтр по роли ("user" или "assistant")
            force_last_user: Если True и роль не задана, то последнее сообщение обязательно от пользователя
            force_last_assistant: Если True и роль не задана, то последнее сообщение обязательно от ассистента
            extra_message: Дополнительное сообщение для добавления в конец списка

        Returns:
            List[Dict]: Список последних сообщений
        """
        if role:
            filtered = [msg for msg in history if msg["role"] == role]
            result = filtered[-count:]
        elif force_last_user:
            last_user_idx = next((i for i in range(len(history)-1, -1, -1) if history[i]["role"] == "user"), None)
            if last_user_idx is None:
                result = history[-count:]
            else:
                start_idx = max(0, last_user_idx - count + 1)
                result = history[start_idx:last_user_idx+1]
        elif force_last_assistant:
            last_assistant_idx = next((i for i in range(len(history)-1, -1, -1) if history[i]["role"] == "assistant"), None)
            if last_assistant_idx is None:
                result = history[-count:]
            else:
                start_idx = max(0, last_assistant_idx - count + 1)
                result = history[start_idx:last_assistant_idx+1]
        else:
            result = history[-count:]

        if extra_message:
            result = result + [extra_message]

        return result

    def get_reset_filtered_messages(self, messages: List[Dict], reset_phrase: str = "Давай начнём всё с начала") -> List[Dict]:
        """
        Возвращает сообщения начиная с последнего вхождения фразы сброса разговора.

        Args:
            messages: Список сообщений для фильтрации
            reset_phrase: Фраза, которая сбрасывает контекст разговора

        Returns:
            List[Dict]: Список сообщений начиная с последнего вхождения фразы сброса (включительно),
                       или пустой список если фраза не найдена
        """
        if not self.config.enable_conversation_reset:
            return []

        # Ищем последнее вхождение фразы среди всех сообщений
        start_idx = None
        for i in range(len(messages)-1, -1, -1):
            if reset_phrase in messages[i]["content"]:
                start_idx = i
                break

        # Если нашли — берём сообщения начиная с этой фразы (включительно)
        if start_idx is not None:
            return messages[start_idx:]
        else:
            return []  # если не нашли — пустой список

    def compute_message_context(self, history: List[Dict], user_text: str) -> Dict[str, Any]:
        """
        Готовит срезы сообщений для LLM и формирует openai_msgs с учётом возможного сброса контекста.

        Returns dict with keys:
        - last_8_messages
        - last_20_assistant_messages
        - last_5_assistant_messages
        - last_3_assistant_messages
        - last_8_user_messages
        - openai_msgs
        """
        last_50_messages = self.get_last_messages(history, count=50)
        last_8_messages = self.get_last_messages(last_50_messages, count=8, force_last_user=True)
        last_20_assistant_messages = self.get_last_messages(last_50_messages, count=20, role="assistant")
        last_5_assistant_messages = self.get_last_messages(last_50_messages, count=5, role="assistant")
        last_3_assistant_messages = self.get_last_messages(last_50_messages, count=3, role="assistant")
        last_8_user_messages = self.get_last_messages(last_50_messages, count=8, role="user")

        msgs_from_phrase = self.get_reset_filtered_messages(last_50_messages)

        if msgs_from_phrase:
            last_8_messages = self.get_last_messages(msgs_from_phrase, count=8, force_last_user=True)
            last_20_assistant_messages = self.get_last_messages(msgs_from_phrase, count=20, role="assistant")
            last_5_assistant_messages = self.get_last_messages(msgs_from_phrase, count=5, role="assistant")
            last_3_assistant_messages = self.get_last_messages(msgs_from_phrase, count=3, role="assistant")
            last_8_user_messages = self.get_last_messages(msgs_from_phrase, count=8, role="user")
            openai_msgs = [
                {"role": "system", "content": self.config.system_prompt},
                *msgs_from_phrase,
                {"role": "user", "content": user_text}
            ]
        else:
            openai_msgs = [
                {"role": "system", "content": self.config.system_prompt},
                *history,
                {"role": "user", "content": user_text}
            ]

        return {
            "last_8_messages": last_8_messages,
            "last_20_assistant_messages": last_20_assistant_messages,
            "last_5_assistant_messages": last_5_assistant_messages,
            "last_3_assistant_messages": last_3_assistant_messages,
            "last_8_user_messages": last_8_user_messages,
            "openai_msgs": openai_msgs,
        }

    def flatten_messages(self, messages_input: Any, count: int = 8) -> Dict[str, List[str]]:
        """
        Универсальный метод для создания сплющенной структуры сообщений с нумерацией.
        Может обрабатывать различные форматы входных данных.

        Args:
            messages_input: Входные данные - может быть списком сообщений, словарем контекста, или другой структурой
            count: Количество сообщений для обработки (по умолчанию 8)

        Returns:
            Dict[str, List[str]]: Словарь с ключами "user" и "assistant",
                                содержащий пронумерованные сообщения
        """
        messages = []

        # Определяем тип входных данных и извлекаем сообщения
        if isinstance(messages_input, list):
            # Если это уже список сообщений
            messages = messages_input
        elif isinstance(messages_input, dict):
            # Если это словарь, ищем сообщения в различных ключах
            if "last_8_messages" in messages_input:
                messages = messages_input["last_8_messages"]
            elif "openai_msgs" in messages_input:
                # Исключаем системные сообщения
                messages = [msg for msg in messages_input["openai_msgs"] if msg.get("role") != "system"]
            elif "messages" in messages_input:
                messages = messages_input["messages"]
            elif "history" in messages_input:
                messages = messages_input["history"]
            else:
                # Если это прямая структура сообщений с ролями
                if all(isinstance(v, list) for v in messages_input.values()):
                    # Уже сплющенная структура - объединяем обратно
                    for role, msgs in messages_input.items():
                        for msg in msgs:
                            # Убираем нумерацию если она есть
                            content = msg
                            if isinstance(msg, str) and '. ' in msg and msg.split('. ', 1)[0].isdigit():
                                content = msg.split('. ', 1)[1]
                            messages.append({"role": role, "content": content})
                else:
                    # Преобразуем словарь в список сообщений
                    for key, value in messages_input.items():
                        if isinstance(value, (str, list)):
                            content = value if isinstance(value, str) else ' '.join(str(v) for v in value)
                            messages.append({"role": "user", "content": content})
        else:
            # Если это строка или другой тип
            content = str(messages_input)
            messages = [{"role": "user", "content": content}]

        # Берем последние count сообщений
        last_messages = messages[-count:] if len(messages) > count else messages

        user_messages = []
        assistant_messages = []

        # Собираем сообщения по ролям
        for msg in last_messages:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content = msg.get("content", str(msg))

            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                assistant_messages.append(content)

        # Нумеруем сообщения
        numbered_user = [f"{i+1}. {content}" for i, content in enumerate(user_messages)]
        numbered_assistant = [f"{i+1}. {content}" for i, content in enumerate(assistant_messages)]

        return {
            "user": numbered_user,
            "assistant": numbered_assistant
        }

    def _is_base64(self, s: str) -> bool:
        """
        Check if a string is likely base64 encoded with improved validation.

        Args:
            s: String to check

        Returns:
            bool: True if string appears to be base64 encoded
        """
        if not s or len(s) < 4:
            return False

        # Base64 strings should be divisible by 4 (with padding)
        if len(s) % 4 != 0:
            return False

        # Check if string contains only valid base64 characters
        valid_chars = string.ascii_letters + string.digits + '+/='
        if not all(c in valid_chars for c in s):
            return False

        # Additional heuristics to avoid false positives:
        # 1. Common words that aren't base64
        common_words = {'text', 'user', 'tenant', 'created_at', 'embedding', 'identifier', 'attribute'}
        if s.lower() in common_words:
            return False

        # 2. If it's a short string without padding, probably not base64
        if len(s) < 8 and not s.endswith('='):
            return False

        # 3. If it looks like a number, probably not base64
        if s.replace('.', '').replace('-', '').isdigit():
            return False

        # Try to decode to verify it's valid base64
        try:
            decoded_bytes = base64.b64decode(s, validate=True)

            # Check if decoded content is reasonable:
            # 1. Not too short (avoid single chars)
            if len(decoded_bytes) < 2:
                return False

            # 2. Try UTF-8 decoding with strict error handling
            try:
                decoded_str = decoded_bytes.decode('utf-8', errors='strict')
                # 3. Check if decoded content looks like meaningful text
                # (printable ASCII or reasonable UTF-8)
                if not decoded_str or not decoded_str.isprintable():
                    return False
                # 4. Avoid very short decoded strings that could be coincidental
                if len(decoded_str) < 2:
                    return False
                return True
            except UnicodeDecodeError:
                # If it can't be decoded as UTF-8, it's probably not text-based base64
                return False

        except Exception:
            return False

    def _try_decode_base64(self, s: str) -> str:
        """
        Try to decode a base64 string with improved error handling.

        Args:
            s: String that might be base64 encoded

        Returns:
            str: Decoded string if successful, original string otherwise
        """
        if not self._is_base64(s):
            return s

        try:
            decoded_bytes = base64.b64decode(s, validate=True)
            # Use strict UTF-8 decoding to catch invalid sequences early
            decoded_str = decoded_bytes.decode('utf-8', errors='strict')
            self.logger.debug("Successfully decoded base64 '%s' -> '%s'", s[:20] + '...' if len(s) > 20 else s, decoded_str)
            return decoded_str
        except UnicodeDecodeError as e:
            self.logger.debug("Base64 decoded but contains invalid UTF-8 sequence in '%s': %s", s[:20] + '...' if len(s) > 20 else s, e)
            return s
        except Exception as e:
            self.logger.debug("Failed to decode base64 '%s': %s", s[:20] + '...' if len(s) > 20 else s, e)
            return s

    def _escape_search_text(self, text: str) -> str:
        """
        Escape text for RedisSearch full-text queries.

        Args:
            text: Raw search text

        Returns:
            str: Escaped text safe for RedisSearch
        """
        if not text:
            return text

        # RedisSearch special characters that need escaping in text queries
        # Keep it minimal - too much escaping can break search
        special_chars = ['(', ')', '{', '}', '[', ']', '"', "'", '\\', '/', '*', '?', ':', '!', '^', '~']

        escaped = text
        for char in special_chars:
            escaped = escaped.replace(char, '\\' + char)

        return escaped
