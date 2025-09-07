# Standard library imports
import logging
import random
from typing import Any, Dict

# Local imports
from mindset.config import Config
from mindset.database_factory import create_database_manager
from mindset.logger import get_default_logger
from mindset.telegram_bot import TelegramBot
from mindset.utils import Utils
from mindset.llm_manager import LLMManager
from mindset.moderation import ModerationService
from mindset.suno_manager import SunoManager
from mindset.langgraph_workflow import ConversationWorkflow
from mindset.langgraph_state import ConversationState

# Configuration from environment variables
config = Config.from_env()
# Создаем логгер с настройками из конфигурации
log_level = getattr(logging, config.log_level.upper(), logging.DEBUG)
logger = get_default_logger(config.log_name, log_level)
# Telegram bot
telegram_bot = TelegramBot(config)
# Database manager - using factory pattern for better error handling
config.database.type = 'postgresql'  # or 'duckdb'
db = create_database_manager(config, logger)
# Utils manager
utils = Utils(config, logger)
# LLM manager
llm = LLMManager(config, utils, logger)
# Moderation service
moderation_service = ModerationService(db, telegram_bot, logger)
# Suno manager
suno_manager = SunoManager(config, db, telegram_bot, utils, llm, logger)

# Initialize LangGraph workflow
workflow = ConversationWorkflow(config, llm, db, utils, telegram_bot, suno_manager, moderation_service, logger)

logger.debug("Configuration loaded")
logger.debug("LangGraph workflow initialized")


bot_id = db.get_or_create_bot(config.bot_token)
logger.debug("Bot initialized with ID %s", bot_id)

def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = utils.parse_body(event)
    logger.debug("Incoming body: %s", body)

    # Handle telegram callback query
    if "callback_query" in body:
        return telegram_bot.handle_callback_query(body, db, config.want_silence_message, bot_id, config.session_lifetime, llm)

    # Handle suno api callback
    if body.get("data") and body["data"].get("callbackType") and body["data"]["callbackType"] == "complete":
        return suno_manager.handle_suno_callback(body, bot_id, config.session_lifetime)

    message = body.get("message") or body.get("edited_message")
    if not message or not message.get("text"):
        return {"statusCode": 200, "body": ""}

    chat_id = message["chat"]["id"]
    text = message["text"]
    tg_msg_id = body["message"]["message_id"]
    user = message["from"]
    full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
    tg_user_id = user.get("id")

    # Валидация tg_user_id
    if not tg_user_id or not isinstance(tg_user_id, int):
        logger.error("Invalid tg_user_id: %s (type: %s), user data: %s", tg_user_id, type(tg_user_id), user)
        return {"statusCode": 200, "body": "Invalid user ID"}

    # Session & history
    tg_user_id_str = str(tg_user_id)
    user_uuid = db.get_or_create_user(chat_id, full_name)
    session_uuid = db.get_active_session(user_uuid, bot_id, config.session_lifetime)
    history = db.fetch_history(session_uuid, limit_count=50)
    db.ensure_user_exists(tg_user_id_str, user_uuid)

    # Check warnings/block
    if moderation_service.is_user_blocked(tg_user_id_str):
        return {"statusCode": 200, "body": "banned"}

    # Подготовка контекста сообщений
    ctx = utils.compute_message_context(history, text)
    last_8_messages = ctx["last_8_messages"]
    last_20_assistant_messages = ctx["last_20_assistant_messages"]
    last_5_assistant_messages = ctx["last_5_assistant_messages"]
    last_3_assistant_messages = ctx["last_3_assistant_messages"]
    last_8_user_messages = ctx["last_8_user_messages"]
    openai_msgs = ctx["openai_msgs"]

    # Determine song state flags
    is_final_song_received = any(
        msg["content"] == "финальная версия песни получена пользователем"
        for msg in last_5_assistant_messages
    )

    is_final_song_sent = any(
        msg["content"] == "финальная версия песни отправлена пользователю"
        for msg in last_5_assistant_messages
    )

    # Create initial state for LangGraph workflow
    initial_state: ConversationState = {
        "chat_id": str(chat_id),
        "user_message": text,
        "tg_msg_id": tg_msg_id,
        "tg_user_id": tg_user_id_str,
        "user_uuid": user_uuid,
        "session_uuid": session_uuid,
        "full_name": full_name,
        "history": history,
        "last_8_messages": last_8_messages,
        "last_20_assistant_messages": last_20_assistant_messages,
        "last_5_assistant_messages": last_5_assistant_messages,
        "last_3_assistant_messages": last_3_assistant_messages,
        "last_8_user_messages": last_8_user_messages,
        "openai_msgs": openai_msgs,
        "intent_analysis": None,
        "emotion_analysis": None,
        "msg_id": None,
        "is_final_song_received": is_final_song_received,
        "is_final_song_sent": is_final_song_sent,
        "is_confused": False,
        "confusion_handled": False,
        "song_generation_triggered": False,
        "feedback_handled": False,
        "ai_response": None,
        "song_data": None,
        "errors": [],
        "steps_completed": []
    }

    # Process the message through LangGraph workflow
    try:
        final_state = workflow.process_message(initial_state)

        # Log any errors that occurred during processing
        if final_state.get("errors"):
            for error in final_state["errors"]:
                logger.error("Workflow error: %s", error)

        logger.debug("Workflow completed. Steps: %s", final_state.get("steps_completed", []))

    except Exception as e:
        logger.exception("Workflow execution failed: %s", e)

        # Fallback to basic error response
        try:
            telegram_bot.send_message_chunks(chat_id, config.fallback_answer)
        except Exception:
            logger.exception("Failed to send fallback message")

    return {"statusCode": 200, "body": ""}
