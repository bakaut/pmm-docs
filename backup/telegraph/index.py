# Standard library imports
import logging
import random
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Local imports
from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.logger import get_default_logger
from mindset.telegram_bot import TelegramBot
from mindset.utils import Utils
from mindset.llm_manager import LLMManager
from mindset.moderation import ModerationService
from mindset.suno_manager import SunoManager
from mindset.semantic_search import SemanticSearch
from mindset.telegraph import TelegraphManager

# Configuration from environment variables
config = Config.from_env()
# Создаем логгер с настройками из конфигурации
log_level = getattr(logging, config.log_level.upper(), logging.DEBUG)
logger = get_default_logger(config.log_name, log_level)
# Telegram bot
telegram_bot = TelegramBot(config)
# Database manager - using direct instantiation instead of factory pattern
db = DatabaseManager(config, logger)
# Utils manager
utils = Utils(config, logger)
# LLM manager
llm = LLMManager(config, utils, logger)
# Moderation service
moderation_service = ModerationService(db, telegram_bot, logger)
# Suno manager
suno_manager = SunoManager(config, db, telegram_bot, utils, llm, logger)
# Semantic search manager
searcher = SemanticSearch(config, logger)
# Telegraph manager
telegraph_manager = TelegraphManager(config)

logger.debug("Configuration loaded")

bot_id = db.get_or_create_bot(config.bot_token)
logger.debug("Bot initialized with ID %s", bot_id)

