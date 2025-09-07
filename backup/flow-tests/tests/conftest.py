"""
pytest configuration and fixtures for poymoymir tests.
"""

import sys
import os
from pathlib import Path

# Add the flow directory to the path so we can import modules
FLOW_DIR = Path(__file__).parent.parent / "flow"
sys.path.insert(0, str(FLOW_DIR))

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    
    # Bot configuration
    config.bot_token = "test_token_1234567890"
    config.log_level = "DEBUG"
    config.log_name = "test_bot"
    config.session_lifetime = 3600
    
    # AI configuration
    config.ai_model = "test-model"
    config.system_prompt_intent = "Analyze intent and return JSON with intent field"
    config.system_prompt_detect_emotion = "Analyze emotions and return JSON with emotions array"
    config.system_prompt_detect_state = "Analyze state and return JSON"
    config.system_prompt_detect_state_v2 = "Analyze state v2 and return JSON"
    config.system_prompt_detect_state_v3 = "Analyze state v3 and return JSON"
    config.system_prompt_prepare_suno = "Extract song data and return JSON"
    
    # Response configuration
    config.confused_intent_answers = ["I understand your confusion..."]
    config.confused_intent_answer_mp3 = "https://example.com/audio.mp3"
    config.song_generating_message = "🎵 Creating your song..."
    config.song_received_message = "How did you like your song?"
    config.song_received_markup = None
    config.fallback_answer = "I apologize for the issue."
    config.want_silence_message = "You chose silence..."
    
    # Network configuration
    config.connect_timeout = 10
    config.read_timeout = 30
    
    # Database configuration
    config.database = Mock()
    config.database.type = "postgresql"
    
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def mock_database():
    """Create a mock database manager."""
    db = Mock()
    
    # Mock database methods
    db.get_or_create_bot.return_value = "test-bot-id"
    db.get_or_create_user.return_value = "test-user-uuid"
    db.get_active_session.return_value = "test-session-uuid"
    db.ensure_user_exists.return_value = None
    db.save_message.return_value = "test-message-id"
    db.update_message_analysis.return_value = None
    db.save_song.return_value = None
    db.fetch_history.return_value = []
    db.is_user_blocked.return_value = False
    
    return db


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    llm = Mock()
    
    # Mock LLM methods
    def mock_llm_conversation(messages, system_prompt):
        # Return different responses based on the system prompt
        if "intent" in system_prompt.lower():
            # Check for song-related keywords
            last_message = messages[-1]["content"] if messages else ""
            if any(word in last_message.lower() for word in ["song", "create", "generate", "music", "sing"]):
                return {"intent": "finalize_song"}
            elif any(word in last_message.lower() for word in ["feedback", "like", "love", "hate", "enjoy"]):
                return {"intent": "feedback"}
            else:
                return {"intent": "conversation"}
                
        elif "emotion" in system_prompt.lower():
            # Check for confusion keywords
            last_message = messages[-1]["content"] if messages else ""
            if any(word in last_message.lower() for word in ["confused", "lost", "don't understand", "help"]):
                return {
                    "emotions": [
                        {"name": "Растерянность", "intensity": 95, "category": "negative"}
                    ]
                }
            else:
                return {
                    "emotions": [
                        {"name": "Радость", "intensity": 70, "category": "positive"}
                    ]
                }
                
        elif "suno" in system_prompt.lower():
            return {
                "lyrics": "Test lyrics about life and dreams",
                "style": "indie folk",
                "name": "Test Song"
            }
            
        else:
            return {"result": "mock response"}
    
    def mock_llm_call(messages, chat_id, user_id, moderation_callback=None):
        last_message = messages[-1]["content"] if messages else ""
        return f"AI response to: {last_message}"
        
    def mock_embd_text(text):
        # Return a simple mock embedding
        return [0.1 * i for i in range(10)]
    
    llm.llm_conversation = mock_llm_conversation
    llm.llm_call = mock_llm_call
    llm.embd_text = mock_embd_text
    
    return llm


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.send_message_chunks.return_value = None
    bot.send_audio.return_value = None
    bot.handle_callback_query.return_value = {"statusCode": 200, "body": ""}
    return bot


@pytest.fixture
def mock_suno_manager():
    """Create a mock Suno manager."""
    suno = Mock()
    suno.request_suno.return_value = {
        "data": {
            "taskId": "mock-task-123"
        }
    }
    suno.handle_suno_callback.return_value = {"statusCode": 200, "body": ""}
    return suno


@pytest.fixture
def mock_moderation_service():
    """Create a mock moderation service."""
    moderation = Mock()
    moderation.is_user_blocked.return_value = False
    moderation.moderate_user.return_value = None
    return moderation


@pytest.fixture
def mock_utils():
    """Create a mock utils manager."""
    utils = Mock()
    
    # Mock compute_message_context to return realistic data
    def mock_compute_message_context(history, text):
        return {
            "last_8_messages": history[-8:] if len(history) >= 8 else history,
            "last_20_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-20:],
            "last_5_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-5:],
            "last_3_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-3:],
            "last_8_user_messages": [msg for msg in history if msg.get("role") == "user"][-8:],
            "openai_msgs": [{"role": msg.get("role", "user"), "content": msg["content"]} for msg in history]
        }
    
    utils.compute_message_context = mock_compute_message_context
    utils.parse_body = lambda event: event.get("body", {}) if isinstance(event, dict) else {}
    
    return utils