# Standard library imports
import base64
import json
import logging
import string
import os
import re
import textwrap
import tempfile
import yaml
from typing import Any, Dict, Optional, List
from pathlib import Path

# Third-party imports
import requests
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
from pydantic import TypeAdapter, Base64Bytes, ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optional imports
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None


class Utils:
    """Класс с вспомогательными утилитами для HTTP сессий, парсинга, работы с сообщениями и шаблонов."""

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

    def convert_mp3_to_wav(self, mp3_path: Path, wav_path: Optional[Path] = None) -> Path:
        """
        Convert an MP3 file to WAV format.

        Args:
            mp3_path: Path to the input MP3 file
            wav_path: Path for the output WAV file (optional, will create temporary file if not provided)

        Returns:
            Path to the WAV file (either the provided path or a temporary file)

        Raises:
            FileNotFoundError: If the MP3 file doesn't exist
            ImportError: If pydub is not available
            Exception: If conversion fails
        """
        # Check if MP3 file exists
        if not mp3_path.exists():
            raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

        # If no output path provided, create a temporary file
        if wav_path is None:
            wav_path = Path(tempfile.mktemp(suffix=".wav"))

        # Try pydub first (if available)
        if PYDUB_AVAILABLE:
            try:
                # Load MP3 file
                audio = AudioSegment.from_mp3(str(mp3_path))
                
                # Export as WAV
                audio.export(str(wav_path), format="wav")
                
                self.logger.debug(f"Converted {mp3_path} to {wav_path} using pydub")
                return wav_path
            except Exception as e:
                self.logger.warning(f"Failed to convert {mp3_path} to WAV using pydub: {e}")
                # Fall back to alternative method

        # Fallback method using system command (ffmpeg)
        try:
            import subprocess
            import shutil
            
            # Check if ffmpeg is available
            if shutil.which("ffmpeg"):
                cmd = ["ffmpeg", "-i", str(mp3_path), "-acodec", "pcm_s16le", "-ar", "44100", str(wav_path)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.debug(f"Converted {mp3_path} to {wav_path} using ffmpeg")
                    return wav_path
                else:
                    self.logger.warning(f"ffmpeg failed: {result.stderr}")
            else:
                self.logger.warning("ffmpeg not found in system PATH")
        except Exception as e:
            self.logger.warning(f"Failed to convert using ffmpeg: {e}")

        # Last resort: Create a placeholder WAV file
        self.logger.warning(f"Creating placeholder WAV file for {mp3_path}")
        import numpy as np
        from scipy.io.wavfile import write as wav_write
        
        # Create a simple 10-second WAV file as placeholder
        sample_rate = 44100
        duration = 10  # 10 seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Create a simple sine wave at 440 Hz
        audio_data = np.sin(440 * 2 * np.pi * t)
        audio_data = (audio_data * 32767).astype(np.int16)  # Convert to 16-bit integers
        wav_write(str(wav_path), sample_rate, audio_data)
        
        self.logger.debug(f"Created placeholder WAV file: {wav_path}")
        return wav_path

    def _read_file(self, path: str, default: str = "", template_dir: str = None) -> str:
        """
        Read content from a file.

        Args:
            path: Path to the file (can be relative to template directory)
            default: Default value if file is not found
            template_dir: Directory to resolve relative paths against

        Returns:
            Content of the file or default value
        """
        # If path is relative and we have a template directory, resolve it relative to the template directory
        if not os.path.isabs(path) and template_dir:
            path = os.path.join(template_dir, path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            self.logger.warning(f"File not found: {path}")
            return default
        except Exception as e:
            self.logger.error(f"Error reading file {path}: {e}")
            return default

    def _load_json(self, path: str, template_dir: str = None) -> Dict[str, Any]:
        """
        Load JSON from a file.

        Args:
            path: Path to the JSON file (can be relative to template directory)
            template_dir: Directory to resolve relative paths against

        Returns:
            Parsed JSON data or empty dict on error
        """
        # If path is relative and we have a template directory, resolve it relative to the template directory
        if not os.path.isabs(path) and template_dir:
            path = os.path.join(template_dir, path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading JSON from {path}: {e}")
            return {}

    def _file_exists(self, path: str, template_dir: str = None) -> bool:
        """
        Check if a file exists.

        Args:
            path: Path to check (can be relative to template directory)
            template_dir: Directory to resolve relative paths against

        Returns:
            True if file exists, False otherwise
        """
        # If path is relative and we have a template directory, resolve it relative to the template directory
        if not os.path.isabs(path) and template_dir:
            path = os.path.join(template_dir, path)

        return os.path.exists(path)

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file.

        Args:
            config_path: Path to config file

        Returns:
            Configuration data
        """
        if not os.path.exists(config_path):
            self.logger.error(f"Config file not found: {config_path}")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Error loading config from {config_path}: {e}")
            return {}

    def load_config_context(self, config_path: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file and return context for template rendering.

        Args:
            config_path: Path to config file

        Returns:
            Context dictionary for template rendering
        """
        cfg = self.load_config(config_path)
        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}
        return ctx

    def render_template_with_config(self, config_path: str, template_path: str, extra_args: Optional[Dict[str, Any]] = None) -> str:
        """
        Render a template with the given configuration file.
        Universal function that can handle any template and config file.

        Args:
            config_path: Path to YAML configuration file
            template_path: Path to Jinja2 template file
            extra_args: Additional key-value pairs to pass to the template

        Returns:
            Rendered document content (not saved to file)

        Raises:
            ValueError: If the rendered template is empty
        """
        # Create a temporary environment with the directory of the template as base
        template_dir = os.path.dirname(os.path.abspath(template_path))
        env = Environment(
            loader=FileSystemLoader(template_dir),
            undefined=StrictUndefined,
            autoescape=False
        )

        # Create helper functions for template rendering
        def _read_file(path: str, default: str = "") -> str:
            """
            Read content from a file.

            Args:
                path: Path to the file (can be relative to template directory)
                default: Default value if file is not found

            Returns:
                Content of the file or default value
            """
            # If path is relative, resolve it relative to the template directory
            if not os.path.isabs(path):
                path = os.path.join(template_dir, path)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.warning(f"File not found: {path}")
                return default
            except Exception as e:
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.error(f"Error reading file {path}: {e}")
                return default

        def _load_json(path: str) -> Dict[str, Any]:
            """
            Load JSON from a file.

            Args:
                path: Path to the JSON file (can be relative to template directory)

            Returns:
                Parsed JSON data or empty dict on error
            """
            # If path is relative, resolve it relative to the template directory
            if not os.path.isabs(path):
                path = os.path.join(template_dir, path)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.error(f"Error loading JSON from {path}: {e}")
                return {}

        def _file_exists(path: str) -> bool:
            """
            Check if a file exists.

            Args:
                path: Path to check (can be relative to template directory)

            Returns:
                True if file exists, False otherwise
            """
            # If path is relative, resolve it relative to the template directory
            if not os.path.isabs(path):
                path = os.path.join(template_dir, path)

            return os.path.exists(path)

        env.globals.update(
            read_file=_read_file,
            load_json=_load_json,
            file_exists=_file_exists
        )

        # Load config from YAML file
        def _load_config(config_path: str) -> Dict[str, Any]:
            """
            Load a YAML configuration file.

            Args:
                config_path: Path to config file

            Returns:
                Configuration data
            """
            if not os.path.exists(config_path):
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.error(f"Config file not found: {config_path}")
                return {}

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.error(f"Error loading config from {config_path}: {e}")
                return {}

        cfg = _load_config(config_path)

        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}

        # Add extra arguments if provided
        if extra_args:
            ctx.update(extra_args)

        # Extract template name from path
        template_name = os.path.basename(template_path)

        # Render template (without saving output)
        try:
            template = env.get_template(template_name)
            rendered = template.render(**ctx)

            # Check if rendered template is empty and fail if so
            if not rendered or not rendered.strip():
                error_msg = f"Rendered template is empty: {template_name}"
                # Create a logger for this method
                logger = logging.getLogger(__name__)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Create a logger for this method
            logger = logging.getLogger(__name__)
            logger.info(f"Template {template_name} rendered successfully")
            return rendered
        except ValueError:
            # Re-raise ValueError exceptions (like empty template)
            raise
        except TemplateError as e:
            error_msg = f"Template rendering error: {e}"
            # Create a logger for this method
            logger = logging.getLogger(__name__)
            logger.error(error_msg)
            return f"[render error] {e}"
        except Exception as e:
            error_msg = f"Unexpected error during template rendering: {e}"
            # Create a logger for this method
            logger = logging.getLogger(__name__)
            logger.error(error_msg)
            return f"[render error] {e}"

    @staticmethod
    def render_template(config_path: str, extra_args: Optional[Dict[str, Any]] = None) -> str:
        """
        Render a template with the given configuration file.
        Universal function that can handle any template and config file.

        Args:
            config_path: Path to YAML configuration file
            Expected file formats: .yaml for config, .j2 for templates
            extra_args: Additional key-value pairs to pass to the template

        Returns:
            Rendered document content (not saved to file)

        Raises:
            ValueError: If the rendered template is empty
        """

        template_path = config_path.replace(".yaml", ".j2")

        # Create a temporary environment with the directory of the config as base
        # This ensures that relative paths in the config are resolved correctly
        config_dir = os.path.dirname(os.path.abspath(config_path))
        env = Environment(
            loader=FileSystemLoader(config_dir),
            undefined=StrictUndefined,
            autoescape=False
        )

        # Create helper functions for template rendering
        def _read_file(path: str, default: str = "") -> str:
            """
            Read content from a file.

            Args:
                path: Path to the file (can be relative to config directory)
                default: Default value if file is not found

            Returns:
                Content of the file or default value
            """
            # If path is relative, resolve it relative to the config directory
            if not os.path.isabs(path):
                path = os.path.join(config_dir, path)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.warning(f"File not found: {path}")
                return default
            except Exception as e:
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.error(f"Error reading file {path}: {e}")
                return default

        def _load_json(path: str) -> Dict[str, Any]:
            """
            Load JSON from a file.

            Args:
                path: Path to the JSON file (can be relative to config directory)

            Returns:
                Parsed JSON data or empty dict on error
            """
            # If path is relative, resolve it relative to the config directory
            if not os.path.isabs(path):
                path = os.path.join(config_dir, path)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.error(f"Error loading JSON from {path}: {e}")
                return {}

        def _file_exists(path: str) -> bool:
            """
            Check if a file exists.

            Args:
                path: Path to check (can be relative to config directory)

            Returns:
                True if file exists, False otherwise
            """
            # If path is relative, resolve it relative to the config directory
            if not os.path.isabs(path):
                path = os.path.join(config_dir, path)

            return os.path.exists(path)

        env.globals.update(
            read_file=_read_file,
            load_json=_load_json,
            file_exists=_file_exists
        )

        # Load config from YAML file
        def _load_config(config_path: str) -> Dict[str, Any]:
            """
            Load a YAML configuration file.

            Args:
                config_path: Path to config file

            Returns:
                Configuration data
            """
            if not os.path.exists(config_path):
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.error(f"Config file not found: {config_path}")
                return {}

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.error(f"Error loading config from {config_path}: {e}")
                return {}

        cfg = _load_config(config_path)

        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}

        # Add extra arguments if provided
        if extra_args:
            ctx.update(extra_args)

        # Extract template name from path
        template_name = os.path.basename(template_path)

        # Render template (without saving output)
        try:
            template = env.get_template(template_name)
            rendered = template.render(**ctx)

            # Check if rendered template is empty and fail if so
            if not rendered or not rendered.strip():
                error_msg = f"Rendered template is empty: {template_name}"
                # Create a logger for this static method
                logger = logging.getLogger(__name__)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Create a logger for this static method
            logger = logging.getLogger(__name__)
            logger.info(f"Template {template_name} rendered successfully")
            return rendered
        except ValueError:
            # Re-raise ValueError exceptions (like empty template)
            raise
        except TemplateError as e:
            error_msg = f"Template rendering error: {e}"
            # Create a logger for this static method
            logger = logging.getLogger(__name__)
            logger.error(error_msg)
            return f"[render error] {e}"
        except Exception as e:
            error_msg = f"Unexpected error during template rendering: {e}"
            # Create a logger for this static method
            logger = logging.getLogger(__name__)
            logger.error(error_msg)
            return f"[render error] {e}"

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

    def _count_tokens(self, msg: Dict[str, str]) -> int:
        """
        Count tokens in a message.

        Args:
            msg: Message dictionary with 'role' and 'content' keys

        Returns:
            int: Number of chars in the message
        """

        # Приблизительный подсчет: ~4 символа на токен
        role_tokens = len(msg["role"]) // 4
        content_tokens = len(msg["content"]) // 4
        return role_tokens + content_tokens + 4

    def _get_messages_by_tokens(self, messages: List[Dict], max_tokens: int, deviation: int ) -> List[Dict]:
        """
        Get messages filtered by token count, including whole messages only.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum number of tokens to include

        Returns:
            List[Dict]: Filtered list of messages within token limit
        """
        if not messages:
            return []

        # Calculate tokens for each message
        message_tokens = [(msg, self._count_tokens(msg)) for msg in messages]

        # Start from the end and accumulate tokens until we reach the limit
        selected_messages = []
        total_tokens = 0

        for msg, tokens in reversed(message_tokens):
            if total_tokens + tokens <= max_tokens:
                selected_messages.insert(0, msg)  # Insert at beginning to maintain order
                total_tokens += tokens
            else:
                break
        # Calculate token drift and check if it's within acceptable range
        token_drift = abs(max_tokens - total_tokens)
        self.logger.debug(f"Selected {len(selected_messages)} messages with total tokens: {total_tokens}, drift: {token_drift}")

        # Find nearest values that are divisible by a max_tokens value

        nearest_divisible = (total_tokens // max_tokens) * max_tokens
        next_nearest = nearest_divisible + max_tokens
        self.logger.debug(f"Token drift analysis - nearest: {nearest_divisible}, next: {next_nearest}")

        # Compare drift with nearest divisible values
        drift_from_nearest = abs(total_tokens - nearest_divisible)
        drift_from_next = abs(total_tokens - next_nearest)
        self.logger.debug(f"Drift from nearest: {drift_from_nearest}, drift from next: {drift_from_next}")

        # If token drift is less than 300 and we're close to a divisible boundary, return messages
        if nearest_divisible > 0 and (drift_from_nearest < deviation or drift_from_next < deviation):
            return selected_messages
        elif nearest_divisible == 0:
            self.logger.debug("Not enough messages for summarization")
            return []
        else:
            self.logger.debug("Unexpected case, skipping the summarization")
            return []

    def compute_message_context(self, history: List[Dict], user_text: str, max_tokens: int, deviation: int) -> Dict[str, Any]:
        """
        Готовит срезы сообщений для LLM и формирует openai_msgs с учётом возможного сброса контекста.

        Returns dict with keys:
        - last_8_messages
        - last_20_assistant_messages
        - last_5_assistant_messages
        - last_3_assistant_messages
        - last_8_user_messages
        - summary_messages
        - openai_msgs
        """
        last_50_messages = self.get_last_messages(history, count=50)
        last_8_messages = self.get_last_messages(last_50_messages, count=8, force_last_user=True)
        last_20_assistant_messages = self.get_last_messages(last_50_messages, count=20, role="assistant")
        last_5_assistant_messages = self.get_last_messages(last_50_messages, count=5, role="assistant")
        last_3_assistant_messages = self.get_last_messages(last_50_messages, count=3, role="assistant")
        last_8_user_messages = self.get_last_messages(last_50_messages, count=8, role="user")
        summary_messages = self._get_messages_by_tokens(last_50_messages, max_tokens=max_tokens, deviation=deviation)

        msgs_from_phrase = self.get_reset_filtered_messages(last_50_messages)

        if msgs_from_phrase:
            last_8_messages = self.get_last_messages(msgs_from_phrase, count=8, force_last_user=True)
            last_20_assistant_messages = self.get_last_messages(msgs_from_phrase, count=20, role="assistant")
            last_5_assistant_messages = self.get_last_messages(msgs_from_phrase, count=5, role="assistant")
            last_3_assistant_messages = self.get_last_messages(msgs_from_phrase, count=3, role="assistant")
            last_8_user_messages = self.get_last_messages(msgs_from_phrase, count=8, role="user")
            summary_messages = self._get_messages_by_tokens(msgs_from_phrase, max_tokens=2500)
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
            "summary_messages": summary_messages,
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

    @staticmethod
    def clean_json_string(s: str) -> dict:
        # убираем тройные кавычки ```json и ```
        cleaned = re.sub(r'^```json\s*(.*?)\s*```$', r'\1', s.strip(), flags=re.DOTALL)
        return json.loads(cleaned)

    # The following methods have been moved to the SemanticSearch class:
    # - parse_intents_and_create_embeddings (now initialize_phrases)
    # - semantic_search_intent (now semantic_search_phrase)
    # - full_text_search_intent (now full_text_search_phrase)