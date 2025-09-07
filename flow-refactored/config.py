"""Configuration module for the SQLAlchemy refactor.

This module centralises reading environment variables and provides a
single `Config` dataclass that can be passed to other components. It
demonstrates the Clean Code rule of using meaningful names: each field
conveys its purpose and is type‑annotated for clarity. Any parsing or
defaulting logic is encapsulated here rather than scattered throughout
the code base.
"""

from dataclasses import dataclass, field
import os
from typing import List, Optional


@dataclass
class Config:
    """Runtime configuration for the bot.

    Attributes are read from environment variables with sensible
    defaults where appropriate. Fallback models are split on
    commas to produce a list of model identifiers.
    """

    bot_token: str = field(default_factory=lambda: os.environ['bot_token'])
    operouter_key: str = field(default_factory=lambda: os.environ['operouter_key'])
    ai_model: str = field(default_factory=lambda: os.getenv('ai_model', 'openai/gpt-4o'))
    ai_models_fallback: List[str] = field(default_factory=lambda: os.getenv(
        'ai_models_fallback', 'openai/gpt-4o,openai/gpt-4o-2024-11-20,openai/gpt-4o-2024-08-06'
    ).split(','))
    ai_endpoint: str = field(default_factory=lambda: os.getenv('ai_endpoint', 'https://openrouter.ai/api/v1/chat/completions'))
    session_lifetime: int = field(default_factory=lambda: int(os.getenv('session_lifetime', '87600')))
    connect_timeout: int = field(default_factory=lambda: int(os.getenv('connect_timeout', '1')))
    read_timeout: int = field(default_factory=lambda: int(os.getenv('read_timeout', '5')))
    retry_total: int = field(default_factory=lambda: int(os.getenv('retry_total', '3')))
    retry_backoff_factor: int = field(default_factory=lambda: int(os.getenv('retry_backoff_factor', '2')))
    proxy_url: Optional[str] = field(default_factory=lambda: os.getenv('proxy_url'))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv('openai_key'))
    database_url: str = field(default_factory=lambda: os.environ['database_url'])
    song_bucket_name: Optional[str] = field(default_factory=lambda: os.getenv('song_bucket_name'))
    suno_api_url: str = field(default_factory=lambda: os.getenv('suno_api_url', 'https://apibox.erweima.ai/api/v1/generate'))
    suno_model: str = field(default_factory=lambda: os.getenv('suno_model', 'V4_5'))
    suno_callback_url: Optional[str] = field(default_factory=lambda: os.getenv('suno_callback_url'))
    suno_api_key: Optional[str] = field(default_factory=lambda: os.getenv('suno_api_key'))