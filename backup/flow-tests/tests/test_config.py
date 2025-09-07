"""
Test configuration for PoyMoyMir Telegram bot tests.
"""

from typing import Dict, Any
import json


class TestConfig:
    """Configuration class for tests."""
    
    # Test user data
    TEST_USER_ID = 987654321
    TEST_CHAT_ID = 123456789
    TEST_USER_FIRST_NAME = "Test"
    TEST_USER_LAST_NAME = "User"
    TEST_BOT_TOKEN = "test_token_1234567890"
    
    # Test messages
    GENERAL_MESSAGES = [
        "Hello!",
        "How are you today?",
        "What can you do?",
        "Tell me something interesting"
    ]
    
    SONG_REQUESTS = [
        "Please create a song for me",
        "Can you generate music?",
        "I want you to sing me something",
        "Make a song about love",
        "Create music that captures happiness"
    ]
    
    CONFUSION_MESSAGES = [
        "I'm confused",
        "I don't understand what's happening",
        "Can you help me? I'm lost",
        "What am I supposed to do?",
        "This is all so confusing"
    ]
    
    FEEDBACK_MESSAGES = [
        "I loved that song!",
        "That was amazing!",
        "Not my favorite, but it's okay",
        "I really enjoyed that",
        "That song was perfect!"
    ]
    
    # Test callback data
    CALLBACK_QUERIES = [
        "hug_author",
        "silence_room"
    ]
    
    # Expected responses
    EXPECTED_INTENTS = [
        "conversation",
        "finalize_song",
        "feedback"
    ]
    
    EXPECTED_EMOTIONS = [
        "Радость",
        "Растерянность",
        "Любовь",
        "Грусть"
    ]
    
    # Test song data
    TEST_SONG_DATA = {
        "lyrics": "Test lyrics for automated testing",
        "style": "test-style",
        "name": "Test Song"
    }
    
    TEST_SUNO_RESPONSE = {
        "data": {
            "taskId": "test-task-123"
        }
    }
    
    TEST_SUNO_CALLBACK = {
        "data": {
            "callbackType": "complete",
            "taskId": "test-task-123",
            "status": "complete",
            "songs": [
                {
                    "id": "test-song-123",
                    "title": "Test Song",
                    "imageUrl": "https://example.com/test-image.jpg",
                    "audioUrl": "https://example.com/test-audio.mp3"
                }
            ]
        }
    }
    
    @classmethod
    def create_telegram_message_event(cls, message_text: str, message_id: int = 1) -> Dict[str, Any]:
        """Create a Telegram message event structure."""
        return {
            "message": {
                "message_id": message_id,
                "from": {
                    "id": cls.TEST_USER_ID,
                    "is_bot": False,
                    "first_name": cls.TEST_USER_FIRST_NAME,
                    "last_name": cls.TEST_USER_LAST_NAME,
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": cls.TEST_CHAT_ID,
                    "first_name": cls.TEST_USER_FIRST_NAME,
                    "last_name": cls.TEST_USER_LAST_NAME,
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1234567890 + message_id,
                "text": message_text
            }
        }
    
    @classmethod
    def create_callback_query_event(cls, data: str) -> Dict[str, Any]:
        """Create a Telegram callback query event structure."""
        return {
            "callback_query": {
                "id": f"callback_query_id_{data}",
                "from": {
                    "id": cls.TEST_USER_ID,
                    "is_bot": False,
                    "first_name": cls.TEST_USER_FIRST_NAME,
                    "last_name": cls.TEST_USER_LAST_NAME,
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
                        "id": cls.TEST_CHAT_ID,
                        "first_name": cls.TEST_USER_FIRST_NAME,
                        "last_name": cls.TEST_USER_LAST_NAME,
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
    
    @classmethod
    def create_suno_callback_event(cls) -> Dict[str, Any]:
        """Create a Suno API callback event structure."""
        return cls.TEST_SUNO_CALLBACK