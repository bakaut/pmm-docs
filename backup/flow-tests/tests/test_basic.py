"""
Basic tests to verify the test setup works correctly.
"""

import pytest
from tests.test_config import TestConfig


def test_test_config_creation():
    """Test that TestConfig class can be instantiated and has expected attributes."""
    # Test that we can access class attributes
    assert TestConfig.TEST_USER_ID == 987654321
    assert TestConfig.TEST_CHAT_ID == 123456789
    assert isinstance(TestConfig.GENERAL_MESSAGES, list)
    assert len(TestConfig.GENERAL_MESSAGES) > 0


def test_telegram_message_event_creation():
    """Test creation of Telegram message events."""
    event = TestConfig.create_telegram_message_event("Hello!")
    
    # Verify structure
    assert "message" in event
    assert event["message"]["text"] == "Hello!"
    assert event["message"]["from"]["id"] == TestConfig.TEST_USER_ID
    assert event["message"]["chat"]["id"] == TestConfig.TEST_CHAT_ID


def test_callback_query_event_creation():
    """Test creation of callback query events."""
    event = TestConfig.create_callback_query_event("hug_author")
    
    # Verify structure
    assert "callback_query" in event
    assert event["callback_query"]["data"] == "hug_author"
    assert event["callback_query"]["from"]["id"] == TestConfig.TEST_USER_ID


def test_suno_callback_event_creation():
    """Test creation of Suno callback events."""
    event = TestConfig.create_suno_callback_event()
    
    # Verify structure
    assert "data" in event
    assert event["data"]["callbackType"] == "complete"
    assert "songs" in event["data"]
    assert len(event["data"]["songs"]) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])