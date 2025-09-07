"""
User journey tests that simulate a complete interaction with the PoyMoyMir bot.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
from typing import List, Dict, Any

# Import the handler function from index.py
from flow.index import handler


class TestUserJourney:
    """Tests that simulate complete user journeys through the bot."""
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_complete_user_journey(self, mock_utils, mock_suno, mock_moderation, 
                                 mock_llm, mock_telegram, mock_db, mock_config):
        """Test a complete user journey from initial contact to song feedback."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        mock_config.song_generating_message = "🎵 Creating your song..."
        mock_config.song_received_message = "How did you like your song?"
        mock_config.system_prompt_prepare_suno = "Extract song data"
        mock_config.confused_intent_answers = ["I understand your confusion..."]
        mock_config.confused_intent_answer_mp3 = "https://example.com/audio.mp3"
        
        mock_db_instance = MagicMock()
        mock_db_instance.get_or_create_bot.return_value = "bot-id-123"
        mock_db_instance.get_or_create_user.return_value = "user-uuid-123"
        mock_db_instance.get_active_session.return_value = "session-uuid-123"
        mock_db_instance.ensure_user_exists.return_value = None
        mock_db_instance.save_message.return_value = "message-id-123"
        mock_db_instance.update_message_analysis.return_value = None
        mock_db_instance.fetch_history.return_value = []
        mock_db_instance.save_song.return_value = None
        mock_db_instance.is_user_blocked.return_value = False
        mock_db.return_value = mock_db_instance
        
        mock_telegram_instance = MagicMock()
        mock_telegram_instance.send_message_chunks.return_value = None
        mock_telegram_instance.send_audio.return_value = None
        mock_telegram.return_value = mock_telegram_instance
        
        mock_suno_instance = MagicMock()
        mock_suno_instance.request_suno.return_value = {
            "data": {
                "taskId": "mock-task-123"
            }
        }
        mock_suno_instance.handle_suno_callback.return_value = {"statusCode": 200, "body": ""}
        mock_suno.return_value = mock_suno_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_utils_instance = MagicMock()
        mock_utils.return_value = mock_utils_instance
        
        # Track conversation state
        conversation_history = []
        
        # Mock LLM responses based on conversation history
        def mock_llm_conversation(messages, system_prompt):
            # Store messages for context
            conversation_history.extend(messages)
            
            if "intent" in system_prompt.lower():
                # Determine intent based on last message
                last_message = messages[-1]["content"] if messages else ""
                if any(word in last_message.lower() for word in ["song", "create", "generate", "music", "sing"]):
                    return {"intent": "finalize_song"}
                elif any(word in last_message.lower() for word in ["feedback", "like", "love", "hate", "enjoy", "amazing", "wonderful"]):
                    return {"intent": "feedback"}
                elif any(word in last_message.lower() for word in ["confused", "lost", "don't understand", "help"]):
                    return {"intent": "conversation"}  # Confusion handled by emotion detection
                else:
                    return {"intent": "conversation"}
                    
            elif "emotion" in system_prompt.lower():
                # Check for confusion in last message
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
                
            elif "state" in system_prompt.lower():
                return {"state": "creative"}
                
            else:
                return {"result": "mock response"}
        
        def mock_llm_call(messages, chat_id, user_id, moderation_callback=None):
            last_message = messages[-1]["content"] if messages else ""
            return f"AI response to: {last_message}"
            
        def mock_embd_text(text):
            return [0.1 * i for i in range(10)]
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation = mock_llm_conversation
        mock_llm_instance.llm_call = mock_llm_call
        mock_llm_instance.embd_text = mock_embd_text
        mock_llm.return_value = mock_llm_instance
        
        def mock_parse_body(event):
            return event.get("body", event) if isinstance(event, dict) else {}
        
        def mock_compute_message_context(history, text):
            return {
                "last_8_messages": history[-8:] if len(history) >= 8 else history,
                "last_20_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-20:],
                "last_5_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-5:],
                "last_3_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-3:],
                "last_8_user_messages": [msg for msg in history if msg.get("role") == "user"][-8:],
                "openai_msgs": [{"role": msg.get("role", "user"), "content": msg["content"]} for msg in history]
            }
        
        mock_utils_instance.parse_body = mock_parse_body
        mock_utils_instance.compute_message_context = mock_compute_message_context
        
        # Simulate user journey:
        # 1. Initial greeting
        event1 = {
            "message": {
                "message_id": 1,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1234567890,
                "text": "Hello! What can you do?"
            }
        }
        
        result1 = handler(event1, {})
        assert result1["statusCode"] == 200
        
        # 2. User asks for a song
        event2 = {
            "message": {
                "message_id": 2,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1234567891,
                "text": "Can you create a song for me about dreams?"
            }
        }
        
        result2 = handler(event2, {})
        assert result2["statusCode"] == 200
        
        # Verify song generation was triggered
        mock_suno_instance.request_suno.assert_called()
        
        # 3. Suno callback (song completion)
        event3 = {
            "data": {
                "callbackType": "complete",
                "taskId": "mock-task-123",
                "status": "complete",
                "songs": [
                    {
                        "id": "song-id-123",
                        "title": "Dreams",
                        "imageUrl": "https://example.com/image.jpg",
                        "audioUrl": "https://example.com/audio.mp3"
                    }
                ]
            }
        }
        
        result3 = handler(event3, {})
        assert result3["statusCode"] == 200
        
        # 4. User provides feedback
        event4 = {
            "message": {
                "message_id": 3,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1234567892,
                "text": "I loved that song! It was amazing!"
            }
        }
        
        result4 = handler(event4, {})
        assert result4["statusCode"] == 200
        
        # Verify all expected interactions occurred
        assert mock_telegram_instance.send_message_chunks.call_count >= 3
        mock_suno_instance.request_suno.assert_called()
        mock_suno_instance.handle_suno_callback.assert_called()
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_confusion_intervention_journey(self, mock_utils, mock_suno, mock_moderation, 
                                          mock_llm, mock_telegram, mock_db, mock_config):
        """Test a user journey where the bot detects and intervenes in user confusion."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        mock_config.confused_intent_answers = ["I understand your confusion..."]
        mock_config.confused_intent_answer_mp3 = "https://example.com/audio.mp3"
        
        mock_db_instance = MagicMock()
        mock_db_instance.get_or_create_bot.return_value = "bot-id-123"
        mock_db_instance.get_or_create_user.return_value = "user-uuid-123"
        mock_db_instance.get_active_session.return_value = "session-uuid-123"
        mock_db_instance.ensure_user_exists.return_value = None
        mock_db_instance.save_message.return_value = "message-id-123"
        mock_db_instance.update_message_analysis.return_value = None
        mock_db_instance.fetch_history.return_value = []
        mock_db_instance.is_user_blocked.return_value = False
        mock_db.return_value = mock_db_instance
        
        mock_telegram_instance = MagicMock()
        mock_telegram_instance.send_message_chunks.return_value = None
        mock_telegram_instance.send_audio.return_value = None
        mock_telegram.return_value = mock_telegram_instance
        
        mock_suno_instance = MagicMock()
        mock_suno.return_value = mock_suno_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_utils_instance = MagicMock()
        mock_utils.return_value = mock_utils_instance
        
        # Mock LLM to detect confusion
        def mock_llm_conversation(messages, system_prompt):
            if "intent" in system_prompt.lower():
                return {"intent": "conversation"}
            elif "emotion" in system_prompt.lower():
                # Always return confusion for this test
                return {
                    "emotions": [
                        {"name": "Растерянность", "intensity": 95, "category": "negative"}
                    ]
                }
            elif "state" in system_prompt.lower():
                return {"state": "confused"}
            else:
                return {"result": "mock response"}
        
        def mock_llm_call(messages, chat_id, user_id, moderation_callback=None):
            last_message = messages[-1]["content"] if messages else ""
            return f"AI response to: {last_message}"
            
        def mock_embd_text(text):
            return [0.1 * i for i in range(10)]
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation = mock_llm_conversation
        mock_llm_instance.llm_call = mock_llm_call
        mock_llm_instance.embd_text = mock_embd_text
        mock_llm.return_value = mock_llm_instance
        
        def mock_parse_body(event):
            return event.get("body", event) if isinstance(event, dict) else {}
        
        def mock_compute_message_context(history, text):
            return {
                "last_8_messages": history[-8:] if len(history) >= 8 else history,
                "last_20_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-20:],
                "last_5_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-5:],
                "last_3_assistant_messages": [msg for msg in history if msg.get("role") == "assistant"][-3:],
                "last_8_user_messages": [msg for msg in history if msg.get("role") == "user"][-8:],
                "openai_msgs": [{"role": msg.get("role", "user"), "content": msg["content"]} for msg in history]
            }
        
        mock_utils_instance.parse_body = mock_parse_body
        mock_utils_instance.compute_message_context = mock_compute_message_context
        
        # Simulate confused user message
        event = {
            "message": {
                "message_id": 1,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Confused",
                    "last_name": "User"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Confused",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1234567890,
                "text": "I'm so confused about what's happening. Can you help me?"
            }
        }
        
        result = handler(event, {})
        assert result["statusCode"] == 200
        
        # Verify that either text or audio response was sent (confusion handling)
        assert (mock_telegram_instance.send_message_chunks.called or 
                mock_telegram_instance.send_audio.called)