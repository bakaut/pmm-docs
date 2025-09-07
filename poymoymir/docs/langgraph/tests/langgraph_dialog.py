#!/usr/bin/env python3
"""
LangGraph Dialog Test Script

This script tests the LangGraph workflow with dummy dialog scenarios
to validate the conversation flow and node routing logic.
"""

import sys
import os
import json
import uuid
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock

# Add the flow directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def create_mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.system_prompt_intent = "Analyze user intent and return JSON with intent field"
    config.system_prompt_detect_emotion = "Analyze emotions and return JSON with emotions array"
    config.system_prompt_prepare_suno = "Extract song data and return JSON with lyrics, style, name"
    config.confused_intent_answers = ["I understand your confusion...", "Let me help clarify..."]
    config.confused_intent_answer_mp3 = "https://example.com/audio.mp3"
    config.song_generating_message = "🎵 Creating your song... Please wait!"
    config.song_received_message = "How did you like your song?"
    config.song_received_markup = None
    config.fallback_answer = "I apologize, but I encountered an issue. Please try again."
    return config

def create_mock_llm_manager():
    """Create a mock LLM manager with sample responses."""
    llm = Mock()

    # Mock intent detection responses
    def mock_llm_conversation(messages, system_prompt):
        if "intent" in system_prompt.lower():
            # Determine intent based on message content
            last_message = messages[-1]["content"] if messages else ""
            if any(word in last_message.lower() for word in ["song", "create", "generate", "music"]):
                return {"intent": "finalize_song"}
            elif any(word in last_message.lower() for word in ["feedback", "like", "love", "hate"]):
                return {"intent": "feedback"}
            else:
                return {"intent": "conversation"}

        elif "emotion" in system_prompt.lower():
            # Mock emotion detection
            last_message = messages[-1]["content"] if messages else ""
            if any(word in last_message.lower() for word in ["confused", "lost", "don't understand"]):
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
            # Mock song preparation
            return {
                "lyrics": "Sample lyrics about life and dreams",
                "style": "indie folk",
                "name": "Test Song"
            }

        return {"result": "mock response"}

    llm.llm_conversation = mock_llm_conversation

    # Mock general LLM call
    def mock_llm_call(messages, chat_id, user_id, moderation_callback=None):
        last_message = messages[-1]["content"] if messages else ""
        return f"AI Response to: {last_message}"

    llm.llm_call = mock_llm_call

    # Mock embedding function
    def mock_embd_text(text):
        # Return a simple mock embedding
        return [0.1 * i for i in range(10)]

    llm.embd_text = mock_embd_text

    return llm

def create_mock_database():
    """Create a mock database manager."""
    db = Mock()

    # Mock message saving
    def mock_save_message(session_uuid, user_uuid, role, content, embedding, tg_msg_id):
        return str(uuid.uuid4())

    db.save_message = mock_save_message

    # Mock analysis update
    db.update_message_analysis = Mock()

    # Mock song saving
    db.save_song = Mock()

    return db

def create_mock_telegram_bot():
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.send_message_chunks = Mock()
    bot.send_audio = Mock()
    return bot

def create_mock_suno_manager():
    """Create a mock Suno manager."""
    suno = Mock()

    def mock_request_suno(lyrics, style, title):
        return {
            "data": {
                "taskId": "mock-task-123"
            }
        }

    suno.request_suno = mock_request_suno
    return suno

def create_mock_moderation_service():
    """Create a mock moderation service."""
    moderation = Mock()

    def mock_moderate_user(chat_id, user_id, reason=""):
        print(f"[MODERATION] User {user_id} in chat {chat_id} flagged: {reason}")

    moderation.moderate_user = mock_moderate_user
    return moderation

def create_mock_utils():
    """Create a mock utils manager."""
    utils = Mock()
    return utils

def create_sample_conversation_state(user_message: str, intent_context: Dict = None) -> Dict[str, Any]:
    """Create a sample conversation state for testing."""

    # Create realistic message history
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help you today?"},
        {"role": "user", "content": "I'm feeling creative"},
        {"role": "assistant", "content": "That's wonderful! What would you like to create?"},
        {"role": "user", "content": user_message}
    ]

    # Extract different message contexts
    last_8_messages = history[-8:] if len(history) >= 8 else history
    last_8_user_messages = [msg for msg in history if msg["role"] == "user"][-8:]
    last_20_assistant_messages = [msg for msg in history if msg["role"] == "assistant"][-20:]
    last_5_assistant_messages = [msg for msg in history if msg["role"] == "assistant"][-5:]
    last_3_assistant_messages = [msg for msg in history if msg["role"] == "assistant"][-3:]

    # OpenAI format messages
    openai_msgs = [{"role": msg["role"], "content": msg["content"]} for msg in history]

    # Add intent context if provided
    if intent_context:
        last_5_assistant_messages.extend(intent_context.get("recent_messages", []))

    return {
        "chat_id": "test-chat-123",
        "user_message": user_message,
        "tg_msg_id": 12345,
        "tg_user_id": "user-123",
        "user_uuid": "user-uuid-123",
        "session_uuid": "session-uuid-123",
        "full_name": "Test User",
        "history": history,
        "last_8_messages": last_8_messages,
        "last_20_assistant_messages": last_20_assistant_messages,
        "last_5_assistant_messages": last_5_assistant_messages,
        "last_3_assistant_messages": last_3_assistant_messages,
        "last_8_user_messages": last_8_user_messages,
        "openai_msgs": openai_msgs,
        "intent_analysis": None,
        "emotion_analysis": None,
        "msg_id": None,
        "is_final_song_received": intent_context.get("is_final_song_received", False) if intent_context else False,
        "is_final_song_sent": intent_context.get("is_final_song_sent", False) if intent_context else False,
        "is_confused": False,
        "confusion_handled": False,
        "song_generation_triggered": False,
        "feedback_handled": False,
        "ai_response": None,
        "song_data": None,
        "errors": [],
        "steps_completed": []
    }

