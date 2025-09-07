"""
Pytest tests for MindScribe functionality
"""

import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add parent directory to path for importing the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fixtures are now imported from conftest.py

class TestProcessingState:
    """Tests for processing state management"""
    
    def test_get_processing_state_exists(self, mock_db_functions):
        from index import get_processing_state
        
        mock_db_functions['query_one'].return_value = {
            'session_id': 'test-session',
            'summary_type': 'L1',
            'role': 'user',
            'last_message_count': 15,
            'processing_status': 'completed'
        }
        
        result = get_processing_state('test-session', 'L1', 'user')
        
        assert result is not None
        assert result['last_message_count'] == 15
        assert result['processing_status'] == 'completed'
        
    def test_get_processing_state_not_exists(self, mock_db_functions):
        from index import get_processing_state
        
        mock_db_functions['query_one'].return_value = None
        
        result = get_processing_state('test-session', 'L1', 'user')
        
        assert result is None
        
    def test_needs_processing_no_state(self, mock_db_functions):
        from index import needs_processing
        
        mock_db_functions['query_one'].return_value = None
        
        result = needs_processing('test-session', 'L1', 'user', 20)
        
        assert result is True
        
    def test_needs_processing_l1_enough_messages(self, mock_db_functions):
        from index import needs_processing
        
        mock_db_functions['query_one'].return_value = {
            'last_message_count': 15
        }
        
        result = needs_processing('test-session', 'L1', 'user', 35)  # 35 >= 15 + 15
        
        assert result is True
        
    def test_needs_processing_l1_not_enough_messages(self, mock_db_functions):
        from index import needs_processing
        
        mock_db_functions['query_one'].return_value = {
            'last_message_count': 15
        }
        
        result = needs_processing('test-session', 'L1', 'user', 25)  # 25 < 15 + 15
        
        assert result is False

class TestSummaryFunctions:
    """Tests for summary creation and retrieval"""
    
    def test_create_summary(self, mock_db_functions):
        from index import create_summary
        
        create_summary('test-session', 'test-user', 'user', 'test content', 'L1')
        
        mock_db_functions['execute'].assert_called_once()
        call_args = mock_db_functions['execute'].call_args[0]
        assert 'INSERT INTO summary' in call_args[0]
        # New parameter order: (id, session_id, user_id, role, created_at, type, summary_text, key_points, main_themes, insights, language)
        assert call_args[1][1] == 'test-session'  # session_id
        assert call_args[1][2] == 'test-user'     # user_id
        assert call_args[1][3] == 'user'          # role
        assert call_args[1][5] == 'L1'            # type (summary_type)
        
    def test_create_enhanced_summary(self, mock_db_functions):
        from index import create_enhanced_summary
        
        create_enhanced_summary(
            'test-session', 'test-user', 'user', 'test content', 
            'L1', 'L1_user_0', 'message_1_15', 15
        )
        
        mock_db_functions['execute'].assert_called_once()
        call_args = mock_db_functions['execute'].call_args[0]
        assert 'group_id, source_range, message_count' in call_args[0]
        
    def test_get_summaries_by_role(self, mock_db_functions):
        from index import get_summaries_by_role
        
        mock_db_functions['query_all'].return_value = [
            {'id': '1', 'summary_text': 'test', 'key_points': '[]', 'main_themes': '[]', 'insights': '[]', 'language': 'ru', 'type': 'L1'},
            {'id': '2', 'summary_text': 'test2', 'key_points': '[]', 'main_themes': '[]', 'insights': '[]', 'language': 'ru', 'type': 'L1'}
        ]
        
        result = get_summaries_by_role('test-session', 'L1', 'user')
        
        assert len(result) == 2
        mock_db_functions['query_all'].assert_called_once()

class TestLLMIntegration:
    """Tests for LLM integration"""
    
    @patch('index.session.post')
    def test_llm_conversation_success(self, mock_post, mock_llm_response):
        from index import llm_conversation
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps(mock_llm_response)}}]
        }
        mock_post.return_value = mock_response
        
        result = llm_conversation([{"role": "user", "content": "test"}], "system prompt")
        
        assert result == mock_llm_response
        mock_post.assert_called_once()
        
    @patch('index.session.post')
    def test_llm_conversation_error(self, mock_post):
        from index import llm_conversation
        
        mock_post.side_effect = Exception("API Error")
        
        result = llm_conversation([{"role": "user", "content": "test"}], "system prompt")
        
        assert "error" in result
        assert result["error"] == "API Error"
        
    @patch('index.llm_conversation')
    def test_llm_summarize_success(self, mock_llm_conv, mock_llm_response, sample_messages):
        from index import llm_summarize
        
        mock_llm_conv.return_value = mock_llm_response
        
        result = llm_summarize(sample_messages[:5])
        
        assert result == mock_llm_response
        mock_llm_conv.assert_called_once()
        
    @patch('index.llm_conversation')
    def test_llm_summarize_error(self, mock_llm_conv, sample_messages):
        from index import llm_summarize
        
        mock_llm_conv.return_value = {"error": "API Error"}
        
        result = llm_summarize(sample_messages[:5])
        
        assert result["summary"] == "Ошибка при создании саммари"
        assert result["language"] == "ru"

