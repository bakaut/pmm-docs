"""
Configuration module

Centralises reading environment variables with pydantic validation.
All env var names are expected in lower-case only.

Architecture:
- All modules receive Config instance through constructors
- Direct access via config.property_name (no aliases in index.py)
- Structured configuration with nested pydantic models
- Property accessors for backward compatibility
"""

import json
import os
from enum import Enum
from textwrap import dedent
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

# Импортируем логгер для обработки ошибок конфигурации
try:
    from .logger import get_default_logger
    # Создаем логгер для конфигурации (может быть вызван до инициализации основного config)
    _config_logger = get_default_logger('config')
except ImportError:
    # Fallback если logger.py еще не готов
    import logging
    _config_logger = logging.getLogger('config')

from .utils import Utils

# ---- Enums ----------------------------------------------------------------

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class SunoModel(str, Enum):
    V4_5PLUS = "V4_5PLUS"
    V3_5 = "V3_5"

# ---- Defaults ----------------------------------------------------------------

DEFAULT_AI_MODELS_FALLBACK: List[str] = [
    "openai/gpt-4o-2024-05-13",
    "openai/gpt-4o-2024-11-20",
    "openai/gpt-4o-2024-08-06",
]

DEFAULT_CONFUSED_INTENT_ANSWERS: List[str] = [
    dedent(
        """
        Ты можешь быть с собой честен здесь. Без страха.
        Даже если честность сейчас — это: "Я не знаю, что чувствую".
        Это уже начало песни...
        """
    ).strip(),
    dedent(
        """
        Чем точнее ты поделишься — тем точнее я смогу услышать тебя.
        А значит, и песня будет ближе к тебе самому...
        """
    ).strip(),
    dedent(
        """
        Иногда самая красивая строчка рождается из фразы
        "я боюсь сказать, что думаю"... Это не слабость. Это глубина.
        """
    ).strip(),
    "В этом месте можно говорить правду. Даже если она шепотом.",
    "💬 Отклики: https://poymoymir.ru/feedback/",
    "🎧 Подкасты: https://poymoymir.ru/feedback/",
]

DEFAULT_SONG_RECEIVED_MARKUP: Dict[str, Any] = {
    "inline_keyboard": [
        [
            {"text": "🌿", "url": "https://bit.ly/4jZSMIH"},
            {"text": "🫂", "switch_inline_query": "ПойМойМир песня о тебе"},
            {"text": "🤗", "callback_data": "hug_author"},
            {"text": "💬", "url": "https://bit.ly/431hC4f"},
            {"text": "🕯", "callback_data": "silence_room"},
            {"text": "🔄", "callback_data": "reset_session"},
        ]
    ]
}

DEFAULT_FALLBACK_ANSWER: str = "Сейчас не могу ответить, загляни чуть позже 🌿"

# Duty workaround for summary_message to overcome deviation limit
DEFAULT_SUMMARIZATION_MESSAGE: str = "Сохранили суммаризацию сообщений пользователя-Сохранили суммаризацию сообщений пользователя-Сохранили суммаризацию сообщений"

DEFAULT_SONG_GENERATING_MESSAGE: str = dedent(
    """
    Твоя песня уже в пути.
    Дай ей немного времени — она рождается 🌿

    Песня придёт отдельным сообщением через 2 минуты
    """
).strip()

DEFAULT_AI_COMPOSER: str = (
    "AI сгенерировано с помощью https://t.me/PoyMoyMirBot"
)

DEFAULT_SONG_RECEIVED_MESSAGE: str = dedent(
    """
    Спасибо за доверие!

    🌿 — Если тебе откликнулось — можешь поддержать проект и вдохновить новые песни
    🫂 — Пригласи друга пройти этот путь. Возможно, его песня тоже ждёт...
    🤗 — Обнять автора
    💬 — Оставить отклик. Это помогает услышать голос песни…
    🕯 — Комната тишины, остаться с собой в моменте
    🔄 — Начать новый разговор
    """
).strip()