def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = utils.parse_body(event)
    logger.debug("Incoming body: %s", body)
    return {"statusCode": 200, "body": "ok"}
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

    # Session and user management
    tg_user_id_str = str(tg_user_id)
    user_uuid = db.get_or_create_user(chat_id, full_name)
    session_uuid = db.get_active_session(user_uuid, bot_id, config.session_lifetime)
    db.ensure_user_exists(tg_user_id_str, user_uuid)

    # Check warnings/block
    if moderation_service.is_user_blocked(tg_user_id_str):
        return {"statusCode": 200, "body": "banned"}

    # Initialize system Telegraph pages
    system_page_urls = telegram_bot.init_telegraph_pages(telegraph_manager, db)
    logger.debug("System Telegraph pages initialized: %s", system_page_urls)

    # Create and pin personal Telegraph page for the user
    personal_page_url = telegram_bot.create_and_pin_user_telegraph_page(
        db, 
        telegraph_manager, 
        tg_user_id, 
        chat_id,
        session_uuid  # Pass session_uuid to save pinned message ID
    )
    
    if personal_page_url:
        logger.debug("Personal Telegraph page created and pinned for user %s: %s", tg_user_id, personal_page_url)
    else:
        logger.warning("Failed to create or pin personal Telegraph page for user %s", tg_user_id)
    return {"statusCode": 200, "body": "banned"}
    # Save user message
    msg_id = db.save_message(session_uuid, user_uuid, "user", text, llm.embd_text(text), tg_msg_id)

    # Подготовка контекста сообщений
    history = db.fetch_history(session_uuid, limit_count=50) # move to the default config
    ctx = utils.compute_message_context(history,text,max_tokens=900,deviation=50) # move to the default config
    last_8_messages = ctx["last_8_messages"]
    last_20_assistant_messages = ctx["last_20_assistant_messages"]
    last_5_assistant_messages = ctx["last_5_assistant_messages"]
    last_3_assistant_messages = ctx["last_3_assistant_messages"]
    last_8_user_messages = ctx["last_8_user_messages"]
    openai_msgs = ctx["openai_msgs"]
    summary_messages = ctx["summary_messages"]
    create_summary = {}
    search_sing_song = searcher.search_phrase(text, "finalize_song", threshold=0.7)

    is_text_sing_song = True if search_sing_song.get("matched") else False
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
    is_summarization_needed = True if summary_messages else False

    # Detect intent emotion and state - in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_intent = executor.submit(llm.llm_conversation, last_8_messages, config.system_prompt_intent, True)
        future_emotion = executor.submit(llm.llm_conversation, last_8_user_messages, config.system_prompt_detect_emotion, True)
        future_state = executor.submit(llm.llm_conversation, last_8_messages, config.system_prompt_detect_state, True)

        # Collect results as they complete
        detect_intent = future_intent.result()
        detect_emotion = future_emotion.result()
        detect_state = future_state.result()

        if summary_messages:
            future_summary = executor.submit(llm.llm_conversation, summary_messages, config.system_prompt_summarization, True)
            create_summary = future_summary.result()

    logger.debug("User emotion: %s", detect_emotion)
    logger.debug("User intent: %s", detect_intent)
    logger.debug("User state: %s", detect_state)
    logger.debug("Conversation summary:", extra={"summary": create_summary})

    state_reason = detect_state.get("reason")
    state_reason_search = searcher.search_phrase(state_reason, "cannot_sing", threshold=0.7)

    is_state_uncertain = True if detect_state.get("result_type") == "UncertainResult" else False
    is_state_cannnot_sing = True if state_reason_search.get("matched") else False
    if is_state_cannnot_sing and is_state_uncertain:
        detect_state["result_type"] = "done"
    is_confused = any(
        e.get("name") == "Растерянность" and e.get("intensity", 0) > 90
        for e in detect_emotion.get("emotions", [])
    )
    is_intent_finalize_song = True if (detect_intent.get("result_type") == "finalize_song" or is_text_sing_song) and not (is_final_song_received or is_final_song_sent) else False
    is_intent_very_fast = True if (detect_intent.get("result_type") == "finalize_song" or is_text_sing_song) and (is_final_song_received or is_final_song_sent) else False
    is_intent_feedback = detect_intent["result_type"] == "feedback" and is_final_song_received

    # Save intent and emotion analysis to DB
    analysis = {"intent": detect_intent, "emotion": detect_emotion}
    db.update_message_analysis(msg_id, analysis)

    # Save intent and state to the new statuses table
    db.save_status(
        session_uuid,
        user_uuid,
        msg_id,
        state=detect_state.get("result_type") if isinstance(detect_state, dict) else str(detect_state),
        state_reason=detect_state.get("reason") if isinstance(detect_state, dict) else None,
        intent=detect_intent.get("result_type") if isinstance(detect_intent, dict) else str(detect_intent),
        intent_reason=detect_intent.get("reason") if isinstance(detect_intent, dict) else None
    )

    if is_summarization_needed:
        summary_text = create_summary.get("summary_brief", "")
        summary_metadata = create_summary
        db.save_memory(
            session_id=session_uuid,
            msg_id=msg_id,
            m_type="summary",
            text=summary_text,
            trigger="tokens",
            metadata=summary_metadata
        )
        db.save_message(session_uuid, user_uuid, "assistant", config.summarization_message, llm.embd_text(config.summarization_message), tg_msg_id)

    if is_intent_very_fast:
        logger.debug("User is trying to get the song too fast")
        assistant_msg_id = telegram_bot.send_message_chunks(chat_id, "Мы уже недавно создали песню, не торопитесь! Подождите немного, прежде чем просить новую.")
        db.save_message(session_uuid, user_uuid, "assistant", "Мы уже недавно создали песню, не торопитесь! Подождите немного, прежде чем просить новую.", llm.embd_text("Мы уже недавно создали песню, не торопитесь! Подождите немного, прежде чем просить новую."), assistant_msg_id)
        db.save_message(session_uuid, user_uuid, "user", text, llm.embd_text(text), tg_msg_id)
        return {"statusCode": 200, "body": ""}

    # Проверяем наличие 'Растерянность' среди эмоций нового формата
    if is_confused:
        if not any(msg["content"] == "confused_send" for msg in last_20_assistant_messages):
            if random.choice([True, False]):
                # Отправляем текст
                answer = random.choice(config.confused_intent_answers)
                assistant_msg_id = telegram_bot.send_message_chunks(chat_id, answer)
                db.save_message(session_uuid, user_uuid, "assistant", f"{answer}", llm.embd_text(answer), assistant_msg_id)
            else:
                # Отправляем аудио
                assistant_msg_id = telegram_bot.send_audio(chat_id, audio_url=config.confused_intent_answer_mp3, title="Ты можешь...")
                db.save_message(session_uuid, user_uuid, "assistant", "confused_send", llm.embd_text("confused_audio_send"), assistant_msg_id)
            db.save_message(session_uuid, user_uuid, "user", text, llm.embd_text(text), tg_msg_id)
            return {"statusCode": 200, "body": ""}

    if is_intent_finalize_song:
        logger.debug("Song request detected, parse song from history")
        try:
            get_song = llm.llm_conversation(last_3_assistant_messages, config.system_prompt_prepare_suno, True)
        except Exception as e:
            logger.exception("Failed to parse song details:", stack_info=True, exc_info=True, extra={"error": str(e), "response": get_song})
            assistant_msg_id = telegram_bot.send_message_chunks(chat_id, config.fallback_answer)
            db.save_message(session_uuid, user_uuid, "assistant", "ошибка парсинга песни", llm.embd_text("ошибка парсинга песни"), assistant_msg_id)
            return {"statusCode": 200, "body": ""}
        lyrics = get_song["lyrics"]
        style = get_song["style"]
        title = get_song["name"]
        logger.debug("Generate song with Suno API")
        song = suno_manager.request_suno(lyrics, style, title)
        if not song:
            logger.error("Failed to generate song with Suno API")
            assistant_msg_id = telegram_bot.send_message_chunks(chat_id, config.fallback_answer)
            db.save_message(session_uuid, user_uuid, "assistant", "ошибка генерации песни", llm.embd_text("ошибка генерации песни"), assistant_msg_id)
            return {"statusCode": 200, "body": ""}
        task_id = song["data"]["taskId"]

        telegram_bot.send_message_chunks(chat_id, config.song_generating_message)
        db.save_song(user_uuid, session_uuid, task_id, title, lyrics, style)

        db.save_message(session_uuid, user_uuid, "assistant", "финальная версия песни отправлена пользователю", llm.embd_text("финальная версия песни отправлена пользователю"), tg_msg_id)
        logger.debug("Suno task ID: %s", task_id)
        return {"statusCode": 200, "body": ""}

    if is_intent_feedback:
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