"""
Pytest configuration and shared fixtures for MindScribe tests
"""

import pytest
import os
import sys
from unittest.mock import patch
from datetime import datetime, timezone

# Add parent directory to path for importing the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_env():
    """Mock environment variables for all tests"""
    with patch.dict(os.environ, {
        'operouter_key': 'test-key',
        'ai_model': 'openai/gpt-4o-mini',
        'database_url_dev': 'postgresql://test:test@localhost:5432/test',
        'env': 'dev'
    }):
        yield


@pytest.fixture
def mock_db_functions():
    """Mock database functions"""
    with patch('index.query_one') as mock_query_one, \
         patch('index.query_all') as mock_query_all, \
         patch('index.execute') as mock_execute:
        yield {
            'query_one': mock_query_one,
            'query_all': mock_query_all,
            'execute': mock_execute
        }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response structure"""
    return {
        "summary": "Test summary of the conversation",
        "key_points": ["Point 1", "Point 2", "Point 3"],
        "main_themes": ["Theme 1", "Theme 2"],
        "insights": ["Insight 1", "Insight 2"],
        "language": "ru"
    }


@pytest.fixture
def sample_messages():
    """Sample messages for testing"""
    return [
        {"role": "user", "content": "Привет, как дела?", "created_at": datetime.now(timezone.utc)},
        {"role": "assistant", "content": "Привет! Всё хорошо, спасибо!", "created_at": datetime.now(timezone.utc)},
        {"role": "user", "content": "Расскажи мне что-нибудь интересное", "created_at": datetime.now(timezone.utc)},
        {"role": "assistant", "content": "Конечно! Вот интересный факт...", "created_at": datetime.now(timezone.utc)},
    ] * 5  # 20 messages total


@pytest.fixture
def sample_session_data():
    """Sample session data for testing"""
    return {
        'session_id': 'test-session-123',
        'user_id': 'test-user-456',
        'bot_id': 'test-bot-789',
        'started_at': datetime.now(timezone.utc),
        'model': 'openai/gpt-4o-mini'
    }


@pytest.fixture
def sample_summary_data():
    """Sample summary data for testing"""
    return {
        'id': 'summary-123',
        'session_id': 'test-session-123',
        'user_id': 'test-user-456',
        'role': 'user',
        'type': 'L1',
        'content': '{"summary": "Test summary", "key_points": ["Point 1"], "language": "ru"}',
        'group_id': 'L1_user_0',
        'source_range': 'message_1_15',
        'message_count': 15,
        'created_at': datetime.now(timezone.utc)
    }
