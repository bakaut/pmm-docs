"""
Comprehensive refactoring of the PMM bot on a modern stack
=========================================================

This module mirrors the original PMM bot logic, functions and structure as
closely as possible while migrating to a different technology stack.  The
goals of this refactoring are:

* Preserve **all existing functionality**: handling Telegram updates,
  interacting with a PostgreSQL database, calling Suno to generate songs,
  moderating content via OpenAI, maintaining conversation history and
  session state, and orchestrating multi‑step flows such as intent
  detection and song generation.
* Transition to **Aiogram** for Telegram interactions, **SQLAlchemy**
  for database access, **LangChain** for LLM integration and **LangGraph**
  to model the conversational flow.  The same prompts, tools and
  heuristics from the original code are preserved.
* Respect the constraints of **Yandex Cloud Functions**: each handler
  invocation is stateless, asynchronous and must complete quickly.

The original code relied on a large number of global functions and
imperative flow.  Here we reorganise the logic into service classes and
state machines while preserving naming and behaviour.  Comments in
English and Russian accompany sections that replicate specific pieces of
logic from the original implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TypedDict

import aiohttp
from aiogram import Bot, Dispatcher, types as aiotypes
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from requests import HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests
import boto3
import tiktoken

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None


# ---------------------------------------------------------------------------
# Logging setup (перенос форматера и уровней из оригинального кода)

class YcLoggingFormatter(jsonlogger.JsonFormatter if jsonlogger else logging.Formatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict) if jsonlogger else None
        log_record["logger"] = record.name
        level = record.levelname
        log_record["level"] = level.replace("WARNING", "WARN").replace("CRITICAL", "FATAL")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("PMM")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = logging.StreamHandler()
    formatter = YcLoggingFormatter("%(message)s %(level)s %(logger)s") if jsonlogger else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logger()


# ---------------------------------------------------------------------------
# Environment configuration (same variable names and defaults as original)

class Config:
    bot_token = os.getenv("bot_token")
    operouter_key = os.getenv("operouter_key")
    ai_model = os.getenv("ai_model", "openai/gpt-4o")
    ai_models_fallback = os.getenv(
        "ai_models_fallback",
        ["openai/gpt-4o", "openai/gpt-4o-2024-11-20", "openai/gpt-4o-2024-08-06"],
    )
    ai_endpoint = os.getenv("ai_endpoint", "https://openrouter.ai/api/v1/chat/completions")
    session_lifetime = int(os.getenv("session_lifetime", "87600"))
    connect_timeout = int(os.getenv("connect_timeout", "1"))
    read_timeout = int(os.getenv("read_timeout", "5"))
    retry_total = int(os.getenv("retry_total", "3"))
    retry_backoff_factor = int(os.getenv("retry_backoff_factor", "2"))
    timeout = (connect_timeout, read_timeout)
    proxy_url = os.getenv("proxy_url")
    openai_api_key = os.getenv("openai_key")
    song_bucket_name = os.getenv("song_bucket_name")
    suno_api_url = os.getenv("suno_api_url", "https://apibox.erweima.ai/api/v1/generate")
    suno_model = os.getenv("suno_model", "V4_5")
    suno_callback_url = os.getenv("suno_callback_url")
    system_prompt = ""
    intent_prompt = ""
    emotion_prompt = ""
    prepare_suno_prompt = ""

    # Loading prompts from files at import time replicates original behaviour
    @classmethod
    def load_prompts(cls) -> None:
        def read_file(fname: str) -> str:
            path = os.path.join(os.path.dirname(__file__), "knowledge_bases", fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                return ""

        cls.system_prompt = read_file("system_prompt.txt")
        cls.intent_prompt = read_file("determinate_intent.txt")
        cls.emotion_prompt = read_file("detect_emotional_state.txt")
        cls.prepare_suno_prompt = read_file("prepare_suno.txt")


Config.load_prompts()


# ---------------------------------------------------------------------------
# Database models and service layer (SQLAlchemy replaces raw psycopg2)

Base = declarative_base()


class BotModel(Base):
    __tablename__ = "bots"
    id = Column(String, primary_key=True)
    token_hash = Column(String, unique=True)
    username = Column(String)
    owner_id = Column(String)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    chat_id = Column(Integer, unique=True)
    full_name = Column(String)
    sessions = relationship("ConversationSessionModel", back_populates="user")


class TelegramUserModel(Base):
    __tablename__ = "tg_users"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    warnings = Column(Integer, default=0)
    blocked = Column(Boolean, default=False)
    blocked_reason = Column(String)
    blocked_at = Column(DateTime)
    user = relationship("UserModel")


class ConversationSessionModel(Base):
    __tablename__ = "conversation_sessions"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    bot_id = Column(String)
    started_at = Column(DateTime)
    ended_at = Column(DateTime, nullable=True)
    model = Column(String)
    user = relationship("UserModel", back_populates="sessions")
    messages = relationship("MessageModel", back_populates="session")


class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("conversation_sessions.id"))
    user_id = Column(String, ForeignKey("users.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime)
    analysis = Column(JSON)
    session = relationship("ConversationSessionModel", back_populates="messages")
    user = relationship("UserModel")


class SongModel(Base):
    __tablename__ = "songs"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    session_id = Column(String, ForeignKey("conversation_sessions.id"))
    task_id = Column(String)
    title = Column(String)
    prompt = Column(Text)
    style = Column(String)
    path = Column(String)
    created_at = Column(DateTime)
    user = relationship("UserModel")
    session = relationship("ConversationSessionModel")


class DatabaseService:
    def __init__(self):
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # DSN fallback replicates original code
            host = os.getenv("DB_HOST")
            port = os.getenv("DB_PORT", "5432")
            name = os.getenv("DB_NAME")
            user = os.getenv("DB_USER")
            password = os.getenv("DB_PASSWORD")
            db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def get_session(self):
        return self.Session()

    # Functions ported from the original code
    def get_or_create_bot(self, token: str, username: Optional[str] = None) -> BotModel:
        token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()
        with self.get_session() as session:
            bot = session.query(BotModel).filter_by(token_hash=token_hash).first()
            if bot:
                return bot
            bot_id = str(uuid.uuid4())
            bot = BotModel(id=bot_id, token_hash=token_hash, username=username, owner_id=None)
            session.add(bot)
            session.commit()
            logger.info("Created bot %s (token hash %s)", bot_id, token_hash)
            return bot

    def ensure_user_exists(self, tg_user_id: str, user_uuid: str) -> TelegramUserModel:
        with self.get_session() as session:
            rec = session.query(TelegramUserModel).filter_by(id=tg_user_id).first()
            if rec:
                return rec
            tg_user = TelegramUserModel(id=tg_user_id, user_id=user_uuid, warnings=0, blocked=False)
            session.add(tg_user)
            session.commit()
            return tg_user

    def moderate_user(self, chat_id: int, tg_user_id: str, additional_reason: str = "Нарушение правил") -> Optional[int]:
        # Replicate original moderation logic: warn, ban permanently on second strike
        with self.get_session() as session:
            tg_user = session.query(TelegramUserModel).filter_by(id=tg_user_id).first()
            warnings = tg_user.warnings if tg_user else 0
            blocked = tg_user.blocked if tg_user else False
            if warnings > 2 and blocked:
                return 3
            new_warnings = warnings + 1
            if not tg_user:
                return None
            tg_user.warnings = new_warnings
            session.commit()
            if warnings == 1 and not blocked:
                tg_user.blocked = True
                tg_user.blocked_reason = additional_reason
                tg_user.blocked_at = datetime.now(timezone.utc)
                session.commit()
                return 1
            elif warnings >= 2 and not blocked:
                tg_user.blocked = True
                tg_user.blocked_reason = additional_reason
                tg_user.blocked_at = datetime.now(timezone.utc)
                session.commit()
                return 2
            return None

    def get_or_create_user(self, chat_id: int, full_name: str) -> UserModel:
        with self.get_session() as session:
            user = session.query(UserModel).filter_by(chat_id=chat_id).first()
            if user:
                return user
            user_id = str(uuid.uuid4())
            user = UserModel(id=user_id, chat_id=chat_id, full_name=full_name)
            session.add(user)
            session.commit()
            logger.info("Created user %s for chat_id %s", user_id, chat_id)
            return user

    def get_active_session(self, user_uuid: str, bot_uuid: str) -> ConversationSessionModel:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=Config.session_lifetime)
        with self.get_session() as session:
            rec = (
                session.query(ConversationSessionModel)
                .filter_by(user_id=user_uuid, bot_id=bot_uuid, ended_at=None)
                .order_by(ConversationSessionModel.started_at.desc())
                .first()
            )
            if rec and rec.started_at and rec.started_at > cutoff:
                return rec
            session_uuid = str(uuid.uuid4())
            new_session = ConversationSessionModel(
                id=session_uuid,
                user_id=user_uuid,
                bot_id=bot_uuid,
                started_at=datetime.now(timezone.utc),
                model=Config.ai_model,
            )
            session.add(new_session)
            session.commit()
            logger.debug("Created session %s", session_uuid)
            return new_session

    def fetch_history(self, session_id: str, limit_count: Optional[int] = None) -> List[Dict[str, str]]:
        with self.get_session() as session:
            query = session.query(MessageModel).filter_by(session_id=session_id).order_by(MessageModel.created_at.asc())
            if limit_count:
                # mimic OFFSET logic of original fetch_history for last N messages
                count = query.count()
                offset = max(0, count - limit_count)
                rows = query.offset(offset).limit(limit_count).all()
            else:
                rows = query.all()
            return [
                {"role": r.role, "content": r.content} for r in rows
            ]

    def add_message(self, session_id: str, user_id: str, role: str, content: str, analysis: Optional[dict] = None) -> str:
        with self.get_session() as session:
            message_id = str(uuid.uuid4())
            msg = MessageModel(
                id=message_id,
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                created_at=datetime.now(timezone.utc),
                analysis=analysis,
            )
            session.add(msg)
            session.commit()
            return message_id

    def update_message_analysis(self, message_id: str, analysis: dict) -> None:
        with self.get_session() as session:
            message = session.query(MessageModel).filter_by(id=message_id).first()
            if message:
                message.analysis = analysis
                session.commit()

    def save_song(self, song_id: str, user_id: str, session_id: str, task_id: str, title: str, prompt: str, style: str, path: Optional[str] = None) -> None:
        with self.get_session() as session:
            song = SongModel(
                id=song_id,
                user_id=user_id,
                session_id=session_id,
                task_id=task_id,
                title=title,
                prompt=prompt,
                style=style,
                path=path,
                created_at=datetime.now(timezone.utc),
            )
            session.add(song)
            session.commit()

    def update_song_path(self, task_id: str, path_prefix: str) -> None:
        with self.get_session() as session:
            song = session.query(SongModel).filter_by(task_id=task_id).first()
            if song:
                song.path = path_prefix
                session.commit()


# ---------------------------------------------------------------------------
# HTTP session with retries, similar to the original `requests.Session` setup

class HttpService:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(
            total=Config.retry_total,
            backoff_factor=Config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        logger.info("HTTP session initialised")

    def post(self, url: str, **kwargs):
        return self.session.post(url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.session.get(url, **kwargs)


# ---------------------------------------------------------------------------
# Telegram service (reimplements send_telegram_markup, _send_audio, etc. using Aiogram)

class TelegramService:
    def __init__(self, bot_token: str, http_service: HttpService):
        self.bot = Bot(bot_token)
        self.http_service = http_service
        # Proxy support for OpenAI and moderation calls (requests).  Aiogram
        # itself does not use this proxy, but the HTTP session may need it.
        self.proxy = {"http": Config.proxy_url, "https": Config.proxy_url} if Config.proxy_url else None

    async def send_callback(self, callback_id: str, text: str) -> None:
        await self.bot.answer_callback_query(callback_query_id=callback_id, text=text, show_alert=False)

    async def send_markup(self, chat_id: int, text: str, markup: dict) -> None:
        # Convert dict to Aiogram InlineKeyboardMarkup
        rows = []
        for row in markup.get("inline_keyboard", []):
            buttons = []
            for button in row:
                if "url" in button:
                    buttons.append(InlineKeyboardButton(text=button["text"], url=button["url"]))
                elif "callback_data" in button:
                    buttons.append(InlineKeyboardButton(text=button["text"], callback_data=button["callback_data"]))
                elif "switch_inline_query" in button:
                    buttons.append(InlineKeyboardButton(text=button["text"], switch_inline_query=button["switch_inline_query"]))
            rows.append(buttons)
        inline_markup = InlineKeyboardMarkup(inline_keyboard=rows)
        await self.bot.send_message(chat_id, text, reply_markup=inline_markup, parse_mode="MarkdownV2")

    async def send_audio(self, chat_id: int, audio_url: str, title: str = "") -> None:
        caption = title if title else None
        await self.bot.send_audio(chat_id, audio=audio_url, title=title, caption=caption)

    async def send_text(self, chat_id: int, text: str) -> None:
        await self.bot.send_message(chat_id, text, disable_web_page_preview=True, parse_mode="MarkdownV2")


# ---------------------------------------------------------------------------
# Song helper service (generate signed URL, download and process MP3, call Suno)

class SongService:
    def __init__(self, http_service: HttpService):
        self.http_service = http_service

    def generate_song_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        s3 = boto3.client("s3")
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in,
        )
        return url

    def download_and_process_song(self, song_url: str, tg_user_id: str, song_title: str, song_artist: str, local_folder: str) -> str:
        local_path = os.path.join(f"{local_folder}/{tg_user_id}/", f"{song_title}.mp3")
        song_key = f"{tg_user_id}/{song_title}.mp3"
        os.makedirs(f"{local_folder}/{tg_user_id}", exist_ok=True)
        r = self.http_service.get(song_url)
        with open(local_path, "wb") as f:
            f.write(r.content)
        from mutagen.easyid3 import EasyID3
        from mutagen.mp3 import MP3
        audio = MP3(local_path, ID3=EasyID3)
        audio["title"] = song_title
        audio["artist"] = song_artist
        audio["composer"] = "AI сгенерировано"
        audio.save()
        signed_url = self.generate_song_url(bucket=Config.song_bucket_name, key=song_key)
        return signed_url

    async def request_suno(self, prompt: str, style: str, title: str) -> Optional[str]:
        if not Config.suno_callback_url:
            logger.error("suno_callback_url is not set")
            return None
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {os.getenv("suno_api_key")}',
        }
        payload = {
            "prompt": prompt,
            "style": style,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": Config.suno_model,
            "callBackUrl": Config.suno_callback_url,
        }
        r = self.http_service.post(Config.suno_api_url, json=payload, timeout=Config.timeout)
        try:
            r.raise_for_status()
        except HTTPError as e:
            logger.exception("Suno generation failed: %s", e)
            return None
        data = r.json()
        return data.get("data", {}).get("taskId")


# ---------------------------------------------------------------------------
# Moderation helper (OpenAI moderation API)

class ModerationService:
    def __init__(self, http_service: HttpService):
        self.http_service = http_service

    def is_text_flagged(self, text: str) -> bool:
        url = "https://api.openai.com/v1/moderations"
        headers = {
            "Authorization": f"Bearer {Config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text, "model": "omni-moderation-latest"}
        resp = self.http_service.post(url, headers=headers, json=payload, proxies=(None if not Config.proxy_url else {"http": Config.proxy_url, "https": Config.proxy_url}), timeout=Config.timeout)
        try:
            resp.raise_for_status()
        except Exception as e:
            logger.error("Moderation call failed: %s", e)
            return False
        data = resp.json()
        return data.get("results", [{}])[0].get("flagged", False)


# ---------------------------------------------------------------------------
# LLM service (wraps ChatOpenAI + original llm_call logic, including token trimming and tool invocation)

class LLMService:
    def __init__(self, http_service: HttpService, db_service: DatabaseService):
        self.http_service = http_service
        self.db_service = db_service
        # Use ChatOpenAI from langchain; fallback models can be passed later
        self.chat = ChatOpenAI(openai_api_key=Config.openai_api_key, model_name=Config.ai_model)
        self.encoder = tiktoken.encoding_for_model("gpt-4o")
        # Tools definitions replicating original moderate_user function
        self.tools = [
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
                            "additional_reason": {"type": "string", "description": "Доп. причина"},
                        },
                        "required": ["chat_id", "user_id"],
                    },
                },
            },
        ]

    # Helper to count tokens like original count_tokens
    def count_tokens(self, msg: dict) -> int:
        role_tokens = len(self.encoder.encode(msg["role"]))
        content_tokens = len(self.encoder.encode(msg["content"]))
        return role_tokens + content_tokens + 4

    async def llm_call(self, messages: List[dict], chat_id: str, tg_user_id: str) -> str:
        MAX_TOKENS = 50000
        total = sum(self.count_tokens(m) for m in messages)
        logger.debug("Total tokens: %s", total)
        # Trim history if necessary
        sys_msg = messages[0]
        chat_msgs = messages[1:]
        while total > MAX_TOKENS and chat_msgs:
            removed = chat_msgs.pop(0)
            total -= self.count_tokens(removed)
        messages = [sys_msg] + chat_msgs
        total = sum(self.count_tokens(m) for m in messages)
        logger.debug("Total tokens after trim: %s", total)
        # Call LLM via direct API (OpenRouter) to preserve tool invocation.  Here
        # we use requests to mimic original llm_call because langchain_openai
        # does not support tool execution directly.  For demonstration purposes
        # we'll fallback to ChatOpenAI for simple answers when tools aren't used.
        try:
            payload = {
                "model": Config.ai_model,
                "messages": messages,
                "tools": self.tools,
                "tool_choice": "auto",
                "models": Config.ai_models_fallback,
            }
            headers = {
                "Authorization": f"Bearer {Config.operouter_key}",
                "Content-Type": "application/json",
            }
            proxies = None if not Config.proxy_url else {"http": Config.proxy_url, "https": Config.proxy_url}
            resp = self.http_service.post(Config.ai_endpoint, json=payload, headers=headers, proxies=proxies, timeout=Config.timeout)
            data = resp.json()
            logger.debug("LLM response: %s", data)
            choice = data["choices"][0]["message"]
            # Handle tool call if present
            if "tool_calls" in choice:
                tool_call = choice["tool_calls"][0]
                if tool_call["function"]["name"] == "moderate_user":
                    args = json.loads(tool_call["function"]["arguments"])
                    # invoke database moderation
                    self.db_service.moderate_user(args["chat_id"], str(args["user_id"]), args.get("additional_reason", ""))
            content = choice.get("content", "")
            logger.debug("LLM content: %s", content)
            # Moderation check
            moderation = ModerationService(self.http_service)
            if content == "Извините, я не могу помочь с этой просьбой." or moderation.is_text_flagged(content):
                self.db_service.moderate_user(chat_id, tg_user_id, "LLM or moderation flagged message")
            return content
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return "Сейчас не могу ответить, загляни чуть позже 🌿"

    async def llm_conversation(self, messages: List[dict], system_message: str) -> dict:
        # Use ChatOpenAI generative call for classification tasks
        if system_message:
            messages = [
                {"role": "system", "content": system_message},
            ] + messages
        response = await self.chat.agenerate(messages)
        content = response.generations[0][0].text
        try:
            return json.loads(content)
        except Exception:
            return {"error": "parse error"}


# ---------------------------------------------------------------------------
# State machine for user flow (LangGraph) replicating original handler branches

class FlowState(TypedDict):
    chat_id: int
    text: str
    user_uuid: str
    session_uuid: str
    tg_user_id: str
    last_messages: List[dict]
    intent: dict
    emotion: dict
    analysis_msg_id: str
    is_final_song_received: bool
    is_final_song_sent: bool


class UserFlow:
    def __init__(
        self,
        db_service: DatabaseService,
        llm_service: LLMService,
        song_service: SongService,
        telegram_service: TelegramService,
    ):
        self.db_service = db_service
        self.llm_service = llm_service
        self.song_service = song_service
        self.telegram_service = telegram_service
        self.graph = StateGraph(FlowState)
        self._build_graph()
        self.compiled = self.graph.compile()

    def _build_graph(self) -> None:
        # detect intent node
        @self.graph.add_node
        async def detect_intent(state: FlowState) -> FlowState:
            intent = await self.llm_service.llm_conversation(state["last_messages"][-8:], Config.intent_prompt)
            state["intent"] = intent
            return state

        # detect emotion node
        @self.graph.add_node
        async def detect_emotion(state: FlowState) -> FlowState:
            emotion = await self.llm_service.llm_conversation(state["last_messages"][-8:], Config.emotion_prompt)
            state["emotion"] = emotion
            return state

        # confusion check
        @self.graph.add_node
        async def confusion(state: FlowState) -> FlowState:
            # match original confusion logic
            emotions = state["emotion"].get("emotions", []) if state["emotion"] else []
            is_confused = any(e.get("name") == "Растерянность" and e.get("intensity", 0) > 90 for e in emotions)
            # find 'confused_send' marker in last 20 assistant messages
            last_20_assistant = [m for m in state["last_messages"][-20:] if m["role"] == "assistant"]
            if is_confused and not any(m["content"] == "confused_send" for m in last_20_assistant):
                # send confusion response randomly
                if random.choice([True, False]):
                    answer = random.choice([
                        "Ты можешь быть с собой честен здесь. Без страха. Даже если честность сейчас — это: \"Я не знаю, что чувствую\". Это уже начало песни...",
                        "Чем точнее ты поделишься — тем точнее я смогу услышать тебя. А значит, и песня будет ближе к тебе самому...",
                        "Иногда самая красивая строчка рождается из фразы \"я боюсь сказать, что думаю\"... Это не слабость. Это глубина.",
                        "В этом месте можно говорить правду. Даже если она шепотом.",
                        "💬 Отклики других людей — чтобы почувствовать, как звучит _ПойМойМир_ в чужих сердцах: https://poymoymir.ru/feedback/",
                        "🎧 Подкасты о проекте — мягкое знакомство с тем, как здесь всё устроено: https://poymoymir.ru/feedback/",
                    ])
                    # send via telegram
                    await self.telegram_service.send_text(state["chat_id"], answer)
                    # record assistant and marker messages
                    self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", answer)
                    self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", "confused_send")
                    # stop processing further
                    raise StopIteration
                else:
                    # send MP3 confusion answer
                    await self.telegram_service.send_audio(state["chat_id"], audio_url="https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/try.mp3", title="Ты можешь...")
                    self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", "confused_send")
                    raise StopIteration
            return state

        # song generation
        @self.graph.add_node
        async def maybe_generate_song(state: FlowState) -> FlowState:
            intent_name = state["intent"].get("intent") if state["intent"] else None
            if intent_name == "finalize_song" and not (state["is_final_song_received"] or state["is_final_song_sent"]):
                # Prepare song via LLM
                last_3_assistant_messages = [m for m in state["last_messages"] if m["role"] == "assistant"][-3:]
                song_info = await self.llm_service.llm_conversation(last_3_assistant_messages, Config.prepare_suno_prompt)
                lyrics = song_info.get("lyrics")
                style = song_info.get("style")
                title = song_info.get("name")
                # Request Suno
                task_id = await self.song_service.request_suno(lyrics, style, title)
                # Save song record
                song_id = str(uuid.uuid4())
                self.song_service  # to avoid unused warning
                self.db_service.save_song(song_id, state["user_uuid"], state["session_uuid"], task_id, title, lyrics, style)
                # Notify user
                generating_message = "Твоя песня уже в пути.\nДай ей немного времени — она рождается 🌿\n\nПесня придёт отдельным сообщением через 2 минуты"
                await self.telegram_service.send_text(state["chat_id"], generating_message)
                self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", generating_message)
                # record final sent marker
                self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", "финальная версия песни отправлена пользователю")
                state["is_final_song_sent"] = True
                raise StopIteration
            return state

        # feedback
        @self.graph.add_node
        async def maybe_feedback(state: FlowState) -> FlowState:
            intent_name = state["intent"].get("intent") if state["intent"] else None
            if intent_name == "feedback" and state["is_final_song_received"]:
                # send feedback markup and audio
                markup = {
                    "inline_keyboard": [
                        [
                            {"text": "🌿", "url": "https://bit.ly/4jZSMIH"},
                            {"text": "🔁", "switch_inline_query": "ПойМойМир песня о тебе"},
                            {"text": "🤗", "callback_data": "hug_author"},
                            {"text": "💬", "url": "https://bit.ly/431hC4f"},
                            {"text": "🔕", "callback_data": "silence_room"},
                        ]
                    ]
                }
                await self.telegram_service.send_markup(state["chat_id"], "Ты можешь...", markup)
                await self.telegram_service.send_audio(state["chat_id"], audio_url="https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/feedback.mp3", title="Береги своё вдохновение...")
                self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", "feedback_audio_send")
                raise StopIteration
            return state

        # final LLM chat reply
        @self.graph.add_node
        async def chat_reply(state: FlowState) -> FlowState:
            # Build openai message list (system prompt + history + user message)
            openai_msgs = [
                {"role": "system", "content": Config.system_prompt},
                *state["last_messages"],
                {"role": "user", "content": state["text"]},
            ]
            reply = await self.llm_service.llm_call(openai_msgs, state["chat_id"], state["tg_user_id"])
            await self.telegram_service.send_text(state["chat_id"], reply)
            self.db_service.add_message(state["session_uuid"], state["user_uuid"], "assistant", reply)
            return state

        # graph edges replicating original flow
        self.graph.set_entry_point(detect_intent)
        self.graph.add_edge(detect_intent, detect_emotion)
        self.graph.add_edge(detect_emotion, confusion)
        self.graph.add_edge(confusion, maybe_generate_song)
        self.graph.add_edge(maybe_generate_song, maybe_feedback)
        self.graph.add_edge(maybe_feedback, chat_reply)

    async def run(self, state: FlowState) -> None:
        # The compiled graph returns when StopIteration is raised by a node,
        # which indicates that a branch handled the response completely.
        try:
            await self.compiled.apredict(state)
        except StopIteration:
            pass


# ---------------------------------------------------------------------------
# Yandex Cloud handler function using Aiogram

async def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main entry point for Yandex Cloud.  Mirrors original handler logic."""
    # Initialise services per invocation.  You can cache these globally to speed up cold starts.
    http_service = HttpService()
    db_service = DatabaseService()
    llm_service = LLMService(http_service, db_service)
    song_service = SongService(http_service)
    telegram_service = TelegramService(Config.bot_token, http_service)
    flow = UserFlow(db_service, llm_service, song_service, telegram_service)

    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
    # Callback query processing
    if "callback_query" in body:
        callback = body["callback_query"]
        data = callback.get("data")
        if data == "hug_author":
            await telegram_service.send_callback(callback["id"], "💞 Автору переданы объятия!")
        return {"statusCode": 200, "body": ""}

    # Suno API callback processing (complete)
    if body.get("data") and body["data"].get("callbackType") == "complete":
        task_id = body["data"]["task_id"]
        song_url = body["data"]["data"][0]["audio_url"]
        song_title = body["data"]["data"][0]["title"]
        song_artist = "ПойМойМир"
        # Find Telegram user by task_id
        with db_service.get_session() as session:
            rec = (
                session.query(SongModel, TelegramUserModel)
                .join(TelegramUserModel, SongModel.user_id == TelegramUserModel.user_id)
                .filter(SongModel.task_id == task_id)
                .first()
            )
            tg_user_id = rec[1].id if rec else None
        if tg_user_id:
            # Download and process song, update DB
            signed_url = song_service.download_and_process_song(
                song_url=song_url,
                tg_user_id=tg_user_id,
                song_title=song_title,
                song_artist=song_artist,
                local_folder="/function/storage/songs/",
            )
            path_prefix = f"{tg_user_id}/{song_title}.mp3"
            db_service.update_song_path(task_id, path_prefix)
            # Send final version to user
            user_uuid = db_service.get_or_create_user(int(tg_user_id), full_name="Dummy").id
            session_uuid = db_service.get_active_session(user_uuid, db_service.get_or_create_bot(Config.bot_token).id).id
            await telegram_service.send_audio(int(tg_user_id), signed_url, song_title)
            db_service.add_message(session_uuid, user_uuid, "assistant", "финальная версия песни получена пользователем")
        return {"statusCode": 200, "body": ""}

    # Message processing
    message = body.get("message") or body.get("edited_message")
    if not message or not message.get("text"):
        return {"statusCode": 200, "body": ""}
    chat_id = message["chat"]["id"]
    text = message["text"]
    user_data = message["from"]
    full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    user = db_service.get_or_create_user(chat_id, full_name)
    tg_user_id = str(user_data.get("id"))
    db_service.ensure_user_exists(tg_user_id, user.id)
    bot_model = db_service.get_or_create_bot(Config.bot_token)
    session = db_service.get_active_session(user.id, bot_model.id)
    # Save user message
    msg_id = db_service.add_message(session.id, user.id, "user", text)
    # History for context
    history = db_service.fetch_history(session.id, limit_count=50)
    # Determine if final song was sent/received
    last_5_assistant = [m for m in history if m["role"] == "assistant"][-5:]
    is_final_song_received = any(m["content"] == "финальная версия песни получена пользователем" for m in last_5_assistant)
    is_final_song_sent = any(m["content"] == "финальная версия песни отправлена пользователю" for m in last_5_assistant)
    # Build flow state
    flow_state: FlowState = {
        "chat_id": chat_id,
        "text": text,
        "user_uuid": user.id,
        "session_uuid": session.id,
        "tg_user_id": tg_user_id,
        "last_messages": history,
        "intent": {},
        "emotion": {},
        "analysis_msg_id": msg_id,
        "is_final_song_received": is_final_song_received,
        "is_final_song_sent": is_final_song_sent,
    }
    # Run state machine
    await flow.run(flow_state)
    return {"statusCode": 200, "body": ""}


# For local testing only: run as script
if __name__ == "__main__":
    async def test():
        # Compose a fake incoming event for debugging
        body = {
            "message": {
                "message_id": 1,
                "from": {"id": 123456, "first_name": "Test", "last_name": "User"},
                "chat": {"id": 123456, "type": "private", "first_name": "Test"},
                "date": int(datetime.now().timestamp()),
                "text": "Привет, давай споём песню",
            }
        }
        await handler({"body": json.dumps(body)}, None)
    asyncio.run(test())