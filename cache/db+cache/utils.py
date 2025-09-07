# Standard library imports
import base64
import hashlib
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
                         force_last_user: bool = False, extra_message: Optional[Dict] = None) -> List[Dict]:
        """
        Возвращает последние count сообщений из истории.

        Args:
            history: История сообщений
            count: Количество сообщений для получения
            role: Фильтр по роли ("user" или "assistant")
            force_last_user: Если True и роль не задана, то последнее сообщение обязательно от пользователя
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

    def compute_message_context(self, history: List[Dict], user_text: str, cache_manager=None, tenant: str = None, user_id: str = None) -> Dict[str, Any]:
        """
        Готовит срезы сообщений для LLM и формирует openai_msgs с учётом возможного сброса контекста.
        Также создает сплющенную структуру сообщений с нумерацией и поддерживает инкрементальное кеширование.

        Стратегия кеширования:
        - Кеширует стабильные сегменты сообщений (first 6 из last 8)
        - При новом сообщении: берет кешированные 6 + добавляет 2 новых
        - Инвалидирует кеш только при значительных изменениях контекста

        Args:
            history: История сообщений
            user_text: Текущий текст пользователя
            cache_manager: Менеджер кеша для оптимизации
            tenant: Идентификатор тенанта для кеширования
            user_id: Идентификатор пользователя для кеширования

        Returns dict with keys:
        - last_8_messages
        - last_20_assistant_messages
        - last_5_assistant_messages
        - last_3_assistant_messages
        - last_8_user_messages
        - openai_msgs
        - last_8_messages_flat: инкрементально кешируемая сплющенная структура
        """
        last_50_messages = self.get_last_messages(history, count=50)
        last_8_messages = self.get_last_messages(last_50_messages, count=8, force_last_user=True)
        last_10_messages = self.get_last_messages(last_50_messages, count=10)
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

        # Создаем сплющенную структуру сообщений из last_8_messages
        user_messages = []
        assistant_messages = []

        # Собираем сообщения по ролям из last_10_messages
        for msg in last_10_messages:
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

        last_10_messages_flat = {
            "user": numbered_user,
            "assistant": numbered_assistant
        }

        return {
            "last_8_messages": last_8_messages,
            "last_20_assistant_messages": last_20_assistant_messages,
            "last_5_assistant_messages": last_5_assistant_messages,
            "last_3_assistant_messages": last_3_assistant_messages,
            "last_8_user_messages": last_8_user_messages,
            "openai_msgs": openai_msgs,
            "last_10_messages_flat": last_10_messages_flat,
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

    def create_content_signature(self, *args: Any, prefix: str = "", length: int = 16) -> str:
        """
        Create a consistent hash signature from multiple arguments.
        
        Useful for generating cache keys, signatures, or identifiers
        based on multiple input parameters.
        
        Args:
            *args: Variable arguments to include in signature
            prefix: Optional prefix for the signature
            length: Length of the hash portion (default 16)
            
        Returns:
            str: Hash signature in format 'prefix:hash' or just 'hash'
        """
        # Convert all arguments to strings and join
        content_parts = []
        for arg in args:
            if isinstance(arg, (dict, list)):
                content_parts.append(json.dumps(arg, sort_keys=True, ensure_ascii=False))
            else:
                content_parts.append(str(arg))
        
        content_string = ":".join(content_parts)
        
        # Generate SHA1 hash and truncate to specified length
        hash_signature = hashlib.sha1(content_string.encode('utf-8')).hexdigest()[:length]
        
        if prefix:
            return f"{prefix}:{hash_signature}"
        return hash_signature
