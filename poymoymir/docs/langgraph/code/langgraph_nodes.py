"""
LangGraph nodes for poymoymir conversation workflow.

This module contains the node implementations for the LangGraph workflow,
including intent detection, emotion analysis, and response generation.
"""

import logging
import random
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .langgraph_state import ConversationState, NodeResult
from .config import Config
from .llm_manager import LLMManager
from .database import DatabaseManager
from .utils import Utils
from .telegram_bot import TelegramBot
from .suno_manager import SunoManager
from .moderation import ModerationService


class BaseNode(ABC):
    """Base class for all LangGraph nodes."""

    def __init__(self, config: Config, llm_manager: LLMManager,
                 database: DatabaseManager, utils: Utils, logger: logging.Logger,
                 telegram_bot: Optional[TelegramBot] = None,
                 suno_manager: Optional[SunoManager] = None,
                 moderation_service: Optional[ModerationService] = None):
        self.config = config
        self.llm_manager = llm_manager
        self.database = database
        self.utils = utils
        self.logger = logger
        self.telegram_bot = telegram_bot
        self.suno_manager = suno_manager
        self.moderation_service = moderation_service

    @abstractmethod
    def execute(self, state: ConversationState) -> ConversationState:
        """Execute the node logic and return updated state."""
        pass

    def _update_state(self, state: ConversationState, updates: Dict[str, Any]) -> ConversationState:
        """Helper method to safely update state."""
        # Create a new state dict with updates
        new_state = state.copy()
        new_state.update(updates)
        return new_state


