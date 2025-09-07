#!/usr/bin/env python3
"""
Test script for LangGraph workflow refactoring.

This script validates that the LangGraph workflow can be imported and initialized
correctly without running the full application.
"""

import sys
import os
import logging
from typing import Dict, Any

# Add the flow directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """Test that all LangGraph modules can be imported successfully."""
    print("Testing imports...")

    try:
        from mindset.langgraph_state import ConversationState, NodeResult
        print("✓ LangGraph state imports successful")

        from mindset.langgraph_nodes import (
            BaseNode, IntentDetectionNode, EmotionAnalysisNode,
            MessageSaveNode, ConfusionHandlerNode, SongGenerationNode,
            FeedbackHandlerNode, ConversationNode
        )
        print("✓ LangGraph nodes imports successful")

        from mindset.langgraph_workflow import ConversationWorkflow
        print("✓ LangGraph workflow imports successful")

        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_state_structure():
    """Test that the ConversationState TypedDict works correctly."""
    print("Testing state structure...")

    try:
        from mindset.langgraph_state import ConversationState

        # Create a sample state
        sample_state: ConversationState = {
            "chat_id": "123456",
            "user_message": "Hello",
            "tg_msg_id": 1,
            "tg_user_id": "user123",
            "user_uuid": "uuid-123",
            "session_uuid": "session-123",
            "full_name": "Test User",
            "history": [],
            "last_8_messages": [],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [],
            "openai_msgs": [],
            "intent_analysis": None,
            "emotion_analysis": None,
            "msg_id": None,
            "is_final_song_received": False,
            "is_final_song_sent": False,
            "is_confused": False,
            "confusion_handled": False,
            "song_generation_triggered": False,
            "feedback_handled": False,
            "ai_response": None,
            "song_data": None,
            "errors": [],
            "steps_completed": []
        }

        print(f"✓ State structure is valid: {len(sample_state)} fields")
        return True
    except Exception as e:
        print(f"✗ State structure test failed: {e}")
        return False

def test_workflow_routing_functions():
    """Test the workflow routing functions."""
    print("Testing workflow routing functions...")

    try:
        from mindset.langgraph_workflow import (
            should_handle_confusion, should_generate_song,
            should_handle_feedback, route_after_analysis
        )
        from mindset.langgraph_state import ConversationState

        # Test confusion routing
        confused_state: ConversationState = {
            "is_confused": True,
            "last_20_assistant_messages": []
        }

        result = should_handle_confusion(confused_state)
        assert result == "confusion", f"Expected 'confusion', got '{result}'"

        # Test song generation routing
        song_state: ConversationState = {
            "intent_analysis": {"intent": "finalize_song"},
            "is_final_song_received": False,
            "is_final_song_sent": False
        }

        result = should_generate_song(song_state)
        assert result == "song_generation", f"Expected 'song_generation', got '{result}'"

        # Test feedback routing
        feedback_state: ConversationState = {
            "intent_analysis": {"intent": "feedback"},
            "is_final_song_received": True,
            "last_5_assistant_messages": []
        }

        result = should_handle_feedback(feedback_state)
        assert result == "feedback", f"Expected 'feedback', got '{result}'"

        print("✓ Workflow routing functions work correctly")
        return True
    except Exception as e:
        print(f"✗ Workflow routing test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Starting LangGraph workflow tests...")
    print("=" * 50)

    tests = [
        test_imports,
        test_state_structure,
        test_workflow_routing_functions
    ]

    passed = 0
    failed = 0

    for test in tests:
        print()
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1

    print()
    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! LangGraph refactoring is successful.")
        return 0
    else:
        print("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
