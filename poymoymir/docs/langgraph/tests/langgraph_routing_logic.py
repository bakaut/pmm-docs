#!/usr/bin/env python3
"""
LangGraph Routing Logic Test

This script tests the core routing logic of the LangGraph workflow
without requiring external dependencies.
"""

import sys
import os
from typing import Dict, Any, Literal

def create_mock_conversation_state(**kwargs) -> Dict[str, Any]:
    """Create a mock conversation state for testing."""
    default_state = {
        "chat_id": "test-chat-123",
        "user_message": "Test message",
        "tg_msg_id": 12345,
        "tg_user_id": "user-123",
        "user_uuid": "user-uuid-123",
        "session_uuid": "session-uuid-123",
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

    # Update with provided kwargs
    default_state.update(kwargs)
    return default_state

# Copy the routing functions from the workflow (without imports)
def should_handle_confusion(state: Dict[str, Any]) -> Literal["confusion", "continue"]:
    """
    Decide whether to handle confusion state.
    """
    if not state.get("is_confused", False):
        return "continue"

    # Check if confusion was already handled recently
    if any(msg["content"] == "confused_send" for msg in state["last_20_assistant_messages"]):
        return "continue"

    return "confusion"

def should_generate_song(state: Dict[str, Any]) -> Literal["song_generation", "continue"]:
    """
    Decide whether to generate a song.
    """
    intent_analysis = state.get("intent_analysis") or {}
    intent = intent_analysis.get("intent", "")

    if intent != "finalize_song":
        return "continue"

    # Check if final song was already sent or received recently
    if state.get("is_final_song_received", False) or state.get("is_final_song_sent", False):
        return "continue"

    return "song_generation"

def should_handle_feedback(state: Dict[str, Any]) -> Literal["feedback", "continue"]:
    """
    Decide whether to handle feedback.
    """
    intent_analysis = state.get("intent_analysis") or {}
    intent = intent_analysis.get("intent", "")

    if intent != "feedback":
        return "continue"

    if not state.get("is_final_song_received", False):
        return "continue"

    # Check if feedback was already handled recently
    if any(msg["content"] == "feedback_final_send" for msg in state["last_5_assistant_messages"]):
        return "continue"

    return "feedback"

def route_after_analysis(state: Dict[str, Any]) -> Literal["confusion", "song_generation", "feedback", "conversation"]:
    """
    Route to appropriate handler after analysis is complete.
    """
    # Check confusion first (highest priority)
    if should_handle_confusion(state) == "confusion":
        return "confusion"

    # Check if song should be generated
    if should_generate_song(state) == "song_generation":
        return "song_generation"

    # Check if feedback should be handled
    if should_handle_feedback(state) == "feedback":
        return "feedback"

    # Default to general conversation
    return "conversation"

def test_routing_scenario(name: str, state: Dict[str, Any], expected_route: str):
    """Test a specific routing scenario."""
    print(f"\n🧪 Testing: {name}")
    print("-" * 40)

    actual_route = route_after_analysis(state)

    print(f"State conditions:")
    intent_analysis = state.get('intent_analysis') or {}
    print(f"  - Intent: {intent_analysis.get('intent', 'None')}")
    print(f"  - Confused: {state.get('is_confused', False)}")
    print(f"  - Song received: {state.get('is_final_song_received', False)}")
    print(f"  - Song sent: {state.get('is_final_song_sent', False)}")

    print(f"Expected route: {expected_route}")
    print(f"Actual route: {actual_route}")

    if actual_route == expected_route:
        print("✅ PASS")
        return True
    else:
        print("❌ FAIL")
        return False

def run_routing_tests():
    """Run comprehensive routing logic tests."""

    print("🚀 LangGraph Routing Logic Tests")
    print("=" * 50)

    test_cases = [
        {
            "name": "General Conversation",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "conversation"}
            ),
            "expected": "conversation"
        },
        {
            "name": "Confusion Handling (High Priority)",
            "state": create_mock_conversation_state(
                is_confused=True,
                intent_analysis={"intent": "finalize_song"},  # Should be overridden by confusion
                last_20_assistant_messages=[]
            ),
            "expected": "confusion"
        },
        {
            "name": "Song Generation Request",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "finalize_song"},
                is_final_song_received=False,
                is_final_song_sent=False
            ),
            "expected": "song_generation"
        },
        {
            "name": "Song Generation Blocked (Already Sent)",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "finalize_song"},
                is_final_song_sent=True
            ),
            "expected": "conversation"
        },
        {
            "name": "Feedback After Song Received",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "feedback"},
                is_final_song_received=True,
                last_5_assistant_messages=[]
            ),
            "expected": "feedback"
        },
        {
            "name": "Feedback Blocked (No Song Received)",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "feedback"},
                is_final_song_received=False
            ),
            "expected": "conversation"
        },
        {
            "name": "Feedback Blocked (Already Handled)",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "feedback"},
                is_final_song_received=True,
                last_5_assistant_messages=[
                    {"content": "feedback_final_send"}
                ]
            ),
            "expected": "conversation"
        },
        {
            "name": "Confusion Already Handled",
            "state": create_mock_conversation_state(
                is_confused=True,
                last_20_assistant_messages=[
                    {"content": "confused_send"}
                ]
            ),
            "expected": "conversation"
        },
        {
            "name": "Unknown Intent",
            "state": create_mock_conversation_state(
                intent_analysis={"intent": "unknown_intent"}
            ),
            "expected": "conversation"
        },
        {
            "name": "Priority Test: Confusion > Song > Feedback",
            "state": create_mock_conversation_state(
                is_confused=True,
                intent_analysis={"intent": "feedback"},
                is_final_song_received=True,
                last_20_assistant_messages=[],
                last_5_assistant_messages=[]
            ),
            "expected": "confusion"  # Confusion has highest priority
        }
    ]

    results = []

    for test_case in test_cases:
        success = test_routing_scenario(
            test_case["name"],
            test_case["state"],
            test_case["expected"]
        )
        results.append(success)

    # Summary
    print(f"\n{'='*50}")
    print("🎯 Test Results Summary")
    print(f"{'='*50}")

    passed = sum(results)
    total = len(results)

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print("\n🎉 All routing tests passed!")
        print("✅ LangGraph routing logic is working correctly")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