class TestProcessingLogic:
    """Tests for main processing logic"""
    
    @patch('index.llm_summarize')
    @patch('index.create_enhanced_summary')
    @patch('index.update_processing_state')
    @patch('index.needs_processing')
    def test_process_level_summaries_l1(self, mock_needs, mock_update, mock_create, mock_llm, 
                                       sample_messages, mock_llm_response):
        from index import process_level_summaries
        
        mock_needs.return_value = True
        mock_llm.return_value = mock_llm_response
        
        # Test L1 processing
        user_messages = [m for m in sample_messages if m['role'] == 'user']
        
        process_level_summaries('test-session', 'test-user', user_messages, 'user', 'L1', 15)
        
        # Should create summary for first group (10 messages >= 5 minimum)
        mock_create.assert_called()
        mock_update.assert_called_with('test-session', 'L1', 'user', len(user_messages))
        
    @patch('index.get_summaries_by_role')
    @patch('index.llm_summarize')
    @patch('index.create_enhanced_summary')
    @patch('index.needs_processing')
    def test_process_level_summaries_l2(self, mock_needs, mock_create, mock_llm, 
                                       mock_get_summaries, mock_llm_response):
        from index import process_level_summaries
        
        mock_needs.return_value = True
        mock_llm.return_value = mock_llm_response
        mock_get_summaries.return_value = [
            {'summary_text': 'test summary 1', 'key_points': '[]', 'main_themes': '[]', 'insights': '[]', 'language': 'ru', 'message_count': 15},
            {'summary_text': 'test summary 2', 'key_points': '[]', 'main_themes': '[]', 'insights': '[]', 'language': 'ru', 'message_count': 15},
            {'summary_text': 'test summary 3', 'key_points': '[]', 'main_themes': '[]', 'insights': '[]', 'language': 'ru', 'message_count': 10},
        ]
        
        # Test L2 processing (higher level)
        process_level_summaries('test-session', 'test-user', None, 'user', 'L2', 4, 'L1')
        
        mock_get_summaries.assert_called_with('test-session', 'L1', 'user')
        mock_create.assert_called()

class TestHandler:
    """Tests for main handler function"""
    
    @patch('index.get_sessions_to_process')
    @patch('index.process_session_summary')
    def test_handler_cron_trigger(self, mock_process, mock_get_sessions, mock_db_functions):
        from index import handler
        
        mock_get_sessions.return_value = [
            {'session_id': 'session1', 'user_id': 'user1'},
            {'session_id': 'session2', 'user_id': 'user2'},
        ]
        
        # Test cron trigger (empty body)
        event = {}
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        assert 'Processed 2 sessions' in result['body']
        assert mock_process.call_count == 2
        
    @patch('index.process_session_summary')
    def test_handler_direct_request(self, mock_process):
        from index import handler
        
        # Test direct session processing
        event = {
            'body': {
                'session_id': 'test-session',
                'user_id': 'test-user'
            }
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        mock_process.assert_called_once_with('test-session', 'test-user')
        
    def test_handler_invalid_request(self):
        from index import handler
        
        # Test invalid request
        event = {
            'body': {
                'invalid': 'data'
            }
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 400
        assert 'Invalid request' in result['body']

# Integration tests
class TestIntegration:
    """Integration tests that test multiple components together"""
    
    @patch('index.llm_conversation')
    @patch('index.get_conn')
    @patch('index.get_processing_state')
    @patch('index.execute')
    def test_full_processing_flow(self, mock_execute, mock_get_processing_state, 
                                  mock_get_conn, mock_llm_conv, 
                                  sample_messages, mock_llm_response):
        """Test the full processing flow with mocked external dependencies"""
        from index import process_messages_for_summary
        
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock processing state - return None to force processing
        mock_get_processing_state.return_value = None
        
        # Mock database execute function
        mock_execute.return_value = None
        
        # Mock LLM responses
        mock_llm_conv.return_value = mock_llm_response
        
        # Test processing
        process_messages_for_summary('test-session', 'test-user', sample_messages)
        
        # Verify LLM was called (should be called for both user and assistant summaries)
        assert mock_llm_conv.call_count > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
