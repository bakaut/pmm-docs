"""
LangGraph workflow for poymoymir conversation processing.

This module creates and manages the LangGraph workflow that processes user messages
through intent detection, emotion analysis, and appropriate response generation.
"""

import logging
from typing import Dict, Any, Literal

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from .langgraph_state import ConversationState
from .langgraph_nodes import (
    IntentDetectionNode, EmotionAnalysisNode, MessageSaveNode,
    ConfusionHandlerNode, SongGenerationNode, FeedbackHandlerNode,
    ConversationNode
)
from .config import Config
from .llm_manager import LLMManager
from .database import DatabaseManager
from .utils import Utils
from .telegram_bot import TelegramBot
from .suno_manager import SunoManager
from .moderation import ModerationService


def should_handle_confusion(state: ConversationState) -> Literal["confusion", "continue"]:
    """
    Decide whether to handle confusion state.

    Args:
        state: Current conversation state

    Returns:
        "confusion" if user is confused and hasn't been handled recently, "continue" otherwise
    """
    if not state.get("is_confused", False):
        return "continue"

    # Check if confusion was already handled recently
    if any(msg["content"] == "confused_send" for msg in state["last_20_assistant_messages"]):
        return "continue"

    return "confusion"


def should_generate_song(state: ConversationState) -> Literal["song_generation", "continue"]:
    """
    Decide whether to generate a song.

    Args:
        state: Current conversation state

    Returns:
        "song_generation" if intent is finalize_song and no song sent recently, "continue" otherwise
    """
    intent_analysis = state.get("intent_analysis") or {}
    intent = intent_analysis.get("intent", "")

    if intent != "finalize_song":
        return "continue"

    # Check if final song was already sent or received recently
    if state.get("is_final_song_received", False) or state.get("is_final_song_sent", False):
        return "continue"

    return "song_generation"


def should_handle_feedback(state: ConversationState) -> Literal["feedback", "continue"]:
    """
    Decide whether to handle feedback.

    Args:
        state: Current conversation state

    Returns:
        "feedback" if intent is feedback and song was received, "continue" otherwise
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


def route_after_analysis(state: ConversationState) -> Literal["confusion", "song_generation", "feedback", "conversation"]:
    """
    Route to appropriate handler after analysis is complete.

    Args:
        state: Current conversation state

    Returns:
        Next node to execute based on analysis results
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


class ConversationWorkflow:
    """
    LangGraph workflow for processing poymoymir conversations.

    This class creates and manages the state graph that processes user messages
    through the various analysis and response generation steps.
    """

    def __init__(self, config: Config, llm_manager: LLMManager, database: DatabaseManager,
                 utils: Utils, telegram_bot: TelegramBot, suno_manager: SunoManager,
                 moderation_service: ModerationService, logger: logging.Logger):
        """
        Initialize the conversation workflow.

        Args:
            config: Application configuration
            llm_manager: LLM management instance
            database: DatabaseManager connection
            utils: Utility functions
            telegram_bot: Telegram bot instance
            suno_manager: Suno API manager
            moderation_service: Moderation service instance
            logger: Logger instance
        """
        self.config = config
        self.llm_manager = llm_manager
        self.database = database
        self.utils = utils
        self.telegram_bot = telegram_bot
        self.suno_manager = suno_manager
        self.moderation_service = moderation_service
        self.logger = logger

        # Initialize nodes
        self.intent_node = IntentDetectionNode(
            config, llm_manager, database, utils, logger
        )
        self.emotion_node = EmotionAnalysisNode(
            config, llm_manager, database, utils, logger
        )
        self.message_save_node = MessageSaveNode(
            config, llm_manager, database, utils, logger
        )
        self.confusion_node = ConfusionHandlerNode(
            config, llm_manager, database, utils, logger, telegram_bot
        )
        self.song_node = SongGenerationNode(
            config, llm_manager, database, utils, logger, telegram_bot, suno_manager
        )
        self.feedback_node = FeedbackHandlerNode(
            config, llm_manager, database, utils, logger, telegram_bot
        )
        self.conversation_node = ConversationNode(
            config, llm_manager, database, utils, logger, telegram_bot, None, moderation_service
        )

        # Build the workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Returns:
            Compiled state graph ready for execution
        """
        # Create the state graph
        workflow = StateGraph(ConversationState)

        # Add nodes to the graph
        workflow.add_node("intent_detection", self.intent_node.execute)
        workflow.add_node("emotion_analysis", self.emotion_node.execute)
        workflow.add_node("message_save", self.message_save_node.execute)
        workflow.add_node("confusion", self.confusion_node.execute)
        workflow.add_node("song_generation", self.song_node.execute)
        workflow.add_node("feedback", self.feedback_node.execute)
        workflow.add_node("conversation", self.conversation_node.execute)

        # Set entry point
        workflow.set_entry_point("intent_detection")

        # Add edges between nodes
        workflow.add_edge("intent_detection", "emotion_analysis")
        workflow.add_edge("emotion_analysis", "message_save")

        # Add conditional routing after message save
        workflow.add_conditional_edges(
            "message_save",
            route_after_analysis,
            {
                "confusion": "confusion",
                "song_generation": "song_generation",
                "feedback": "feedback",
                "conversation": "conversation"
            }
        )

        # All specialized handlers end the workflow
        workflow.add_edge("confusion", END)
        workflow.add_edge("song_generation", END)
        workflow.add_edge("feedback", END)
        workflow.add_edge("conversation", END)

        # Compile the workflow
        return workflow.compile()

    def process_message(self, initial_state: ConversationState) -> ConversationState:
        """
        Process a user message through the workflow.

        Args:
            initial_state: Initial conversation state

        Returns:
            Final state after processing
        """
        try:
            self.logger.debug("Starting conversation workflow")

            # Run the workflow
            final_state = self.workflow.invoke(initial_state)

            self.logger.debug("Conversation workflow completed")
            return final_state

        except Exception as e:
            self.logger.error("Workflow execution failed: %s", e)

            # Return state with error
            error_state = initial_state.copy()
            error_state["errors"] = initial_state.get("errors", []) + [f"Workflow failed: {str(e)}"]

            return error_state

    def get_workflow_visualization(self) -> str:
        """
        Get a string representation of the workflow for debugging.

        Returns:
            Workflow structure as string
        """
        try:
            return str(self.workflow.get_graph().draw_mermaid())
        except Exception as e:
            self.logger.error("Failed to generate workflow visualization: %s", e)
            return "Workflow visualization not available"
