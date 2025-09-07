"""
LangGraph State schema for poymoymir conversation flow.

This module defines the TypedDict state structure that flows through the LangGraph workflow,
containing all necessary information for processing user messages through intent detection,
emotion analysis, and response generation.
"""

from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class ConversationState(TypedDict):
    """
    State object that flows through the LangGraph workflow.

    This contains all the information needed to process a user message
    through the various stages of analysis and response generation.
    """

    # Input message data
    chat_id: str
    user_message: str
    tg_msg_id: int
    tg_user_id: str
    user_uuid: str
    session_uuid: str
    full_name: str

    # Message context and history
    history: List[Dict[str, Any]]
    last_8_messages: List[Dict[str, str]]
    last_20_assistant_messages: List[Dict[str, str]]
    last_5_assistant_messages: List[Dict[str, str]]
    last_3_assistant_messages: List[Dict[str, str]]
    last_8_user_messages: List[Dict[str, str]]
    openai_msgs: List[Dict[str, str]]

    # Analysis results
    intent_analysis: Optional[Dict[str, Any]]
    emotion_analysis: Optional[Dict[str, Any]]
    msg_id: Optional[str]

    # Processing flags
    is_final_song_received: bool
    is_final_song_sent: bool
    is_confused: bool
    confusion_handled: bool
    song_generation_triggered: bool
    feedback_handled: bool

    # Response data
    ai_response: Optional[str]
    song_data: Optional[Dict[str, Any]]

    # Error handling
    errors: List[str]

    # Processing steps completed
    steps_completed: List[str]


class NodeResult(TypedDict):
    """
    Standard result structure returned by each node in the graph.
    """
    success: bool
    state_updates: Dict[str, Any]
    next_node: Optional[str]
    error_message: Optional[str]