DEFAULT_WANT_SILENCE_MESSAGE: str = dedent(
    """
    🕯️ _Хорошо._
    Ты в **комнате тишины**.
    Здесь не нужно отвечать, не нужно продолжать.
    Всё, что ты уже сказал, всё, что ты почувствовал —
    **в целости. И ждёт вместе с тобой.**
    """
).strip()


# ---- Pydantic Models ---------------------------------------------------------

class DatabaseConfig(BaseModel):
    """Database connection configuration for PostgreSQL only"""
    url: Optional[str] = Field(None, description="Database connection URL (PostgreSQL)")
    host: Optional[str] = Field(None, description="Database host (PostgreSQL fallback)")
    port: Optional[int] = Field(5432, description="Database port (PostgreSQL fallback)", ge=1, le=65535)
    name: Optional[str] = Field(None, description="Database name (PostgreSQL fallback)")
    user: Optional[str] = Field(None, description="Database user (PostgreSQL fallback)")
    password: Optional[str] = Field(None, description="Database password (PostgreSQL fallback)")

    @field_validator('url')
    @classmethod
    def validate_database_url(cls, v):
        if v and not v.strip():
            raise ValueError('Database URL cannot be empty if provided')
        return v.strip() if v else None

    @model_validator(mode='after')
    def validate_config_consistency(self):
        if not self.url and not all([self.host, self.name, self.user, self.password]):
            raise ValueError('PostgreSQL requires either URL or all of: host, name, user, password')
        return self

    @property
    def connection_params(self) -> Dict[str, Any]:
        """Возвращает параметры подключения к базе данных."""
        if self.url:
            return {"dsn": self.url}
        else:
            return {
                "host": self.host,
                "port": self.port or 5432,
                "dbname": self.name,
                "user": self.user,
                "password": self.password,
            }

class AIConfig(BaseModel):
    """AI service configuration"""
    model: str = Field(default="openai/gpt-4o-2024-05-13", description="Primary AI model")
    models_fallback: List[str] = Field(default_factory=lambda: DEFAULT_AI_MODELS_FALLBACK[:], description="Fallback AI models")
    endpoint: str = Field(default="https://openrouter.ai/api/v1/chat/completions", description="AI API endpoint")
    operouter_key: str = Field(..., description="OpenRouter API key")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")

    @field_validator('models_fallback', mode='before')
    @classmethod
    def parse_models_fallback(cls, v):
        if isinstance(v, str):
            if not v or not v.strip():
                return DEFAULT_AI_MODELS_FALLBACK[:]
            v = v.strip()
            if v.startswith("["):
                try:
                    data = json.loads(v)
                    return [str(s).strip() for s in data if str(s).strip()]
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in ai_models_fallback: {e}")
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('AI endpoint must be a valid HTTP/HTTPS URL')
        return v

class NetworkConfig(BaseModel):
    """Network and timeout configuration"""
    proxy_url: Optional[str] = Field(None, description="Proxy URL")
    connect_timeout: int = Field(default=1, description="Connection timeout in seconds", ge=1)
    read_timeout: int = Field(default=5, description="Read timeout in seconds", ge=1)
    retry_total: int = Field(default=3, description="Total number of retries", ge=0)
    retry_backoff_factor: int = Field(default=2, description="Backoff factor for retries", ge=1)
    proxy_test_url: str = Field(default="https://pmm-http-bin.website.yandexcloud.net", description="URL for proxy testing")

    @field_validator('proxy_url')
    @classmethod
    def validate_proxy_url(cls, v):
        if v and not v.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            raise ValueError('Proxy URL must be a valid HTTP/HTTPS/SOCKS URL')
        return v

    @property
    def proxy(self) -> Dict[str, Optional[str]]:
        """Возвращает словарь прокси настроек."""
        if self.proxy_url:
            return {"http": self.proxy_url, "https": self.proxy_url}
        return {"http": None, "https": None}

