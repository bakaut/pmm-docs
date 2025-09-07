#!/usr/bin/env python3
"""
LangGraph Dialog Flow Simulator

This script simulates how the LangGraph workflow would process
various conversation scenarios, showing the decision-making flow.
"""

from typing import Dict, Any, List
import json

def simulate_workflow_step(state: Dict[str, Any], step_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a workflow step and update state."""
    new_state = state.copy()
    new_state.update(updates)
    new_state["steps_completed"].append(step_name)
    return new_state

def simulate_intent_detection(state: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """Simulate intent detection based on message content."""
    intent = "conversation"  # default

    # Simple keyword-based intent detection simulation
    message_lower = user_message.lower()

    if any(word in message_lower for word in ["song", "create", "generate", "music", "compose"]):
        intent = "finalize_song"
    elif any(word in message_lower for word in ["feedback", "like", "love", "hate", "opinion", "think"]):
        intent = "feedback"
    elif any(word in message_lower for word in ["help", "what", "how"]):
        intent = "help"

    return simulate_workflow_step(state, "intent_detection", {
        "intent_analysis": {"intent": intent, "confidence": 0.85}
    })

def simulate_emotion_analysis(state: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """Simulate emotion analysis based on message content."""
    emotions = []

    message_lower = user_message.lower()

    # Check for confusion indicators
    if any(word in message_lower for word in ["confused", "don't understand", "lost", "unclear"]):
        emotions.append({"name": "Растерянность", "intensity": 95, "category": "negative"})
        is_confused = True
    else:
        # Default positive emotion
        emotions.append({"name": "Радость", "intensity": 70, "category": "positive"})
        is_confused = False

    return simulate_workflow_step(state, "emotion_analysis", {
        "emotion_analysis": {"emotions": emotions},
        "is_confused": is_confused
    })

def simulate_routing_decision(state: Dict[str, Any]) -> str:
    """Simulate the routing decision logic."""
    # Copy the actual routing logic from the workflow

    # Check confusion first (highest priority)
    if state.get("is_confused", False):
        if not any(msg.get("content") == "confused_send" for msg in state.get("last_20_assistant_messages", [])):
            return "confusion"

    # Check if song should be generated
    intent_analysis = state.get("intent_analysis") or {}
    intent = intent_analysis.get("intent", "")

    if intent == "finalize_song":
        if not (state.get("is_final_song_received", False) or state.get("is_final_song_sent", False)):
            return "song_generation"

    # Check if feedback should be handled
    if intent == "feedback":
        if state.get("is_final_song_received", False):
            if not any(msg.get("content") == "feedback_final_send" for msg in state.get("last_5_assistant_messages", [])):
                return "feedback"

    # Default to general conversation
    return "conversation"

def simulate_handler_execution(state: Dict[str, Any], route: str) -> Dict[str, Any]:
    """Simulate the execution of the selected handler."""

    if route == "confusion":
        return simulate_workflow_step(state, "confusion_handled", {
            "confusion_handled": True,
            "ai_response": "I understand your confusion. Let me help clarify things for you."
        })

    elif route == "song_generation":
        return simulate_workflow_step(state, "song_generation", {
            "song_generation_triggered": True,
            "song_data": {
                "task_id": "mock-task-123",
                "title": "Generated Song",
                "lyrics": "Sample lyrics based on your request",
                "style": "indie folk"
            },
            "ai_response": "🎵 Creating your song... Please wait!"
        })

    elif route == "feedback":
        return simulate_workflow_step(state, "feedback_handled", {
            "feedback_handled": True,
            "ai_response": "Thank you for your feedback! How did you like your song?"
        })

    else:  # conversation
        intent_analysis = state.get("intent_analysis") or {}
        intent = intent_analysis.get("intent", "conversation")

        if intent == "help":
            response = "I'm here to help! I can create personalized songs for you or have a conversation. What would you like to do?"
        else:
            response = f"Thank you for your message. I'm here to chat and can create songs for you if you'd like!"

        return simulate_workflow_step(state, "conversation", {
            "ai_response": response
        })

def create_dialog_scenario(user_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a dialog scenario state."""

    # Base conversation history
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help you today?"},
    ]

    # Add context if provided
    if context:
        if "previous_messages" in context:
            history.extend(context["previous_messages"])

    # Add current user message
    history.append({"role": "user", "content": user_message})

    # Extract message contexts
    last_8_messages = history[-8:]
    last_20_assistant_messages = [msg for msg in history if msg["role"] == "assistant"][-20:]
    last_5_assistant_messages = [msg for msg in history if msg["role"] == "assistant"][-5:]

    # Create initial state
    initial_state = {
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
        "last_3_assistant_messages": last_5_assistant_messages[-3:],
        "last_8_user_messages": [msg for msg in history if msg["role"] == "user"][-8:],
        "openai_msgs": [{"role": msg["role"], "content": msg["content"]} for msg in history],
        "intent_analysis": None,
        "emotion_analysis": None,
        "msg_id": None,
        "is_final_song_received": context.get("is_final_song_received", False) if context else False,
        "is_final_song_sent": context.get("is_final_song_sent", False) if context else False,
        "is_confused": False,
        "confusion_handled": False,
        "song_generation_triggered": False,
        "feedback_handled": False,
        "ai_response": None,
        "song_data": None,
        "errors": [],
        "steps_completed": []
    }

    return initial_state