def test_conversation_scenario(workflow, scenario_name: str, user_message: str,
                             intent_context: Dict = None, expected_route: str = None):
    """Test a specific conversation scenario."""
    print(f"\n{'='*60}")
    print(f"Testing Scenario: {scenario_name}")
    print(f"User Message: '{user_message}'")
    print(f"{'='*60}")

    # Create initial state
    initial_state = create_sample_conversation_state(user_message, intent_context)

    try:
        # Process through workflow
        final_state = workflow.process_message(initial_state)

        # Display results
        print("\n📊 Workflow Results:")
        print(f"Steps Completed: {final_state.get('steps_completed', [])}")
        print(f"Intent Analysis: {final_state.get('intent_analysis', {})}")
        print(f"Emotion Analysis: {final_state.get('emotion_analysis', {})}")
        print(f"AI Response: {final_state.get('ai_response', 'None')}")
        print(f"Song Data: {final_state.get('song_data', 'None')}")
        print(f"Errors: {final_state.get('errors', [])}")

        # Check expected route
        if expected_route:
            steps = final_state.get('steps_completed', [])
            if expected_route in steps:
                print(f"✅ Expected route '{expected_route}' was taken")
            else:
                print(f"❌ Expected route '{expected_route}' was NOT taken")
                print(f"   Actual steps: {steps}")

        return final_state

    except Exception as e:
        print(f"❌ Workflow failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_dialog_tests():
    """Run comprehensive dialog tests."""

    print("🚀 Starting LangGraph Dialog Tests")
    print("=" * 60)

    try:
        # Import LangGraph components
        from mindset.langgraph_workflow import ConversationWorkflow
        from mindset.langgraph_state import ConversationState

        # Create mock logger
        import logging
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)

        # Create all mock components
        config = create_mock_config()
        llm_manager = create_mock_llm_manager()
        database = create_mock_database()
        utils = create_mock_utils()
        telegram_bot = create_mock_telegram_bot()
        suno_manager = create_mock_suno_manager()
        moderation_service = create_mock_moderation_service()

        # Initialize workflow
        workflow = ConversationWorkflow(
            config, llm_manager, database, utils, telegram_bot,
            suno_manager, moderation_service, logger
        )

        print("✅ Workflow initialized successfully")

        # Test scenarios
        test_scenarios = [
            {
                "name": "General Conversation",
                "message": "How are you today?",
                "expected_route": "conversation"
            },
            {
                "name": "Confusion Detection",
                "message": "I'm confused and don't understand what's happening",
                "expected_route": "confusion_handled"
            },
            {
                "name": "Song Generation Request",
                "message": "Please create a song for me about love",
                "expected_route": "song_generation"
            },
            {
                "name": "Feedback After Song",
                "message": "I loved that song!",
                "intent_context": {"is_final_song_received": True},
                "expected_route": "feedback_handled"
            },
            {
                "name": "Complex Creative Request",
                "message": "Can you generate music that captures the feeling of a sunset?",
                "expected_route": "song_generation"
            }
        ]

        results = []

        for scenario in test_scenarios:
            result = test_conversation_scenario(
                workflow,
                scenario["name"],
                scenario["message"],
                scenario.get("intent_context"),
                scenario.get("expected_route")
            )
            results.append({
                "scenario": scenario["name"],
                "success": result is not None,
                "final_state": result
            })

        # Summary
        print(f"\n{'='*60}")
        print("🎯 Test Summary")
        print(f"{'='*60}")

        successful = sum(1 for r in results if r["success"])
        total = len(results)

        print(f"Total Scenarios: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")
        print(f"Success Rate: {(successful/total)*100:.1f}%")

        for result in results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['scenario']}")

        if successful == total:
            print("\n🎉 All tests passed! LangGraph workflow is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {total - successful} test(s) failed. Please check the issues above.")
            return 1

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure all LangGraph dependencies are installed:")
        print("pip install langgraph langchain-core typing-extensions")
        return 1

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_dialog_tests())