class SunoConfig(BaseModel):
    """Suno API configuration"""
    api_url: str = Field(default="https://apibox.erweima.ai/api/v1/generate", description="Suno API URL")
    model: SunoModel = Field(default=SunoModel.V4_5PLUS, description="Suno model to use")
    callback_url: Optional[str] = Field(None, description="Callback URL for Suno")
    api_key: Optional[str] = Field(None, description="Suno API key")

    @field_validator('api_url')
    @classmethod
    def validate_api_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Suno API URL must be a valid HTTP/HTTPS URL')
        return v

class StorageConfig(BaseModel):
    """Storage configuration"""
    song_bucket_name: Optional[str] = Field(None, description="S3 bucket for songs")
    song_path: str = Field(default="/function/storage/songs/", description="Local path for songs")

class MessagesConfig(BaseModel):
    """Message templates and constants"""
    fallback_answer: str = Field(default=DEFAULT_FALLBACK_ANSWER, description="Fallback answer")
    song_generating_message: str = Field(default=DEFAULT_SONG_GENERATING_MESSAGE, description="Song generation message")
    ai_composer: str = Field(default=DEFAULT_AI_COMPOSER, description="AI composer attribution")
    song_received_message: str = Field(default=DEFAULT_SONG_RECEIVED_MESSAGE, description="Song received message")
    want_silence_message: str = Field(default=DEFAULT_WANT_SILENCE_MESSAGE, description="Silence room message")
    confused_intent_answers: List[str] = Field(default_factory=lambda: DEFAULT_CONFUSED_INTENT_ANSWERS[:], description="Confused intent answers")
    song_received_markup: Dict[str, Any] = Field(default_factory=lambda: json.loads(json.dumps(DEFAULT_SONG_RECEIVED_MARKUP)), description="Song received markup")
    summarization_message: str = Field(default=DEFAULT_SUMMARIZATION_MESSAGE, description="Summarization message")

    @field_validator('confused_intent_answers', mode='before')
    @classmethod
    def parse_confused_intent_answers(cls, v):
        if isinstance(v, str):
            if not v or not v.strip():
                return DEFAULT_CONFUSED_INTENT_ANSWERS[:]
            try:
                return json.loads(v)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in confused_intent_answers: {e}")
        return v

    @field_validator('song_received_markup', mode='before')
    @classmethod
    def parse_song_received_markup(cls, v):
        if isinstance(v, str):
            if not v or not v.strip():
                return json.loads(json.dumps(DEFAULT_SONG_RECEIVED_MARKUP))
            try:
                data = json.loads(v)
                if not isinstance(data, dict):
                    raise ValueError("song_received_markup must be a JSON object")
                return data
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in song_received_markup: {e}")
        return v