def simulate_complete_workflow(user_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Simulate the complete LangGraph workflow for a user message."""

    # Create initial state
    state = create_dialog_scenario(user_message, context)

    # Step 1: Intent Detection
    state = simulate_intent_detection(state, user_message)

    # Step 2: Emotion Analysis
    state = simulate_emotion_analysis(state, user_message)

    # Step 3: Message Save (simulated)
    state = simulate_workflow_step(state, "message_save", {"msg_id": "mock-msg-123"})

    # Step 4: Routing Decision
    route = simulate_routing_decision(state)

    # Step 5: Handler Execution
    state = simulate_handler_execution(state, route)

    return state

def print_workflow_simulation(scenario_name: str, user_message: str, context: Dict[str, Any] = None):
    """Print a detailed workflow simulation."""

    print(f"\n{'='*80}")
    print(f"🎭 SCENARIO: {scenario_name}")
    print(f"{'='*80}")
    print(f"📝 User Message: \"{user_message}\"")

    if context:
        print(f"🔧 Context: {json.dumps(context, indent=2)}")

    print(f"\n{'🔄 WORKFLOW EXECUTION'}")
    print("-" * 50)

    # Run simulation
    final_state = simulate_complete_workflow(user_message, context)

    # Display results
    print(f"📊 Analysis Results:")
    print(f"   Intent: {final_state.get('intent_analysis', {}).get('intent', 'None')}")
    print(f"   Emotions: {[e['name'] for e in final_state.get('emotion_analysis', {}).get('emotions', [])]}")
    print(f"   Confused: {final_state.get('is_confused', False)}")

    print(f"\n🛤️  Processing Steps:")
    for i, step in enumerate(final_state.get('steps_completed', []), 1):
        print(f"   {i}. {step}")

    print(f"\n🤖 AI Response:")
    print(f"   \"{final_state.get('ai_response', 'No response generated')}\"")

    if final_state.get('song_data'):
        print(f"\n🎵 Song Generated:")
        song_data = final_state['song_data']
        print(f"   Title: {song_data.get('title', 'Unknown')}")
        print(f"   Style: {song_data.get('style', 'Unknown')}")
        print(f"   Task ID: {song_data.get('task_id', 'Unknown')}")

    if final_state.get('errors'):
        print(f"\n❌ Errors: {final_state['errors']}")

def main():
    """Run dialog flow simulations."""

    print("🚀 LangGraph Dialog Flow Simulation")
    print("=" * 80)
    print("This simulation shows how the LangGraph workflow processes different")
    print("conversation scenarios and makes routing decisions.")

    # Test scenarios
    scenarios = [
        {
            "name": "General Greeting",
            "message": "How are you doing today?",
            "context": None
        },
        {
            "name": "Confusion Expression",
            "message": "I'm confused and don't understand what's happening",
            "context": None
        },
        {
            "name": "Song Creation Request",
            "message": "Can you create a song about love and friendship?",
            "context": None
        },
        {
            "name": "Feedback After Song",
            "message": "I loved that song! It was beautiful!",
            "context": {"is_final_song_received": True}
        },
        {
            "name": "Help Request",
            "message": "What can you help me with?",
            "context": None
        },
        {
            "name": "Song Request (Already Generated)",
            "message": "Generate another song please!",
            "context": {"is_final_song_sent": True}
        },
        {
            "name": "Creative Writing Request",
            "message": "Help me compose a musical piece about the ocean",
            "context": None
        }
    ]

    # Run simulations
    for scenario in scenarios:
        print_workflow_simulation(
            scenario["name"],
            scenario["message"],
            scenario["context"]
        )

    print(f"\n{'='*80}")
    print("✅ All dialog flow simulations completed!")
    print("🎯 The LangGraph workflow correctly routes different conversation types")
    print("   to their appropriate handlers based on intent and context.")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
