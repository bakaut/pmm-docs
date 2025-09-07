# Standard library imports
import logging
import random
from typing import Any, Dict

# Local imports
from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.logger import get_default_logger
from mindset.telegram_bot import TelegramBot
from mindset.utils import Utils
from mindset.llm_manager import LLMManager
from mindset.moderation import ModerationService
from mindset.suno_manager import SunoManager
from mindset.cache_manager import CacheManager


# Configuration from environment variables
config = Config.from_env()
# Создаем логгер с настройками из конфигурации
log_level = getattr(logging, config.log_level.upper(), logging.DEBUG)
logger = get_default_logger(config.log_name, log_level)
# Telegram bot
telegram_bot = TelegramBot(config)
# Database manager
db = DatabaseManager(config, logger)
# Utils manager
utils = Utils(config, logger)
# LLM manager
llm = LLMManager(config, utils, logger)
# Moderation service
moderation_service = ModerationService(db, telegram_bot, logger)
# Suno manager
suno_manager = SunoManager(config, db, telegram_bot, utils, logger)
# Cache manager
cache_manager = CacheManager(config, llm, logger)

logger.debug("Configuration loaded")


bot_id = db.get_or_create_bot(config.bot_token)
logger.debug("Bot initialized with ID %s", bot_id)

def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = utils.parse_body(event)
    logger.debug("Incoming body: %s", body)

    # Handle telegram callback query
    if "callback_query" in body:
        return telegram_bot.handle_callback_query(body, db, config.want_silence_message, bot_id, config.session_lifetime)

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

    # testing cache manager
    logger.debug("Testing cache manager")

    # Check cache health and index configuration
    health = cache_manager.health_check()
    logger.debug("Cache health: %s", health)

    index_info = cache_manager.get_index_info()
    logger.debug("Index info: %s", index_info)

    # Clear any existing test cache
    cache_manager.clear_tenant_cache("test_key")

    # Add test entries with Russian text
    cache_key1 = cache_manager.put_cache("test_key", str(tg_user_id), "my|signature", f"Данный текст необходим для тестирования кеша {tg_user_id}-{tg_msg_id}")
    cache_key2 = cache_manager.put_cache("test_key", str(tg_user_id), "my|signature2", f"Текст нужен для тестирования кеширования {tg_user_id}-{tg_msg_id}")
    logger.debug("Created cache entries: %s, %s", cache_key1, cache_key2)

    # Verify entries were created
    cache_entry1 = cache_manager.get_cache_by_signature("test_key", "my|signature")
    logger.debug("Cache entry 1: %s", cache_entry1)

    # Test semantic search
    semantic_result = cache_manager.semantic_search("test_key", "Текст нужен для тестирования кеширования", 5, str(tg_user_id))
    logger.debug("Semantic search result: %s", semantic_result)

    # Test full-text search with detailed debugging
    search_query = "тестиро"
    logger.debug("Testing full-text search with query: '%s'", search_query)

    # Try the actual search
    text_search_result = cache_manager.text_search("test_key", search_query, str(tg_user_id), 5)
    logger.debug("Text search result: %s", text_search_result)

    # Try different search variations
    test_queries = ["тестиро", "тестирования", "текст", "кеш", "необходим"]
    for test_query in test_queries:
        result = cache_manager.text_search("test_key", test_query, str(tg_user_id), 5)
        logger.debug("Search for '%s': %d results", test_query, result.get("total", 0), extra={"result": result})

    # Get cache statistics
    stats = cache_manager.get_cache_stats("test_key")
    logger.debug("Cache statistics", extra={"stats": stats})

    # return {"statusCode": 200, "body": ""}

    # Валидация tg_user_id
    if not tg_user_id or not isinstance(tg_user_id, int):
        logger.error("Invalid tg_user_id: %s (type: %s), user data: %s", tg_user_id, type(tg_user_id), user)
        return {"statusCode": 200, "body": "Invalid user ID"}

    tg_user_id_str = str(tg_user_id)
    user_uuid = db.get_or_create_user(chat_id, full_name)

    # Session & history
    session_uuid = db.get_active_session(user_uuid, bot_id, config.session_lifetime)
    history = db.fetch_history(session_uuid)
    
    # testing
    ctx = utils.compute_message_context(history, text)
    last_8_messages = ctx["last_8_messages"]
    user_history_flat = utils.flatten_messages(history, 8)['user']

    cache_manager.put_cache("history", tg_user_id_str, f"session|{session_uuid}", user_history_flat, 36)
    cached_history = cache_manager.get_cache_by_signature("history", f"session|{session_uuid}")
    if cached_history:
        logger.debug("Retrieved cached history: %s", cached_history)
    # testing end

    db.ensure_user_exists(tg_user_id_str, user_uuid)
    return {"statusCode": 200, "body": ""}

    # Check warnings/block
    if moderation_service.is_user_blocked(tg_user_id_str):
        return {"statusCode": 200, "body": "banned"}

    # Save user message
    msg_id = db.save_message(session_uuid, user_uuid, "user", text, llm.embd_text(text), tg_msg_id)

    # Подготовка контекста сообщений
    ctx = utils.compute_message_context(history, text)
    last_8_messages = ctx["last_8_messages"]
    last_20_assistant_messages = ctx["last_20_assistant_messages"]
    last_5_assistant_messages = ctx["last_5_assistant_messages"]
    last_3_assistant_messages = ctx["last_3_assistant_messages"]
    last_8_user_messages = ctx["last_8_user_messages"]
    openai_msgs = ctx["openai_msgs"]

    # Detect intent and emotion
    detect_intent = llm.llm_conversation(last_8_messages, config.system_prompt_intent)
    detect_emotion = llm.llm_conversation(last_8_user_messages, config.system_prompt_detect_emotion)

    logger.debug("User emotion: %s", detect_emotion)
    logger.debug("User intent: %s", detect_intent)

    # Save intent and emotion analysis to DB
    analysis = {"intent": detect_intent, "emotion": detect_emotion}
    db.update_message_analysis(msg_id, analysis)

    is_final_song_received = None
    is_final_song_sent = None

    is_final_song_received = any(
        msg["content"] == "финальная версия песни получена пользователем"
        for msg in last_5_assistant_messages
    )

    is_final_song_sent = any(
        msg["content"] == "финальная версия песни отправлена пользователю"
        for msg in last_5_assistant_messages
    )

    # Проверяем наличие 'Растерянность' среди эмоций нового формата
    is_confused = any(
        e.get("name") == "Растерянность" and e.get("intensity", 0) > 90
        for e in detect_emotion.get("emotions", [])
    )
    if is_confused:
        if not any(msg["content"] == "confused_send" for msg in last_20_assistant_messages):
            if random.choice([True, False]):
                # Отправляем текст
                answer = random.choice(config.confused_intent_answers)
                db.save_message(session_uuid, user_uuid, "assistant", f"{answer}", llm.embd_text(answer), tg_msg_id)
                telegram_bot.send_message_chunks(chat_id, answer)
            else:
                # Отправляем аудио
                telegram_bot.send_audio(chat_id, audio_url=config.confused_intent_answer_mp3, title="Ты можешь...")
            db.save_message(session_uuid, user_uuid, "assistant", "confused_send", llm.embd_text("confused_send"), tg_msg_id)
            return {"statusCode": 200, "body": ""}

    if detect_intent["intent"] == "finalize_song" and not (is_final_song_received or is_final_song_sent):
        logger.debug("Song request detected")
        logger.debug("Parse song from history")
        get_song = llm.llm_conversation(last_3_assistant_messages, config.system_prompt_prepare_suno)
        lyrics = get_song["lyrics"]
        style = get_song["style"]
        title = get_song["name"]
        logger.debug("Generate song with Suno API")
        song = suno_manager.request_suno(lyrics, style, title)
        if not song:
            logger.error("Failed to generate song with Suno API")
            telegram_bot.send_message_chunks(chat_id, config.fallback_answer)
            db.save_message(session_uuid, user_uuid, "assistant", "ошибка генерации песни")
            return {"statusCode": 200, "body": ""}
        task_id = song["data"]["taskId"]

        telegram_bot.send_message_chunks(chat_id, config.song_generating_message)
        db.save_song(user_uuid, session_uuid, task_id, title, lyrics, style)
        db.save_message(session_uuid, user_uuid, "assistant", config.song_generating_message, llm.embd_text(config.song_generating_message), tg_msg_id)
        db.save_message(session_uuid, user_uuid, "assistant", "финальная версия песни отправлена пользователю", llm.embd_text("финальная версия песни отправлена пользователю"), tg_msg_id)
        logger.debug("Suno task ID: %s", task_id)
        return {"statusCode": 200, "body": ""}

    if detect_intent["intent"] == "feedback" and is_final_song_received:
        if not any(msg["content"] == "feedback_final_send" for msg in last_5_assistant_messages):
            logger.debug("Feedback intent detected, user emotion: %s", detect_emotion)
            telegram_bot.send_message_chunks(chat_id, config.song_received_message, config.song_received_markup)
            db.save_message(session_uuid, user_uuid, "assistant", "feedback_final_send", llm.embd_text("feedback_final_send"), tg_msg_id)
            return {"statusCode": 200, "body": ""}

    ai_answer = llm.llm_call(openai_msgs, chat_id, tg_user_id_str, moderation_service.moderate_user)

    if ai_answer and ai_answer != config.fallback_answer:
        # Save assistant response
        db.save_message(session_uuid, user_uuid, "assistant", ai_answer, llm.embd_text(ai_answer), tg_msg_id)

    # Send back to Telegram
    try:
        telegram_bot.send_message_chunks(chat_id, ai_answer)
    except Exception:
        logger.exception("Failed to send message to Telegram %s", chat_id)

    return {"statusCode": 200, "body": ""}