class AudioConfig(BaseModel):
    """Audio URLs configuration"""
    confused_intent_answer_mp3: str = Field(
        default="https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/try.mp3",
        description="Confused intent audio URL"
    )
    feedback_intent_answer_mp3: str = Field(
        default="https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/feedback.mp3",
        description="Feedback intent audio URL"
    )

    @field_validator('confused_intent_answer_mp3', 'feedback_intent_answer_mp3')
    @classmethod
    def validate_audio_urls(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Audio URLs must be valid HTTP/HTTPS URLs')
        return v

class PromptsConfig(BaseModel):
    """System prompts configuration"""
    system_prompt_template: str = Field(default="knowledge_bases/templates/system_prompt.txt.yaml", description="Template for main system prompt")
    prepare_suno_template: str = Field(default="knowledge_bases/templates/prepare_suno.txt.yaml", description="Template for Suno preparation prompt")
    emotion_detection_template: str = Field(default="knowledge_bases/templates/detect_emotional_state.txt.yaml", description="Template for emotion detection prompt")
    intent_detection_template: str = Field(default="knowledge_bases/templates/detect_intent.txt.yaml", description="Template for intent detection prompt")
    intent_detection_v1_template: str = Field(default="knowledge_bases/templates/detect_intent_v1.txt.yaml", description="Template for intent detection v1 prompt")
    intent_detection_v2_template: str = Field(default="knowledge_bases/templates/detect_intent_v2.txt.yaml", description="Template for intent detection v2 prompt")
    state_detection_template: str = Field(default="knowledge_bases/templates/detect_state.txt.yaml", description="Template for state detection prompt")
    summarization_template: str = Field(default="knowledge_bases/templates/summarize_conversation.txt.yaml", description="Template for conversation summarization prompt")

    # Cached prompt content
    _system_prompt: Optional[str] = None
    _prepare_suno_prompt: Optional[str] = None
    _intent_detection_prompt: Optional[str] = None
    _intent_detection_v1_prompt: Optional[str] = None
    _intent_detection_v2_prompt: Optional[str] = None
    _emotion_detection_prompt: Optional[str] = None
    _state_detection_prompt: Optional[str] = None
    _summarization_prompt: Optional[str] = None

    def _load_file(self, file_path: str) -> str:
        """Load a text file with UTF-8 encoding"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            _config_logger.warning(f"Prompt file not found: {file_path}")
            return ""
        except Exception as e:
            _config_logger.error(f"Error loading prompt file {file_path}: {e}")
            return ""

    @property
    def system_prompt(self) -> str:
        """Load and cache system prompt using template"""
        if self._system_prompt is None:
            if self.system_prompt_template:
                try:
                    self._system_prompt = Utils.render_template(self.system_prompt_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering system prompt template: {e}")
                    self._system_prompt = ""
            else:
                _config_logger.error("No system prompt template specified")
                self._system_prompt = ""
        return self._system_prompt

    @property
    def prepare_suno_prompt(self) -> str:
        """Load and cache Suno preparation prompt using template"""
        if self._prepare_suno_prompt is None:
            if self.prepare_suno_template:
                try:
                    self._prepare_suno_prompt = Utils.render_template(self.prepare_suno_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering prepare suno template: {e}")
                    self._prepare_suno_prompt = ""
            else:
                _config_logger.error("No prepare suno template specified")
                self._prepare_suno_prompt = ""
        return self._prepare_suno_prompt

    @property
    def intent_detection_prompt(self) -> str:
        """Load and cache intent detection prompt using template"""
        if self._intent_detection_prompt is None:
            if self.intent_detection_template:
                try:
                    self._intent_detection_prompt = Utils.render_template(self.intent_detection_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering intent detection template: {e}")
                    self._intent_detection_prompt = ""
            else:
                _config_logger.error("No intent detection template specified")
                self._intent_detection_prompt = ""
        return self._intent_detection_prompt

    @property
    def intent_detection_v1_prompt(self) -> str:
        """Load and cache intent detection v1 prompt using template"""
        if self._intent_detection_v1_prompt is None:
            if self.intent_detection_v1_template:
                try:
                    self._intent_detection_v1_prompt = Utils.render_template(self.intent_detection_v1_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering intent detection v1 template: {e}")
                    self._intent_detection_v1_prompt = ""
            else:
                _config_logger.error("No intent detection v1 template specified")
                self._intent_detection_v1_prompt = ""
        return self._intent_detection_v1_prompt

    @property
    def intent_detection_v2_prompt(self) -> str:
        """Load and cache intent detection v2 prompt using template"""
        if self._intent_detection_v2_prompt is None:
            if self.intent_detection_v2_template:
                try:
                    self._intent_detection_v2_prompt = Utils.render_template(self.intent_detection_v2_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering intent detection v2 template: {e}")
                    self._intent_detection_v2_prompt = ""
            else:
                _config_logger.error("No intent detection v2 template specified")
                self._intent_detection_v2_prompt = ""
        return self._intent_detection_v2_prompt

    @property
    def emotion_detection_prompt(self) -> str:
        """Load and cache emotion detection prompt using template"""
        if self._emotion_detection_prompt is None:
            if self.emotion_detection_template:
                try:
                    from .utils import Utils
                    self._emotion_detection_prompt = Utils.render_template(self.emotion_detection_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering emotion detection template: {e}")
                    self._emotion_detection_prompt = ""
            else:
                _config_logger.error("No emotion detection template specified")
                self._emotion_detection_prompt = ""
        return self._emotion_detection_prompt

    @property
    def state_detection_prompt(self) -> str:
        """Load and cache state detection prompt using template"""
        if self._state_detection_prompt is None:
            if self.state_detection_template:
                try:
                    self._state_detection_prompt = Utils.render_template(self.state_detection_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering state detection template: {e}")
                    self._state_detection_prompt = ""
            else:
                _config_logger.error("No state detection template specified")
                self._state_detection_prompt = ""
        return self._state_detection_prompt

    @property
    def summarization_prompt(self) -> str:
        """Load and cache conversation summarization prompt using template"""
        if self._summarization_prompt is None:
            if self.summarization_template:
                try:
                    self._summarization_prompt = Utils.render_template(self.summarization_template)
                except Exception as e:
                    _config_logger.error(f"Error rendering summarization template: {e}")
                    self._summarization_prompt = ""
            else:
                _config_logger.error("No summarization template specified")
                self._summarization_prompt = ""
        return self._summarization_prompt

class CacheConfig(BaseModel):
    """Redis cache configuration"""
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    sqlite_path: str = Field(default="/function/storage/songs/sqlvec.db", description="SQLite database file path for SQLite-Vec cache")
    index_name: str = Field(default="idx:cache", description="RedisSearch index name")
    key_prefix: str = Field(default="cache:", description="Redis key prefix")
    embedding_dimensions: int = Field(default=1536, description="Embedding vector dimensions", ge=1)
    default_ttl: int = Field(default=3600, description="Default TTL in seconds", ge=1)
    enable_embeddings: bool = Field(default=True, description="Enable embedding storage and search")
    max_text_length: int = Field(default=10000, description="Maximum text length for caching", ge=1)
    batch_size: int = Field(default=100, description="Batch size for bulk operations", ge=1)
    fault_tolerant: bool = Field(default=True, description="Enable fault-tolerant mode for graceful degradation")

    @field_validator('redis_url')
    @classmethod
    def validate_redis_url(cls, v):
        if not v or not v.strip():
            raise ValueError('Redis URL cannot be empty')
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError('Redis URL must start with redis:// or rediss://')
        return v.strip()

    @field_validator('index_name', 'key_prefix')
    @classmethod
    def validate_names(cls, v):
        if not v or not v.strip():
            raise ValueError('Index name and key prefix cannot be empty')
        return v.strip()

class ToolsConfig(BaseModel):
    """AI tools configuration"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        """Returns the tools configuration for AI function calls"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "moderate_user",
                    "description": "Мутит или банит пользователя в Telegram на основании числа предупреждений в базе.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer", "description": "ID чата"},
                            "user_id": {"type": "string", "description": "Telegram user ID"},
                            "additional_reason": {"type": "string", "description": "Доп. причина"}
                        },
                        "required": ["chat_id", "user_id"]
                    }
                }
            }
        ]