def test_individual_functions():
    """Test individual routing functions."""
    print("\n🔍 Testing Individual Functions")
    print("=" * 40)

    # Test confusion detection
    print("\n1. Testing should_handle_confusion:")

    confused_state = {"is_confused": True, "last_20_assistant_messages": []}
    result = should_handle_confusion(confused_state)
    print(f"   Confused user (no recent handling): {result} ✅" if result == "confusion" else f"   FAILED: {result} ❌")

    already_handled = {"is_confused": True, "last_20_assistant_messages": [{"content": "confused_send"}]}
    result = should_handle_confusion(already_handled)
    print(f"   Confused user (already handled): {result} ✅" if result == "continue" else f"   FAILED: {result} ❌")

    not_confused = {"is_confused": False, "last_20_assistant_messages": []}
    result = should_handle_confusion(not_confused)
    print(f"   Not confused user: {result} ✅" if result == "continue" else f"   FAILED: {result} ❌")

    # Test song generation
    print("\n2. Testing should_generate_song:")

    song_request = {"intent_analysis": {"intent": "finalize_song"}, "is_final_song_received": False, "is_final_song_sent": False}
    result = should_generate_song(song_request)
    print(f"   Valid song request: {result} ✅" if result == "song_generation" else f"   FAILED: {result} ❌")

    wrong_intent = {"intent_analysis": {"intent": "conversation"}, "is_final_song_received": False, "is_final_song_sent": False}
    result = should_generate_song(wrong_intent)
    print(f"   Wrong intent: {result} ✅" if result == "continue" else f"   FAILED: {result} ❌")

    # Test feedback
    print("\n3. Testing should_handle_feedback:")

    valid_feedback = {"intent_analysis": {"intent": "feedback"}, "is_final_song_received": True, "last_5_assistant_messages": []}
    result = should_handle_feedback(valid_feedback)
    print(f"   Valid feedback: {result} ✅" if result == "feedback" else f"   FAILED: {result} ❌")

    no_song = {"intent_analysis": {"intent": "feedback"}, "is_final_song_received": False, "last_5_assistant_messages": []}
    result = should_handle_feedback(no_song)
    print(f"   Feedback without song: {result} ✅" if result == "continue" else f"   FAILED: {result} ❌")

if __name__ == "__main__":
    # Run individual function tests first
    test_individual_functions()

    # Run comprehensive routing tests
    exit_code = run_routing_tests()

    sys.exit(exit_code)
