"""
End-to-end tests for the Telegram bot that simulate real user interactions.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
from typing import Dict, Any

# Import the handler function from index.py
from flow.index import handler


class TestTelegramE2E:
    """End-to-end tests for Telegram bot interactions."""
    
    def create_telegram_message_event(self, message_text: str, chat_id: int = 123456789, 
                                    user_id: int = 987654321, first_name: str = "Test", 
                                    last_name: str = "User") -> Dict[str, Any]:
        """Create a Telegram message event structure."""
        return {
            "message": {
                "message_id": 1,
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": chat_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1234567890,
                "text": message_text
            }
        }
    
    def create_callback_query_event(self, data: str, chat_id: int = 123456789, 
                                  user_id: int = 987654321, first_name: str = "Test", 
                                  last_name: str = "User") -> Dict[str, Any]:
        """Create a Telegram callback query event structure."""
        return {
            "callback_query": {
                "id": "callback_query_id_123",
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": "testuser",
                    "language_code": "en"
                },
                "message": {
                    "message_id": 2,
                    "from": {
                        "id": 9876543210,  # Bot ID
                        "is_bot": True,
                        "first_name": "PoyMoyMirBot",
                        "username": "PoyMoyMirBot"
                    },
                    "chat": {
                        "id": chat_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "username": "testuser",
                        "type": "private"
                    },
                    "date": 1234567891,
                    "text": "Test message"
                },
                "chat_instance": "-1234567890123456789",
                "data": data
            }
        }
    
    def create_suno_callback_event(self, task_id: str = "mock-task-123") -> Dict[str, Any]:
        """Create a Suno API callback event structure."""
        return {
            "data": {
                "callbackType": "complete",
                "taskId": task_id,
                "status": "complete",
                "songs": [
                    {
                        "id": "song-id-123",
                        "title": "Test Song",
                        "imageUrl": "https://example.com/image.jpg",
                        "audioUrl": "https://example.com/audio.mp3"
                    }
                ]
            }
        }
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_general_conversation(self, mock_utils, mock_suno, mock_moderation, 
                                mock_llm, mock_telegram, mock_db, mock_config, mock_logger):
        """Test a general conversation flow."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        
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
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation.return_value = {"intent": "conversation"}
        mock_llm_instance.llm_call.return_value = "Hello! How can I help you today?"
        mock_llm_instance.embd_text.return_value = [0.1] * 10
        mock_llm.return_value = mock_llm_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_suno_instance = MagicMock()
        mock_suno.return_value = mock_suno_instance
        
        mock_utils_instance = MagicMock()
        mock_utils_instance.parse_body.return_value = {
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
                "text": "Hello!"
            }
        }
        mock_utils_instance.compute_message_context.return_value = {
            "last_8_messages": [],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [],
            "openai_msgs": [{"role": "user", "content": "Hello!"}]
        }
        mock_utils.return_value = mock_utils_instance
        
        # Create event
        event = self.create_telegram_message_event("Hello!")
        
        # Call handler
        result = handler(event, {})
        
        # Assertions
        assert result["statusCode"] == 200
        mock_telegram_instance.send_message_chunks.assert_called()
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_song_generation_flow(self, mock_utils, mock_suno, mock_moderation, 
                                mock_llm, mock_telegram, mock_db, mock_config):
        """Test the song generation flow."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        mock_config.song_generating_message = "🎵 Creating your song..."
        mock_config.system_prompt_prepare_suno = "Extract song data"
        
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
        mock_telegram.return_value = mock_telegram_instance
        
        # Mock LLM to return song generation intent
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation.side_effect = [
            {"intent": "finalize_song"},  # intent detection
            {"emotions": [{"name": "Радость", "intensity": 70}]},  # emotion detection
            {"state": "creative"},  # state detection
            {"state": "creative"},  # state detection v2
            {"state": "creative"},  # state detection v3
            {  # song preparation
                "lyrics": "Test lyrics about life and dreams",
                "style": "indie folk",
                "name": "Test Song"
            }
        ]
        mock_llm_instance.llm_call.return_value = "I'll create a song for you!"
        mock_llm_instance.embd_text.return_value = [0.1] * 10
        mock_llm.return_value = mock_llm_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_suno_instance = MagicMock()
        mock_suno_instance.request_suno.return_value = {
            "data": {
                "taskId": "mock-task-123"
            }
        }
        mock_suno.return_value = mock_suno_instance
        
        mock_utils_instance = MagicMock()
        mock_utils_instance.parse_body.return_value = {
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
                "text": "Please create a song for me"
            }
        }
        mock_utils_instance.compute_message_context.return_value = {
            "last_8_messages": [],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [],
            "openai_msgs": [{"role": "user", "content": "Please create a song for me"}]
        }
        mock_utils.return_value = mock_utils_instance
        
        # Create event
        event = self.create_telegram_message_event("Please create a song for me")
        
        # Call handler
        result = handler(event, {})
        
        # Assertions
        assert result["statusCode"] == 200
        mock_suno_instance.request_suno.assert_called()
        mock_telegram_instance.send_message_chunks.assert_called()
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_confusion_handling(self, mock_utils, mock_suno, mock_moderation, 
                              mock_llm, mock_telegram, mock_db, mock_config):
        """Test confusion detection and handling."""
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
        
        # Mock LLM to return confusion emotion
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation.side_effect = [
            {"intent": "conversation"},  # intent detection
            {"emotions": [{"name": "Растерянность", "intensity": 95}]},  # emotion detection (confused)
            {"state": "confused"},  # state detection
            {"state": "confused"},  # state detection v2
            {"state": "confused"}   # state detection v3
        ]
        mock_llm_instance.llm_call.return_value = "I'm here to help!"
        mock_llm_instance.embd_text.return_value = [0.1] * 10
        mock_llm.return_value = mock_llm_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_suno_instance = MagicMock()
        mock_suno.return_value = mock_suno_instance
        
        mock_utils_instance = MagicMock()
        mock_utils_instance.parse_body.return_value = {
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
                "text": "I'm confused, can you help me?"
            }
        }
        mock_utils_instance.compute_message_context.return_value = {
            "last_8_messages": [],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [],
            "openai_msgs": [{"role": "user", "content": "I'm confused, can you help me?"}]
        }
        mock_utils.return_value = mock_utils_instance
        
        # Create event
        event = self.create_telegram_message_event("I'm confused, can you help me?")
        
        # Call handler
        result = handler(event, {})
        
        # Assertions
        assert result["statusCode"] == 200
        # Either text or audio should be sent
        assert (mock_telegram_instance.send_message_chunks.called or 
                mock_telegram_instance.send_audio.called)
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_callback_query_handling(self, mock_utils, mock_suno, mock_moderation, 
                                   mock_llm, mock_telegram, mock_db, mock_config):
        """Test callback query handling."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        mock_config.want_silence_message = "You chose silence..."
        
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
        mock_telegram_instance.handle_callback_query.return_value = {"statusCode": 200, "body": ""}
        mock_telegram.return_value = mock_telegram_instance
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.llm_conversation.return_value = {"intent": "conversation"}
        mock_llm_instance.llm_call.return_value = "Hello!"
        mock_llm_instance.embd_text.return_value = [0.1] * 10
        mock_llm.return_value = mock_llm_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation_instance.is_user_blocked.return_value = False
        mock_moderation.return_value = mock_moderation_instance
        
        mock_suno_instance = MagicMock()
        mock_suno.return_value = mock_suno_instance
        
        mock_utils_instance = MagicMock()
        mock_utils_instance.parse_body.return_value = {
            "callback_query": {
                "id": "callback_query_id_123",
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User"
                },
                "data": "silence_room"
            }
        }
        mock_utils.return_value = mock_utils_instance
        
        # Create callback event
        event = self.create_callback_query_event("silence_room")
        
        # Call handler
        result = handler(event, {})
        
        # Assertions
        assert result["statusCode"] == 200
        mock_telegram_instance.handle_callback_query.assert_called()
    
    @patch('flow.index.Config')
    @patch('flow.index.create_database_manager')
    @patch('flow.index.TelegramBot')
    @patch('flow.index.LLMManager')
    @patch('flow.index.ModerationService')
    @patch('flow.index.SunoManager')
    @patch('flow.index.Utils')
    def test_suno_callback_handling(self, mock_utils, mock_suno, mock_moderation, 
                                  mock_llm, mock_telegram, mock_db, mock_config):
        """Test Suno API callback handling."""
        # Setup mocks
        mock_config.from_env.return_value = mock_config
        mock_config.bot_token = "test_token"
        mock_config.log_level = "DEBUG"
        mock_config.log_name = "test"
        mock_config.session_lifetime = 3600
        mock_config.database.type = "postgresql"
        
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
        mock_telegram.return_value = mock_telegram_instance
        
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        
        mock_moderation_instance = MagicMock()
        mock_moderation.return_value = mock_moderation_instance
        
        mock_suno_instance = MagicMock()
        mock_suno_instance.handle_suno_callback.return_value = {"statusCode": 200, "body": ""}
        mock_suno.return_value = mock_suno_instance
        
        mock_utils_instance = MagicMock()
        mock_utils_instance.parse_body.return_value = {
            "data": {
                "callbackType": "complete",
                "taskId": "mock-task-123"
            }
        }
        mock_utils.return_value = mock_utils_instance
        
        # Create Suno callback event
        event = self.create_suno_callback_event()
        
        # Call handler
        result = handler(event, {})
        
        # Assertions
        assert result["statusCode"] == 200
        mock_suno_instance.handle_suno_callback.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])