class Config(BaseSettings):
    """Runtime configuration for the bot with pydantic validation."""

    # Core bot settings
    bot_token: str = Field(..., description="Telegram bot token")
    session_lifetime: int = Field(default=87600, description="Session lifetime in seconds", ge=1)

    # Feature flags
    enable_conversation_reset: bool = Field(default=True, description="Enable conversation reset functionality")

    # Logging
    log_level: LogLevel = Field(default=LogLevel.DEBUG, description="Logging level")
    log_name: str = Field(default="poymoymir", description="Logger name")

    # Nested configurations
    database: DatabaseConfig
    ai: AIConfig
    network: NetworkConfig
    suno: SunoConfig
    storage: StorageConfig
    messages: MessagesConfig
    audio: AudioConfig
    cache: CacheConfig
    tools: ToolsConfig
    prompts: PromptsConfig

    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': False,
        'env_nested_delimiter': '__'
    }

    @field_validator('bot_token')
    @classmethod
    def validate_bot_token(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Bot token must be at least 10 characters long')
        return v.strip()

    @model_validator(mode='after')
    def validate_database_connection(self):
        db_config = self.database
        if not db_config.url and not all([db_config.host, db_config.name, db_config.user, db_config.password]):
            raise ValueError('PostgreSQL requires either database_url or all fallback fields: host, name, user, password')
        return self

    # Property accessors for direct config usage
    # All modules now use config.property_name instead of aliases
    @property
    def operouter_key(self) -> str:
        return self.ai.operouter_key

    @property
    def ai_model(self) -> str:
        return self.ai.model

    @property
    def ai_models_fallback(self) -> List[str]:
        return self.ai.models_fallback

    @property
    def ai_endpoint(self) -> str:
        return self.ai.endpoint

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.ai.openai_api_key

    @property
    def proxy_url(self) -> Optional[str]:
        return self.network.proxy_url

    @property
    def connect_timeout(self) -> int:
        return self.network.connect_timeout

    @property
    def read_timeout(self) -> int:
        return self.network.read_timeout

    @property
    def retry_total(self) -> int:
        return self.network.retry_total

    @property
    def retry_backoff_factor(self) -> int:
        return self.network.retry_backoff_factor

    @property
    def proxy_test_url(self) -> str:
        return self.network.proxy_test_url

    @property
    def proxy(self) -> Dict[str, Optional[str]]:
        return self.network.proxy

    @property
    def db_connection_params(self) -> Dict[str, Any]:
        return self.database.connection_params

    @property
    def song_bucket_name(self) -> Optional[str]:
        return self.storage.song_bucket_name

    @property
    def song_path(self) -> str:
        return self.storage.song_path

    @property
    def suno_api_url(self) -> str:
        return self.suno.api_url

    @property
    def suno_model(self) -> str:
        return self.suno.model.value

    @property
    def suno_callback_url(self) -> Optional[str]:
        return self.suno.callback_url

    @property
    def suno_api_key(self) -> Optional[str]:
        return self.suno.api_key

    # Message configuration properties
    @property
    def fallback_answer(self) -> str:
        return self.messages.fallback_answer

    @property
    def song_generating_message(self) -> str:
        return self.messages.song_generating_message

    @property
    def ai_composer(self) -> str:
        return self.messages.ai_composer

    @property
    def song_received_message(self) -> str:
        return self.messages.song_received_message

    @property
    def want_silence_message(self) -> str:
        return self.messages.want_silence_message

    @property
    def confused_intent_answers(self) -> List[str]:
        return self.messages.confused_intent_answers

    @property
    def song_received_markup(self) -> Dict[str, Any]:
        return self.messages.song_received_markup

    @property
    def summarization_message(self) -> str:
        return self.messages.summarization_message

    @property
    def confused_intent_answer_mp3(self) -> str:
        return self.audio.confused_intent_answer_mp3

    @property
    def llm_tools(self) -> List[Dict[str, Any]]:
        return self.tools.tools

    # System prompt configuration properties
    @property
    def system_prompt(self) -> str:
        return self.prompts.system_prompt

    @property
    def system_prompt_prepare_suno(self) -> str:
        return self.prompts.prepare_suno_prompt

    @property
    def system_prompt_intent(self) -> str:
        return self.prompts.intent_detection_prompt

    @property
    def system_prompt_intent_v1(self) -> str:
        return self.prompts.intent_detection_v1_prompt

    @property
    def system_prompt_intent_v2(self) -> str:
        return self.prompts.intent_detection_v2_prompt

    @property
    def system_prompt_detect_emotion(self) -> str:
        return self.prompts.emotion_detection_prompt

    @property
    def system_prompt_detect_state(self) -> str:
        return self.prompts.state_detection_prompt

    @property
    def system_prompt_summarization(self) -> str:
        return self.prompts.summarization_prompt

    # Cache configuration properties
    @property
    def cache_redis_url(self) -> str:
        return self.cache.redis_url

    @property
    def cache_sqlite_path(self) -> str:
        return self.cache.sqlite_path

    @property
    def cache_index_name(self) -> str:
        return self.cache.index_name

    @property
    def cache_key_prefix(self) -> str:
        return self.cache.key_prefix

    @property
    def cache_embedding_dimensions(self) -> int:
        return self.cache.embedding_dimensions

    @property
    def cache_default_ttl(self) -> int:
        return self.cache.default_ttl

    @property
    def cache_enable_embeddings(self) -> bool:
        return self.cache.enable_embeddings

    @property
    def cache_max_text_length(self) -> int:
        return self.cache.max_text_length

    @property
    def cache_batch_size(self) -> int:
        return self.cache.batch_size

    @property
    def cache_fault_tolerant(self) -> bool:
        return self.cache.fault_tolerant



    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "Config":
        """
        Factory method to create Config instance from environment variables.
        Used in index.py as config = Config.from_env()
        """
        _config_logger.debug("Loading configuration from environment variables")

        # Определяем источник переменных окружения
        env_source = env if env is not None else os.environ

        def get_env(key: str, default: str = "") -> str:
            return env_source.get(key, default)

        def get_env_int(key: str, default: int) -> int:
            try:
                return int(env_source.get(key, str(default)))
            except (ValueError, TypeError):
                return default

        try:
            # Создаем конфигурацию вручную из плоских переменных окружения
            config = cls(
                bot_token=get_env("bot_token"),
                session_lifetime=get_env_int("session_lifetime", 87600),
                enable_conversation_reset=get_env("enable_conversation_reset", "true").lower() == "true",
                log_level=LogLevel(get_env("log_level", "DEBUG")),
                log_name=get_env("log_name", "poymoymir"),

                database=DatabaseConfig(
                    url=get_env("database_url"),
                    host=get_env("db_host") or None,
                    port=get_env_int("db_port", 5432) if get_env("db_port") else None,
                    name=get_env("db_name") or None,
                    user=get_env("db_user") or None,
                    password=get_env("db_password") or None
                ),

                ai=AIConfig(
                    model=get_env("ai_model", "openai/gpt-4o-2024-05-13"),
                    models_fallback=get_env("ai_models_fallback", ""),
                    endpoint=get_env("ai_endpoint", "https://openrouter.ai/api/v1/chat/completions"),
                    operouter_key=get_env("operouter_key"),
                    openai_api_key=get_env("openai_key") or get_env("openai_api_key") or None
                ),

                network=NetworkConfig(
                    proxy_url=get_env("proxy_url") or None,
                    connect_timeout=get_env_int("connect_timeout", 1),
                    read_timeout=get_env_int("read_timeout", 5),
                    retry_total=get_env_int("retry_total", 3),
                    retry_backoff_factor=get_env_int("retry_backoff_factor", 2),
                    proxy_test_url=get_env("proxy_test_url", "https://pmm-http-bin.website.yandexcloud.net")
                ),

                suno=SunoConfig(
                    api_url=get_env("suno_api_url", "https://apibox.erweima.ai/api/v1/generate"),
                    model=SunoModel(get_env("suno_model", "V4_5PLUS")),
                    callback_url=get_env("suno_callback_url") or None,
                    api_key=get_env("suno_api_key") or None
                ),

                storage=StorageConfig(
                    song_bucket_name=get_env("song_bucket_name") or None,
                    song_path=get_env("song_path", "/function/storage/songs/")
                ),

                messages=MessagesConfig(
                    fallback_answer=get_env("fallback_answer", DEFAULT_FALLBACK_ANSWER),
                    song_generating_message=get_env("song_generating_message", DEFAULT_SONG_GENERATING_MESSAGE),
                    ai_composer=get_env("ai_composer", DEFAULT_AI_COMPOSER),
                    song_received_message=get_env("song_received_message", DEFAULT_SONG_RECEIVED_MESSAGE),
                    want_silence_message=get_env("want_silence_message", DEFAULT_WANT_SILENCE_MESSAGE),
                    confused_intent_answers=get_env("confused_intent_answers", ""),
                    song_received_markup=get_env("song_received_markup", ""),
                    summarization_message=get_env("summarization_message", DEFAULT_SUMMARIZATION_MESSAGE)
                ),

                audio=AudioConfig(
                    confused_intent_answer_mp3=get_env("confused_intent_answer_mp3", "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/try.mp3"),
                    feedback_intent_answer_mp3=get_env("feedback_intent_answer_mp3", "https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/feedback.mp3")
                ),

                cache=CacheConfig(
                    redis_url=get_env("cache_redis_url", "redis://localhost:6379/0"),
                    sqlite_path=get_env("sqlite_path", "/function/storage/songs/sqlvec.db"),
                    index_name=get_env("cache_index_name", "idx:cache"),
                    key_prefix=get_env("cache_key_prefix", "cache:"),
                    embedding_dimensions=get_env_int("cache_embedding_dimensions", 1536),
                    default_ttl=get_env_int("cache_default_ttl", 3600),
                    enable_embeddings=get_env("cache_enable_embeddings", "true").lower() == "true",
                    max_text_length=get_env_int("cache_max_text_length", 10000),
                    batch_size=get_env_int("cache_batch_size", 100),
                    fault_tolerant=get_env("cache_fault_tolerant", "true").lower() == "true"
                ),

                tools=ToolsConfig(),

                prompts=PromptsConfig(
                    system_prompt_template=get_env("system_prompt_template") or "knowledge_bases/templates/system_prompt.txt.yaml",
                    prepare_suno_template=get_env("prepare_suno_template") or "knowledge_bases/templates/prepare_suno.txt.yaml",
                    intent_detection_template=get_env("intent_detection_template") or "knowledge_bases/templates/detect_intent.txt.yaml",
                    intent_detection_v1_template=get_env("intent_detection_v1_template") or "knowledge_bases/templates/detect_intent_v1.txt.yaml",
                    intent_detection_v2_template=get_env("intent_detection_v2_template") or "knowledge_bases/templates/detect_intent_v2.txt.yaml",
                    emotion_detection_template=get_env("emotion_detection_template") or "knowledge_bases/templates/detect_emotional_state.txt.yaml",
                    state_detection_template=get_env("state_detection_template") or "knowledge_bases/templates/detect_state.txt.yaml",
                    summarization_template=get_env("summarization_template") or "knowledge_bases/templates/summarize_conversation.txt.yaml"
                )

            )

            _config_logger.debug("Configuration loaded successfully")
            _config_logger.debug("Log level: %s, Log name: %s", config.log_level, config.log_name)
            return config

        except Exception as e:
            _config_logger.error("Failed to create configuration: %s", str(e))
            _config_logger.debug("Available env vars: %s", list(env_source.keys()) if env_source else [])
            raise


# ---- Factory Functions -------------------------------------------------------

def create_config(env_dict: Optional[Dict[str, str]] = None) -> Config:
    """
    Создает конфигурацию с автоматической валидацией.

    Args:
        env_dict: Словарь переменных окружения (если None, используются системные)

    Returns:
        Валидированная конфигурация

    Raises:
        ValidationError: При неверных данных конфигурации
    """
    return Config.from_env(env_dict)

def get_config() -> Config:
    """
    Получает конфигурацию из переменных окружения.
    Удобная функция для быстрого доступа.
    """
    return Config.from_env()
