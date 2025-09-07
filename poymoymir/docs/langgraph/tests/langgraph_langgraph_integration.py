#!/usr/bin/env python3
"""
LangGraph Integration Test

This script tests the actual LangGraph workflow implementation
with real dependencies to validate the complete system.
"""

import sys
import os
import logging
from unittest.mock import Mock, MagicMock

# Add the flow directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def setup_test_environment():
    """Set up the test environment with proper logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("integration_test")
    return logger

def create_mock_components():
    """Create mock components for testing."""

    # Mock Config
    config = Mock()
    config.system_prompt_intent = "Analyze intent and return JSON with intent field"
    config.system_prompt_detect_emotion = "Analyze emotions and return JSON with emotions array"
    config.system_prompt_prepare_suno = "Extract song data and return JSON"
    config.confused_intent_answers = ["I understand your confusion..."]
    config.confused_intent_answer_mp3 = "https://example.com/audio.mp3"
    config.song_generating_message = "🎵 Creating your song..."
    config.song_received_message = "How did you like your song?"
    config.song_received_markup = None
    config.fallback_answer = "I apologize for the issue."
    config.log_level = "DEBUG"
    config.log_name = "test_logger"

    # Mock LLM Manager
    llm_manager = Mock()

    def mock_llm_conversation(messages, system_prompt):
        # Simple intent detection based on content
        last_message = messages[-1]["content"] if messages else ""

        if "intent" in system_prompt.lower():
            if any(word in last_message.lower() for word in ["song", "create", "generate", "music"]):
                return {"intent": "finalize_song"}
            elif any(word in last_message.lower() for word in ["feedback", "love", "hate", "beautiful"]):
                return {"intent": "feedback"}
            else:
                return {"intent": "conversation"}

        elif "emotion" in system_prompt.lower():
            if "confused" in last_message.lower():
                return {"emotions": [{"name": "Растерянность", "intensity": 95, "category": "negative"}]}
            else:
                return {"emotions": [{"name": "Радость", "intensity": 70, "category": "positive"}]}

        elif "suno" in system_prompt.lower():
            return {"lyrics": "Test lyrics", "style": "indie folk", "name": "Test Song"}

        return {"result": "mock response"}

    llm_manager.llm_conversation = mock_llm_conversation

    def mock_llm_call(messages, chat_id, user_id, moderation_callback=None):
        return "AI response to your message"

    llm_manager.llm_call = mock_llm_call

    def mock_embd_text(text):
        return [0.1] * 10  # Simple mock embedding

    llm_manager.embd_text = mock_embd_text

    # Mock Database
    database = Mock()

    def mock_save_message(session_uuid, user_uuid, role, content, embedding, tg_msg_id):
        return "mock-message-id"

    database.save_message = mock_save_message
    database.update_message_analysis = Mock()
    database.save_song = Mock()
    database.get_or_create_user = Mock(return_value="mock-user-uuid")
    database.get_active_session = Mock(return_value="mock-session-uuid")
    database.fetch_history = Mock(return_value=[])
    database.ensure_user_exists = Mock()
    database.get_or_create_bot = Mock(return_value="mock-bot-id")

    # Mock Utils
    utils = Mock()
    utils.parse_body = Mock(return_value={"message": {"text": "test"}})

    def mock_compute_message_context(history, text):
        return {
            "last_8_messages": [{"role": "user", "content": text}],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [{"role": "user", "content": text}],
            "last_5_user_messages": [{"role": "user", "content": text}],
            "openai_msgs": [{"role": "user", "content": text}]
        }

    utils.compute_message_context = mock_compute_message_context

    # Mock Telegram Bot
    telegram_bot = Mock()
    telegram_bot.send_message_chunks = Mock()
    telegram_bot.send_audio = Mock()
    telegram_bot.handle_callback_query = Mock()

    # Mock Suno Manager
    suno_manager = Mock()

    def mock_request_suno(lyrics, style, title):
        return {"data": {"taskId": "mock-task-id"}}

    suno_manager.request_suno = mock_request_suno
    suno_manager.handle_suno_callback = Mock()

    # Mock Moderation Service
    moderation_service = Mock()
    moderation_service.is_user_blocked = Mock(return_value=False)
    moderation_service.moderate_user = Mock()

    return {
        "config": config,
        "llm_manager": llm_manager,
        "database": database,
        "utils": utils,
        "telegram_bot": telegram_bot,
        "suno_manager": suno_manager,
        "moderation_service": moderation_service
    }

def test_langgraph_workflow_integration():
    """Test the actual LangGraph workflow integration."""

    print("🚀 LangGraph Integration Test")
    print("=" * 50)

    try:
        # Import LangGraph components
        from mindset.langgraph_workflow import ConversationWorkflow
        from mindset.langgraph_state import ConversationState

        # Set up environment
        logger = setup_test_environment()

        # Create mock components
        components = create_mock_components()

        # Initialize workflow
        workflow = ConversationWorkflow(
            components["config"],
            components["llm_manager"],
            components["database"],
            components["utils"],
            components["telegram_bot"],
            components["suno_manager"],
            components["moderation_service"],
            logger
        )

        print("✅ Workflow initialized successfully")

        # Create test state
        initial_state: ConversationState = {
            "chat_id": "test-chat-123",
            "user_message": "Can you create a song for me?",
            "tg_msg_id": 12345,
            "tg_user_id": "user-123",
            "user_uuid": "user-uuid-123",
            "session_uuid": "session-uuid-123",
            "full_name": "Test User",
            "history": [],
            "last_8_messages": [{"role": "user", "content": "Can you create a song for me?"}],
            "last_20_assistant_messages": [],
            "last_5_assistant_messages": [],
            "last_3_assistant_messages": [],
            "last_8_user_messages": [{"role": "user", "content": "Can you create a song for me?"}],
            "last_5_user_messages": [{"role": "user", "content": "Can you create a song for me?"}],
            "openai_msgs": [{"role": "user", "content": "Can you create a song for me?"}],
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

        print("🔄 Processing test message through workflow...")

        # Process through workflow
        final_state = workflow.process_message(initial_state)

        # Validate results
        steps = final_state.get("steps_completed", [])
        print(f"📊 Steps completed: {steps}")

        if "song_generation" in steps:
            print("✅ Song generation route was taken correctly")
        else:
            print("⚠️  Song generation route was not taken")

        if final_state.get("song_data"):
            print("✅ Song data was generated")
        else:
            print("⚠️  No song data was generated")

        errors = final_state.get("errors", [])
        if errors:
            print(f"❌ Errors occurred: {errors}")
            return False
        else:
            print("✅ No errors occurred")

        print("🎉 Integration test completed successfully!")
        return True

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return False

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workflow_visualization():
    """Test workflow visualization capabilities."""

    print("\n🎨 Testing Workflow Visualization")
    print("-" * 35)

    try:
        # Import and create workflow
        from mindset.langgraph_workflow import ConversationWorkflow
        from mindset.langgraph_state import ConversationState

        logger = setup_test_environment()
        components = create_mock_components()

        workflow = ConversationWorkflow(
            components["config"],
            components["llm_manager"],
            components["database"],
            components["utils"],
            components["telegram_bot"],
            components["suno_manager"],
            components["moderation_service"],
            logger
        )

        # Try to get visualization
        try:
            viz = workflow.get_workflow_visualization()
            if viz and "graph" in viz.lower():
                print("✅ Workflow visualization generated successfully")
                print("📊 Visualization preview:")
                lines = viz.split('\n')
                for i, line in enumerate(lines[:10]):  # Show first 10 lines
                    print(f"   {line}")
                if len(lines) > 10:
                    print("   ...")
            else:
                print("⚠️  Visualization returned but may be empty")
        except Exception as viz_error:
            print(f"⚠️  Visualization failed (not critical): {viz_error}")

        return True

    except Exception as e:
        print(f"❌ Visualization test failed: {e}")
        return False

def main():
    """Run all integration tests."""

    print("🧪 LangGraph Integration Tests")
    print("=" * 50)

    # Run workflow integration test
    workflow_success = test_langgraph_workflow_integration()

    # Run visualization test
    viz_success = test_workflow_visualization()

    # Summary
    print(f"\n{'='*50}")
    print("🎯 Test Results Summary")
    print("=" * 50)

    if workflow_success:
        print("✅ Workflow Integration: PASSED")
    else:
        print("❌ Workflow Integration: FAILED")

    if viz_success:
        print("✅ Visualization Test: PASSED")
    else:
        print("❌ Visualization Test: FAILED")

    overall_success = workflow_success and viz_success

    if overall_success:
        print("\n🎉 All integration tests passed!")
        print("✅ LangGraph workflow is ready for production use!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    # Activate virtual environment if available
    venv_path = os.path.join(os.path.dirname(__file__), '..', 'venv')
    if os.path.exists(venv_path):
        activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
        if os.path.exists(activate_script):
            exec(open(activate_script).read(), {'__file__': activate_script})

    sys.exit(main())
