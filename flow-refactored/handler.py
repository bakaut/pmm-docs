"""Request handler coordinating all services.

This module binds together the database layer, external API clients and
application logic. It demonstrates three Clean Code practices:

1. **Meaningful names** – methods and variables clearly indicate their
   purpose, reducing the need for comments.
2. **Small functions with single responsibility** – each method performs
   one logical task, whether it’s fetching a session, saving a message or
   responding to a callback.
3. **Don’t Repeat Yourself (DRY)** – repeated patterns like inserting
   messages into the database are encapsulated in helper methods.
"""

import json
import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .config import Config
from .database import Database
from .telegram_client import TelegramClient
from .suno_client import SunoClient
from .llm_client import LLMClient
from .utilities import parse_body, get_last_messages


class Handler:
    """High‑level orchestrator for the bot’s logic."""

    CONFUSED_TEXTS: List[str] = [
        "Ты можешь быть с собой честен здесь. Без страха. Даже если честность сейчас — это: \"Я не знаю, что чувствую\". Это уже начало песни...",
        "Чем точнее ты поделишься — тем точнее я смогу услышать тебя. А значит, и песня будет ближе к тебе самому...",
        "Иногда самая красивая строчка рождается из фразы \"я боюсь сказать, что думаю\"... Это не слабость. Это глубина.",
        "В этом месте можно говорить правду. Даже если она шепотом.",
        "💬 Отклики других людей — чтобы почувствовать, как звучит _ПойМойМир_ в чужих сердцах: https://poymoymir.ru/feedback/",
        "🎧 Подкасты о проекте — мягкое знакомство с тем, как здесь всё устроено: https://poymoymir.ru/feedback/",
    ]

    def __init__(self, config: Config) -> None:
        self.config = config
        self.db = Database(config)
        self.telegram = TelegramClient(config)
        self.suno = SunoClient(config)
        self.llm = LLMClient(config)
        self.bot_id = self._get_or_create_bot(config.bot_token)

    # -- Database helper methods --
    def _get_or_create_bot(self, token: str) -> str:
        token_hash = uuid.uuid5(uuid.NAMESPACE_DNS, token).hex
        rec = self.db.query_one("SELECT id FROM bots WHERE token = :token LIMIT 1", (token_hash,))
        if rec:
            return rec['id']
        bot_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO bots(id, token, username, owner_id) VALUES (:id, :token, :username, :owner_id)",
            (bot_id, token_hash, None, None),
        )
        return bot_id

    def _get_or_create_user(self, chat_id: int, full_name: str) -> str:
        rec = self.db.query_one("SELECT id FROM users WHERE chat_id = :chat_id LIMIT 1", (chat_id,))
        if rec:
            return rec['id']
        user_uuid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO users(id, chat_id, full_name) VALUES (:id, :chat_id, :full_name)",
            (user_uuid, chat_id, full_name),
        )
        return user_uuid

    def _active_session(self, user_uuid: str) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.session_lifetime)
        rec = self.db.query_one(
            "SELECT id, started_at FROM conversation_sessions WHERE user_id = :user_id AND bot_id = :bot_id AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
            (user_uuid, self.bot_id),
        )
        if rec and rec.get('started_at') and rec['started_at'] > cutoff:
            return rec['id']
        session_uuid = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO conversation_sessions(id, user_id, bot_id, started_at, model) VALUES (:id, :user_id, :bot_id, NOW(), :model)",
            (session_uuid, user_uuid, self.bot_id, self.config.ai_model),
        )
        return session_uuid

    def _save_message(self, session_id: str, user_id: str, role: str, content: str, analysis: Optional[Dict[str, Any]] = None) -> str:
        message_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO messages(id, session_id, user_id, role, content, analysis, created_at) VALUES (:id, :session_id, :user_id, :role, :content, :analysis, NOW())",
            (message_id, session_id, user_id, role, content, json.dumps(analysis) if analysis else None),
        )
        return message_id

    # -- Main entry point --
    def handle(self, event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        body = parse_body(event)
        if isinstance(body, dict) and 'message' in body:
            return self._handle_message(body['message'])
        if isinstance(body, dict) and 'callback_query' in body:
            self._handle_callback(body['callback_query'])
            return {'statusCode': 200, 'body': ''}
        # Other event types can be handled here
        return {'statusCode': 200, 'body': ''}

    # -- Message processing --
    def _handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        chat_id = message['chat']['id']
        text = message.get('text', '')
        user = message['from']
        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        user_uuid = self._get_or_create_user(chat_id, full_name)
        session_id = self._active_session(user_uuid)
        # Save user message
        self._save_message(session_id, user_uuid, 'user', text)
        # Fetch history
        history = self.db.query_all("SELECT role, content FROM messages WHERE session_id = :sid ORDER BY created_at ASC", (session_id,))
        # Build prompt
        last_msgs = get_last_messages(history, 8, force_last_user=True)
        # Detect intent and emotion (pseudo)
        intent = self.llm.call_conversation(last_msgs, system_message=open('knowledge_bases/determinate_intent.txt', encoding='utf-8').read())
        emotion = self.llm.call_conversation(last_msgs, system_message=open('knowledge_bases/detect_emotional_state.txt', encoding='utf-8').read())
        # Save analysis
        self._save_message(session_id, user_uuid, 'assistant', '', {'intent': intent, 'emotion': emotion})
        # Respond based on intent (simplified)
        if intent.get('intent') == 'greet':
            self.telegram.send_message(chat_id, 'Привет! Чем могу помочь?')
        else:
            reply = self.llm.call_with_tools(
                [{'role': 'system', 'content': open('system_prompt.txt', encoding='utf-8').read()}, *history, {'role': 'user', 'content': text}],
                tools=[],
            )
            self.telegram.send_message(chat_id, reply)
        return {'statusCode': 200, 'body': ''}

    # -- Callback processing --
    def _handle_callback(self, callback: Dict[str, Any]) -> None:
        data = callback['data']
        callback_id = callback['id']
        if data == 'hug_author':
            self.telegram.answer_callback(callback_id, '💞 Автору переданы объятия!')