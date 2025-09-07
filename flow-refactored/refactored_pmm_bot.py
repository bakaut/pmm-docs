"""
Refactored PMM bot using modern Python stack
================================================

This module contains a refactoring of the original PMM (ПойМойМир) bot
architecture to leverage a modern stack consisting of:

* **Aiogram** — asynchronous Telegram bot framework used to process
  incoming updates via webhook in Yandex Cloud Functions.
* **SQLAlchemy** — ORM layer replacing raw SQL queries and manual
  connection management.  Models and service objects encapsulate
  database interactions.
* **LangChain** — abstraction over LLM providers.  It powers both
  free‑form chat answers and structured tasks like intent and emotion
  classification.
* **LangGraph** — state machine library built on top of LangChain.
  The entire user flow of the bot is modeled as a state graph with
  explicit transitions.  This makes the flow easy to reason about and
  extend.
* **OpenAI** (via `langchain_openai`) — LLM backend.  You can swap
  providers without changing the rest of the code.

The code below is organised into several classes.  Each class is
responsible for a specific concern (database access, Telegram
communication, LLM requests, song generation, moderation).  At the
bottom of the module you will find an asynchronous `handler` function
which is suitable for deployment to Yandex Cloud Functions.  It uses
Aiogram internally to handle Telegram updates.

This is a skeleton and can be expanded further.  Some operations are
represented by placeholders (e.g. saving to Yandex Object Storage),
but the overall architecture illustrates how to compose these
technologies together.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph

# ---------------------------------------------------------------------------
# Logging configuration
#
# Reuse the JSON logger from the original code for structured logs.  You can
# customise the formatter or destination (stdout vs cloud logging) as needed.
try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("pmm_bot")
    logger.setLevel(logging.DEBUG)
    if jsonlogger:
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(level)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        logging.basicConfig(level=logging.DEBUG)
    return logger


logger = setup_logger()

# ---------------------------------------------------------------------------
# Database layer
#
# We model the database using SQLAlchemy ORM.  Replace the table
# definitions with ones that reflect your actual schema.  The service
# methods mirror the helpers from the original code but use ORM sessions
# instead of raw SQL.

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
    id = Column(String, primary_key=True)  # telegram user id as string
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
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime)
    analysis = Column(JSON, nullable=True)

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
    """Service encapsulating database operations via SQLAlchemy."""

    def __init__(self) -> None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # Construct DSN from individual env vars if DATABASE_URL is absent.
            host = os.getenv("DB_HOST")
            port = os.getenv("DB_PORT", "5432")
            name = os.getenv("DB_NAME")
            user = os.getenv("DB_USER")
            password = os.getenv("DB_PASSWORD")
            db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        # It is caller's responsibility to call Base.metadata.create_all() when
        # deploying the stack for the first time.  We do not call it here
        # automatically because Yandex Cloud Functions may not allow DDL.

    def get_session(self):
        return self.Session()

    # Helper methods mirroring the original code
    def get_or_create_bot(self, token: str, username: Optional[str] = None) -> BotModel:
        import hashlib

        token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()
        with self.get_session() as session:
            bot = session.query(BotModel).filter_by(token_hash=token_hash).first()
            if bot:
                return bot
            bot_id = str(uuid.uuid4())
            bot = BotModel(id=bot_id, token_hash=token_hash, username=username)
            session.add(bot)
            session.commit()
            logger.info("Created bot %s (token hash %s)", bot_id, token_hash)
            return bot

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

    def ensure_telegram_user(self, tg_user_id: str, user: UserModel) -> TelegramUserModel:
        with self.get_session() as session:
            tg_user = session.query(TelegramUserModel).filter_by(id=tg_user_id).first()
            if tg_user:
                return tg_user
            tg_user = TelegramUserModel(id=tg_user_id, user_id=user.id, warnings=0, blocked=False)
            session.add(tg_user)
            session.commit()
            return tg_user

    def new_session(self, user: UserModel, bot_id: str) -> ConversationSessionModel:
        with self.get_session() as session:
            # find an active session that hasn't expired
            cutoff = datetime.now(timezone.utc) - timedelta(hours=int(os.getenv("SESSION_LIFETIME", "87600")))
            existing = (
                session.query(ConversationSessionModel)
                .filter_by(user_id=user.id, bot_id=bot_id, ended_at=None)
                .order_by(ConversationSessionModel.started_at.desc())
                .first()
            )
            if existing and existing.started_at > cutoff:
                return existing
            sess_id = str(uuid.uuid4())
            conv = ConversationSessionModel(
                id=sess_id,
                user_id=user.id,
                bot_id=bot_id,
                started_at=datetime.now(timezone.utc),
                model=os.getenv("AI_MODEL", "openai/gpt-4o"),
            )
            session.add(conv)
            session.commit()
            logger.debug("Created new conversation session %s", sess_id)
            return conv

    def add_message(self, session_id: str, user_id: str, role: str, content: str, analysis: Optional[dict] = None) -> str:
        with self.get_session() as session:
            msg_id = str(uuid.uuid4())
            msg = MessageModel(
                id=msg_id,
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                created_at=datetime.now(timezone.utc),
                analysis=analysis,
            )
            session.add(msg)
            session.commit()
            return msg_id

    def get_last_messages(self, session_id: str, limit: int = 50) -> List[MessageModel]:
        with self.get_session() as session:
            return (
                session.query(MessageModel)
                .filter_by(session_id=session_id)
                .order_by(MessageModel.created_at.asc())
                .limit(limit)
                .all()
            )

    def save_song(self, song_id: str, user: UserModel, session: ConversationSessionModel, task_id: str, title: str, prompt: str, style: str, path: Optional[str] = None) -> None:
        with self.get_session() as session_:
            song = SongModel(
                id=song_id,
                user_id=user.id,
                session_id=session.id,
                task_id=task_id,
                title=title,
                prompt=prompt,
                style=style,
                path=path,
                created_at=datetime.now(timezone.utc),
            )
            session_.add(song)
            session_.commit()


# ---------------------------------------------------------------------------
# LLM service
#
# This service wraps LangChain's ChatOpenAI to provide methods for chat,
# intent detection and emotion detection.  Prompts are loaded from local
# files defined by the original code.  You can extend or modify the
# templates as needed.


class LLMService:
    def __init__(self) -> None:
        # Use OpenAI key via environment.  When using OpenRouter you can
        # supply "models" to the call as shown in the original code.  Here
        # we illustrate the simple case.
        openai_api_key = os.getenv("openai_key")
        ai_model = os.getenv("ai_model", "gpt-4o")
        # ChatOpenAI defaults to text-davinci model; specify temperature if needed
        self.chat = ChatOpenAI(openai_api_key=openai_api_key, model_name=ai_model)
        # Load system prompts from files.  In production these should be
        # packaged together with the code (for example, in a knowledge_bases
        # directory).
        def read_prompt(fname: str) -> str:
            path = os.path.join(os.path.dirname(__file__), "knowledge_bases", fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""

        self.system_prompt = read_prompt("system_prompt.txt")
        self.intent_prompt = read_prompt("determinate_intent.txt")
        self.emotion_prompt = read_prompt("detect_emotional_state.txt")
        self.prepare_suno_prompt = read_prompt("prepare_suno.txt")

    async def detect_intent(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Detect user intent using a short history of messages."""
        prompt = PromptTemplate.from_template(self.intent_prompt)
        # Build a simple conversation for intent detection
        conversation = [
            {"role": "system", "content": self.intent_prompt},
        ] + messages
        response = await self.chat.agenerate(conversation)
        try:
            return json.loads(response.generations[0][0].text)
        except Exception:
            # If parsing fails, return a fallback structure
            return {"intent": "unknown"}

    async def detect_emotion(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Detect user emotion via LLM."""
        conversation = [
            {"role": "system", "content": self.emotion_prompt},
        ] + messages
        response = await self.chat.agenerate(conversation)
        try:
            return json.loads(response.generations[0][0].text)
        except Exception:
            return {"emotions": []}

    async def chat_reply(self, messages: List[Dict[str, str]]) -> str:
        """Generate a chat reply given the conversation history."""
        conversation = [
            {"role": "system", "content": self.system_prompt},
        ] + messages
        response = await self.chat.agenerate(conversation)
        return response.generations[0][0].text

    async def prepare_suno(self, messages: List[Dict[str, str]]) -> Dict[str, str]:
        """Prepare lyrics, style and title for song generation.
        This function mirrors the original `llm_conversation` call with the
        prepare_suno system prompt.
        """
        conversation = [
            {"role": "system", "content": self.prepare_suno_prompt},
        ] + messages
        response = await self.chat.agenerate(conversation)
        try:
            return json.loads(response.generations[0][0].text)
        except Exception:
            return {"lyrics": "", "style": "", "name": ""}


# ---------------------------------------------------------------------------
# Suno API service
#
# Responsible for interacting with the Suno API to generate songs and for
# storing and retrieving MP3s.  Yandex Object Storage integration (via
# boto3) could be added here.


class SunoService:
    def __init__(self) -> None:
        self.api_url = os.getenv("suno_api_url", "https://apibox.erweima.ai/api/v1/generate")
        self.api_key = os.getenv("suno_api_key")
        self.model = os.getenv("suno_model", "V4_5")
        self.callback_url = os.getenv("suno_callback_url")
        # Reuse a shared HTTP session for performance
        self.session = aiohttp.ClientSession()

    async def request_song(self, lyrics: str, style: str, title: str) -> Optional[str]:
        """Send a generation request to the Suno API and return a task ID."""
        if not self.api_key:
            logger.error("Suno API key not configured")
            return None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "prompt": lyrics,
            "style": style,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": self.model,
            "callBackUrl": self.callback_url,
        }
        async with self.session.post(self.api_url, json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                logger.error("Suno API returned %s", resp.status)
                return None
            data = await resp.json()
            return data.get("data", {}).get("taskId")

    async def close(self) -> None:
        await self.session.close()


# ---------------------------------------------------------------------------
# Moderation service
#
# Encapsulates calls to the OpenAI moderation API.  See the original code
# for context.  Returns True when text should be flagged.


class ModerationService:
    def __init__(self) -> None:
        self.api_key = os.getenv("openai_key")
        self.session = aiohttp.ClientSession()

    async def is_flagged(self, text: str) -> bool:
        url = "https://api.openai.com/v1/moderations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text, "model": "omni-moderation-latest"}
        async with self.session.post(url, json=payload, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                logger.error("Moderation API returned %s", resp.status)
                return False
            data = await resp.json()
            return data.get("results", [{}])[0].get("flagged", False)

    async def close(self) -> None:
        await self.session.close()


# ---------------------------------------------------------------------------
# LangGraph user flow
#
# The entire conversational flow is modeled as a state machine.  Each node
# performs a discrete task (intent detection, emotion detection, generating
# a reply, or triggering an external API) and returns the updated state.


class FlowState(TypedDict):
    chat_id: int
    message_text: str
    user_id: str
    session_id: str
    last_messages: List[Dict[str, str]]  # history in LLM-friendly format
    intent: Optional[Dict[str, Any]]
    emotion: Optional[Dict[str, Any]]
    final_song_generated: bool
    final_song_received: bool
    response: Optional[str]


class UserFlow:
    def __init__(
        self,
        llm_service: LLMService,
        suno_service: SunoService,
        moderation_service: ModerationService,
    ) -> None:
        self.llm = llm_service
        self.suno = suno_service
        self.moderation = moderation_service
        self.graph = StateGraph(FlowState)
        self._build_graph()
        self.compiled = self.graph.compile()

    def _build_graph(self) -> None:
        # Node: detect intent
        @self.graph.add_node
        async def detect_intent(state: FlowState) -> FlowState:
            state["intent"] = await self.llm.detect_intent(state["last_messages"])
            return state

        # Node: detect emotion
        @self.graph.add_node
        async def detect_emotion(state: FlowState) -> FlowState:
            state["emotion"] = await self.llm.detect_emotion(state["last_messages"])
            return state

        # Node: check confusion and maybe short‑circuit
        @self.graph.add_node
        async def check_confusion(state: FlowState) -> FlowState:
            emotions = state.get("emotion", {}).get("emotions", [])
            confused = any(e.get("name") == "Растерянность" and e.get("intensity", 0) > 90 for e in emotions)
            if confused:
                # Choose one of the predefined messages (mirroring CONFUSED_INTENT_ANSWER)
                responses = [
                    "Ты можешь быть с собой честен здесь. Без страха.",
                    "Чем точнее ты поделишься — тем точнее я смогу услышать тебя.",
                    "Иногда самая красивая строчка рождается из фразы \"я боюсь сказать, что думаю\".",
                    "В этом месте можно говорить правду. Даже если она шепотом.",
                ]
                import random

                state["response"] = random.choice(responses)
                return state
            return state

        # Node: maybe generate a song
        @self.graph.add_node
        async def maybe_generate_song(state: FlowState) -> FlowState:
            intent = state.get("intent", {}).get("intent")
            if intent == "finalize_song" and not state["final_song_generated"]:
                # Ask the LLM to prepare lyrics and style
                result = await self.llm.prepare_suno(state["last_messages"][-3:])
                lyrics = result.get("lyrics", "")
                style = result.get("style", "")
                title = result.get("name", "Песня")
                task_id = await self.suno.request_song(lyrics, style, title)
                if task_id:
                    # update state so we don't generate again
                    state["final_song_generated"] = True
                    state["response"] = "Твоя песня уже в пути. Дай ей немного времени — она рождается 🌿"
                return state
            return state

        # Node: maybe send feedback
        @self.graph.add_node
        async def maybe_feedback(state: FlowState) -> FlowState:
            intent = state.get("intent", {}).get("intent")
            if intent == "feedback" and state["final_song_received"]:
                # Send a feedback audio or markup.  In Aiogram handler we will
                # render a reply depending on this state["response"].
                state["response"] = "Спасибо за доверие!\n\n🔁 - Поделиться песней с другом \n🤗 - Обнять автора"
                return state
            return state

        # Node: generic chat reply
        @self.graph.add_node
        async def chat_reply(state: FlowState) -> FlowState:
            # If no earlier response was set by previous nodes, generate one
            if not state.get("response"):
                reply = await self.llm.chat_reply(state["last_messages"])
                # If moderation flags the reply, replace with a fallback
                if await self.moderation.is_flagged(reply):
                    reply = "Сейчас не могу ответить, загляни чуть позже 🌿"
                state["response"] = reply
            return state

        # Entry point: detect intent
        self.graph.set_entry_point(detect_intent)

        # Sequence of nodes: detect intent -> detect emotion -> check confusion -> maybe generate song -> maybe feedback -> chat reply
        self.graph.add_edge(detect_intent, detect_emotion)
        self.graph.add_edge(detect_emotion, check_confusion)
        self.graph.add_edge(check_confusion, maybe_generate_song)
        self.graph.add_edge(maybe_generate_song, maybe_feedback)
        self.graph.add_edge(maybe_feedback, chat_reply)

    async def run(self, state: FlowState) -> FlowState:
        return await self.compiled.apredict(state)


# ---------------------------------------------------------------------------
# Telegram bot service
#
# Uses Aiogram to handle incoming updates.  The dispatcher routes
# messages and callbacks to corresponding handlers.  Each handler uses
# `DatabaseService` to persist events and `UserFlow` to drive the
# conversation state machine.


class TelegramBotService:
    def __init__(
        self,
        bot_token: str,
        db_service: DatabaseService,
        flow: UserFlow,
    ) -> None:
        self.bot = Bot(bot_token)
        self.dp = Dispatcher(self.bot)
        self.db = db_service
        self.flow = flow
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.dp.message_handler()
        async def handle_message(message: aiotypes.Message) -> None:
            chat_id = message.chat.id
            text = message.text or ""
            user_data = message.from_user
            full_name = f"{user_data.first_name or ''} {user_data.last_name or ''}".strip()

            # Ensure user and session
            user = self.db.get_or_create_user(chat_id, full_name)
            tg_user_id = str(user_data.id)
            tg_user = self.db.ensure_telegram_user(tg_user_id, user)

            # Create or reuse conversation session
            bot_model = self.db.get_or_create_bot(os.getenv("bot_token"))
            session = self.db.new_session(user, bot_model.id)

            # Persist the incoming message
            self.db.add_message(session.id, user.id, "user", text)

            # Load last few messages for context.  We keep the last 8 messages
            # similar to the original code.  Only content and role are passed
            # to the LLM service.
            history_models = self.db.get_last_messages(session.id, limit=8)
            last_messages = [
                {"role": m.role, "content": m.content} for m in history_models
            ]

            # Build initial flow state
            flow_state: FlowState = {
                "chat_id": chat_id,
                "message_text": text,
                "user_id": user.id,
                "session_id": session.id,
                "last_messages": last_messages,
                "intent": None,
                "emotion": None,
                "final_song_generated": False,
                "final_song_received": False,
                "response": None,
            }

            # Run the state machine
            new_state = await self.flow.run(flow_state)

            # Save assistant message
            if new_state.get("response"):
                self.db.add_message(session.id, user.id, "assistant", new_state["response"])

            # Send reply to Telegram
            await message.answer(new_state["response"])

        # Example callback handler for inline buttons (e.g. hug_author)
        @self.dp.callback_query_handler(lambda c: True)
        async def handle_callback(callback: aiotypes.CallbackQuery) -> None:
            data = callback.data
            if data == "hug_author":
                await callback.answer("💞 Автору переданы объятия!", show_alert=False)

    async def process_event(self, event: Dict[str, Any]) -> None:
        update = json.loads(event["body"])
        Bot.set_current(self.bot)
        update_obj = aiotypes.Update.to_object(update)
        await self.dp.process_update(update_obj)


# ---------------------------------------------------------------------------
# Yandex Cloud Function handler
#
# Entry point for serverless deployment.  Instantiates the services and
# processes each incoming webhook event.  Because Aiogram creates a new
# dispatcher per invocation, the overhead is minimal and there is no
# global state between invocations.  All classes are imported at module
# level to comply with the user requirement.


async def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Yandex Cloud function entry point.  Must be asynchronous."""
    # Initialise services on each call.  In a real deployment you might
    # cache these in global variables to reuse between invocations and
    # reduce cold start time.
    db_service = DatabaseService()
    llm_service = LLMService()
    suno_service = SunoService()
    moderation_service = ModerationService()
    flow = UserFlow(llm_service, suno_service, moderation_service)
    bot_token = os.getenv("bot_token")
    telegram_service = TelegramBotService(bot_token, db_service, flow)
    # Process the event through the Aiogram dispatcher
    await telegram_service.process_event(event)
    return {"statusCode": 200, "body": "ok"}


# When running locally for debugging you can execute the handler as an
# asynchronous function.  This stub allows invoking the handler with a
# sample event.  It is not executed in the Yandex Cloud environment.
if __name__ == "__main__":
    import asyncio

    # Example of a mock event for local testing
    mock_event = {
        "body": json.dumps({
            "update_id": 10000,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                },
                "chat": {
                    "id": 123456,
                    "type": "private",
                    "first_name": "Test",
                    "username": "testuser",
                },
                "date": int(datetime.now().timestamp()),
                "text": "Привет, сделай песню о любви",
            }
        })
    }

    # Run the handler once.  Requires that environment variables be set
    async def run_handler():
        await handler(mock_event, None)

    asyncio.run(run_handler())