class IntentDetectionNode(BaseNode):
    """Node for detecting user intent from conversation history."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Analyze the conversation history to detect user intent.

        Args:
            state: Current conversation state

        Returns:
            Updated state with intent analysis results
        """
        self.logger.debug("Executing intent detection node")

        try:
            # Perform intent detection using LLM
            intent_result = self.llm_manager.llm_conversation(
                state["last_8_messages"],
                self.config.system_prompt_intent
            )

            self.logger.debug("Intent detection result: %s", intent_result)

            # Update state with intent analysis
            updates = {
                "intent_analysis": intent_result,
                "steps_completed": state["steps_completed"] + ["intent_detection"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Intent detection failed: %s", e)

            # Add error to state and continue
            updates = {
                "intent_analysis": {"intent": "unknown", "error": str(e)},
                "errors": state["errors"] + [f"Intent detection failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["intent_detection"]
            }

            return self._update_state(state, updates)


class EmotionAnalysisNode(BaseNode):
    """Node for analyzing user emotional state."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Analyze user messages to detect emotional state.

        Args:
            state: Current conversation state

        Returns:
            Updated state with emotion analysis results
        """
        self.logger.debug("Executing emotion analysis node")

        try:
            # Perform emotion analysis using LLM
            emotion_result = self.llm_manager.llm_conversation(
                state["last_8_user_messages"],
                self.config.system_prompt_detect_emotion
            )

            self.logger.debug("Emotion analysis result: %s", emotion_result)

            # Check for confusion state
            is_confused = any(
                e.get("name") == "Растерянность" and e.get("intensity", 0) > 90
                for e in emotion_result.get("emotions", [])
            )

            # Update state with emotion analysis
            updates = {
                "emotion_analysis": emotion_result,
                "is_confused": is_confused,
                "steps_completed": state["steps_completed"] + ["emotion_analysis"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Emotion analysis failed: %s", e)

            # Add error to state and continue
            updates = {
                "emotion_analysis": {"emotions": [], "error": str(e)},
                "is_confused": False,
                "errors": state["errors"] + [f"Emotion analysis failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["emotion_analysis"]
            }

            return self._update_state(state, updates)


class MessageSaveNode(BaseNode):
    """Node for saving user message and analysis to database."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Save the user message and analysis results to the database.

        Args:
            state: Current conversation state

        Returns:
            Updated state with message ID
        """
        self.logger.debug("Executing message save node")

        try:
            # Save user message to database
            msg_id = self.database.save_message(
                state["session_uuid"],
                state["user_uuid"],
                "user",
                state["user_message"],
                self.llm_manager.embd_text(state["user_message"]),
                state["tg_msg_id"]
            )

            # Save analysis results if available
            analysis = {}
            if state.get("intent_analysis"):
                analysis["intent"] = state["intent_analysis"]
            if state.get("emotion_analysis"):
                analysis["emotion"] = state["emotion_analysis"]

            if analysis:
                self.database.update_message_analysis(msg_id, analysis)

            # Update state with message ID
            updates = {
                "msg_id": msg_id,
                "steps_completed": state["steps_completed"] + ["message_save"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Message save failed: %s", e)

            # Add error to state
            updates = {
                "errors": state["errors"] + [f"Message save failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["message_save"]
            }

            return self._update_state(state, updates)


class ConfusionHandlerNode(BaseNode):
    """Node for handling confusion state with random responses."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Handle confusion state by sending random response or audio.

        Args:
            state: Current conversation state

        Returns:
            Updated state with confusion handling completed
        """
        self.logger.debug("Executing confusion handler node")

        try:
            # Check if confusion already handled recently
            if any(msg["content"] == "confused_send" for msg in state["last_20_assistant_messages"]):
                updates = {
                    "confusion_handled": True,
                    "steps_completed": state["steps_completed"] + ["confusion_handled"]
                }
                return self._update_state(state, updates)

            # Randomly choose between text and audio response
            if random.choice([True, False]):
                # Send text response
                answer = random.choice(self.config.confused_intent_answers)
                self.telegram_bot.send_message_chunks(state["chat_id"], answer)

                # Save assistant message
                self.database.save_message(
                    state["session_uuid"],
                    state["user_uuid"],
                    "assistant",
                    answer,
                    self.llm_manager.embd_text(answer),
                    state["tg_msg_id"]
                )
            else:
                # Send audio response
                self.telegram_bot.send_audio(
                    state["chat_id"],
                    audio_url=self.config.confused_intent_answer_mp3,
                    title="Ты можешь..."
                )

            # Mark confusion as handled
            self.database.save_message(
                state["session_uuid"],
                state["user_uuid"],
                "assistant",
                "confused_send",
                self.llm_manager.embd_text("confused_send"),
                state["tg_msg_id"]
            )

            updates = {
                "confusion_handled": True,
                "steps_completed": state["steps_completed"] + ["confusion_handled"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Confusion handling failed: %s", e)

            updates = {
                "confusion_handled": True,  # Mark as handled even on error to prevent loops
                "errors": state["errors"] + [f"Confusion handling failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["confusion_handled"]
            }

            return self._update_state(state, updates)


class SongGenerationNode(BaseNode):
    """Node for handling song generation requests."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Handle finalize_song intent by generating a song using Suno API.

        Args:
            state: Current conversation state

        Returns:
            Updated state with song generation results
        """
        self.logger.debug("Executing song generation node")

        try:
            # Extract song parameters from conversation history
            get_song = self.llm_manager.llm_conversation(
                state["last_3_assistant_messages"],
                self.config.system_prompt_prepare_suno
            )

            lyrics = get_song["lyrics"]
            style = get_song["style"]
            title = get_song["name"]

            self.logger.debug("Generating song with Suno API")

            # Request song generation from Suno API
            song = self.suno_manager.request_suno(lyrics, style, title)

            if not song:
                # Song generation failed
                self.logger.error("Failed to generate song with Suno API")
                self.telegram_bot.send_message_chunks(state["chat_id"], self.config.fallback_answer)

                self.database.save_message(
                    state["session_uuid"],
                    state["user_uuid"],
                    "assistant",
                    "ошибка генерации песни",
                    self.llm_manager.embd_text("ошибка генерации песни"),
                    state["tg_msg_id"]
                )

                updates = {
                    "song_generation_triggered": True,
                    "errors": state["errors"] + ["Song generation failed"],
                    "steps_completed": state["steps_completed"] + ["song_generation"]
                }

                return self._update_state(state, updates)

            # Song generation successful
            task_id = song["data"]["taskId"]

            # Send generation message to user
            self.telegram_bot.send_message_chunks(state["chat_id"], self.config.song_generating_message)

            # Save song and messages to database
            self.database.save_song(state["user_uuid"], state["session_uuid"], task_id, title, lyrics, style)

            self.database.save_message(
                state["session_uuid"],
                state["user_uuid"],
                "assistant",
                self.config.song_generating_message,
                self.llm_manager.embd_text(self.config.song_generating_message),
                state["tg_msg_id"]
            )

            self.database.save_message(
                state["session_uuid"],
                state["user_uuid"],
                "assistant",
                "финальная версия песни отправлена пользователю",
                self.llm_manager.embd_text("финальная версия песни отправлена пользователю"),
                state["tg_msg_id"]
            )

            self.logger.debug("Suno task ID: %s", task_id)

            updates = {
                "song_generation_triggered": True,
                "song_data": {"task_id": task_id, "title": title, "lyrics": lyrics, "style": style},
                "steps_completed": state["steps_completed"] + ["song_generation"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Song generation failed: %s", e)

            # Send fallback message
            self.telegram_bot.send_message_chunks(state["chat_id"], self.config.fallback_answer)

            updates = {
                "song_generation_triggered": True,
                "errors": state["errors"] + [f"Song generation failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["song_generation"]
            }

            return self._update_state(state, updates)


class FeedbackHandlerNode(BaseNode):
    """Node for handling feedback after song delivery."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Handle feedback intent after song has been received.

        Args:
            state: Current conversation state

        Returns:
            Updated state with feedback handling completed
        """
        self.logger.debug("Executing feedback handler node")

        try:
            # Check if feedback already sent recently
            if any(msg["content"] == "feedback_final_send" for msg in state["last_5_assistant_messages"]):
                updates = {
                    "feedback_handled": True,
                    "steps_completed": state["steps_completed"] + ["feedback_handled"]
                }
                return self._update_state(state, updates)

            # Send feedback request message
            self.telegram_bot.send_message_chunks(
                state["chat_id"],
                self.config.song_received_message,
                self.config.song_received_markup
            )

            # Mark feedback as sent
            self.database.save_message(
                state["session_uuid"],
                state["user_uuid"],
                "assistant",
                "feedback_final_send",
                self.llm_manager.embd_text("feedback_final_send"),
                state["tg_msg_id"]
            )

            updates = {
                "feedback_handled": True,
                "steps_completed": state["steps_completed"] + ["feedback_handled"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Feedback handling failed: %s", e)

            updates = {
                "feedback_handled": True,  # Mark as handled even on error
                "errors": state["errors"] + [f"Feedback handling failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["feedback_handled"]
            }

            return self._update_state(state, updates)


class ConversationNode(BaseNode):
    """Node for general AI conversation responses."""

    def execute(self, state: ConversationState) -> ConversationState:
        """
        Generate general AI conversation response.

        Args:
            state: Current conversation state

        Returns:
            Updated state with AI response
        """
        self.logger.debug("Executing conversation node")

        try:
            # Generate AI response using LLM with moderation if available
            moderation_callback = None
            if self.moderation_service:
                moderation_callback = self.moderation_service.moderate_user

            ai_answer = self.llm_manager.llm_call(
                state["openai_msgs"],
                state["chat_id"],
                state["tg_user_id"],
                moderation_callback
            )

            if ai_answer and ai_answer != self.config.fallback_answer:
                # Save assistant response to database
                self.database.save_message(
                    state["session_uuid"],
                    state["user_uuid"],
                    "assistant",
                    ai_answer,
                    self.llm_manager.embd_text(ai_answer),
                    state["tg_msg_id"]
                )

            # Send response to Telegram
            try:
                self.telegram_bot.send_message_chunks(state["chat_id"], ai_answer)
            except Exception as e:
                self.logger.exception("Failed to send message to Telegram %s", state["chat_id"])

            updates = {
                "ai_response": ai_answer,
                "steps_completed": state["steps_completed"] + ["conversation"]
            }

            return self._update_state(state, updates)

        except Exception as e:
            self.logger.error("Conversation failed: %s", e)

            # Send fallback response
            try:
                self.telegram_bot.send_message_chunks(state["chat_id"], self.config.fallback_answer)
            except Exception:
                self.logger.exception("Failed to send fallback message to Telegram %s", state["chat_id"])

            updates = {
                "ai_response": self.config.fallback_answer,
                "errors": state["errors"] + [f"Conversation failed: {str(e)}"],
                "steps_completed": state["steps_completed"] + ["conversation"]
            }

            return self._update_state(state, updates)
