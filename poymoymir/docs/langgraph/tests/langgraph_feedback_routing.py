#!/usr/bin/env python3
"""
Feedback Routing Test

This script specifically tests the feedback routing logic to ensure
it works correctly in different scenarios.
"""

from typing import Dict, Any
import sys

def simulate_feedback_intent_detection(user_message: str) -> str:
    """More accurate feedback intent detection."""
    message_lower = user_message.lower()

    # Specific feedback keywords
    feedback_words = ["loved", "liked", "hated", "beautiful", "amazing", "terrible", "awful", "great", "good", "bad"]
    opinion_words = ["think", "feel", "opinion", "feedback", "review"]

    if any(word in message_lower for word in feedback_words + opinion_words):
        return "feedback"
    elif any(word in message_lower for word in ["song", "create", "generate", "music", "compose"]):
        return "finalize_song"
    else:
        return "conversation"

def test_feedback_scenarios():
    """Test specific feedback routing scenarios."""

    print("🎯 Testing Feedback Routing Logic")
    print("=" * 50)

    test_cases = [
        {
            "name": "Positive Feedback After Song",
            "message": "I loved that song! It was beautiful!",
            "context": {"is_final_song_received": True, "last_5_assistant_messages": []},
            "expected": "feedback"
        },
        {
            "name": "Negative Feedback After Song",
            "message": "I didn't like that song, it was awful",
            "context": {"is_final_song_received": True, "last_5_assistant_messages": []},
            "expected": "feedback"
        },
        {
            "name": "Opinion Request After Song",
            "message": "What do you think about the song?",
            "context": {"is_final_song_received": True, "last_5_assistant_messages": []},
            "expected": "feedback"
        },
        {
            "name": "Feedback Without Song Received",
            "message": "I loved that song!",
            "context": {"is_final_song_received": False, "last_5_assistant_messages": []},
            "expected": "conversation"
        },
        {
            "name": "Feedback Already Handled",
            "message": "I loved that song!",
            "context": {
                "is_final_song_received": True,
                "last_5_assistant_messages": [{"content": "feedback_final_send"}]
            },
            "expected": "conversation"
        },
        {
            "name": "Mixed Message - Song Request vs Feedback",
            "message": "I loved that song! Can you create another one?",
            "context": {"is_final_song_received": True, "last_5_assistant_messages": []},
            "expected": "feedback"  # Feedback should take priority when song is received
        }
    ]

    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        print("-" * 40)

        # Simulate intent detection
        detected_intent = simulate_feedback_intent_detection(test_case['message'])
        print(f"Detected Intent: {detected_intent}")

        # Create state
        state = {
            "intent_analysis": {"intent": detected_intent},
            "is_final_song_received": test_case['context']['is_final_song_received'],
            "last_5_assistant_messages": test_case['context']['last_5_assistant_messages']
        }

        # Apply routing logic
        intent_analysis = state.get("intent_analysis") or {}
        intent = intent_analysis.get("intent", "")

        if intent == "feedback":
            if state.get("is_final_song_received", False):
                if not any(msg.get("content") == "feedback_final_send" for msg in state.get("last_5_assistant_messages", [])):
                    actual_route = "feedback"
                else:
                    actual_route = "conversation"
            else:
                actual_route = "conversation"
        else:
            actual_route = "conversation"

        print(f"Expected Route: {test_case['expected']}")
        print(f"Actual Route: {actual_route}")

        if actual_route == test_case['expected']:
            print("✅ PASS")
        else:
            print("❌ FAIL")

def demonstrate_improved_intent_detection():
    """Demonstrate improved intent detection for feedback."""

    print(f"\n{'='*60}")
    print("🔍 Improved Intent Detection for Feedback")
    print("=" * 60)

    test_messages = [
        "I loved that song!",
        "That was beautiful music",
        "I didn't like it very much",
        "What do you think about the song?",
        "My opinion is that it was great",
        "Can you create a song about love?",
        "Generate more music please",
        "How are you today?",
        "I feel the song was amazing",
        "That song was terrible"
    ]

    for message in test_messages:
        intent = simulate_feedback_intent_detection(message)
        print(f"'{message}' → {intent}")

if __name__ == "__main__":
    test_feedback_scenarios()
    demonstrate_improved_intent_detection()

    print(f"\n{'='*60}")
    print("💡 Key Insights:")
    print("- Feedback intent requires specific emotional/opinion words")
    print("- Feedback routing only works when is_final_song_received=True")
    print("- Feedback is blocked if already handled recently")
    print("- The intent detection logic can be improved for better accuracy")
    print("=" * 60)
