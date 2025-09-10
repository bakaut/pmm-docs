"""
Message analysis module for song creation process detection.

This module contains:
- MessageAnalyzer class that identifies song creation processes from user messages
- Methods for reading messages by user UUID and grouping them into song creation segments
- LLM-based classification of messages to detect start and end of song creation processes
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from database import DatabaseManager
from llm_manager import LLMManager


class MessageAnalyzer:
    """Analyzes user messages to identify song creation processes."""

    def __init__(self, db: DatabaseManager, llm: LLMManager, logger: Optional[logging.Logger] = None):
        """
        Initialize MessageAnalyzer with database and LLM managers.

        Args:
            db: DatabaseManager instance for accessing messages
            llm: LLMManager instance for classification
            logger: Optional logger instance
        """
        self.db = db
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)

    def _classify_message_intent(self, message_content: str) -> Dict[str, Any]:
        """
        Classify a message to determine if it's part of a song creation process.

        Args:
            message_content: The content of the message to classify

        Returns:
            Dictionary with classification results
        """
        # Use the existing intent detection prompt from config
        system_prompt = """
        You are a classifier that identifies user intents in a song creation process.
        
        Possible intents:
        - "create_song": User wants to start a new song
        - "edit_song": User wants to modify the current version
        - "finalize_song": User is satisfied and considers the song complete
        - "cancel": User wants to cancel the last action or start over
        - "clarify": User asks a clarifying question or intent is unclear
        - "arrange_song": User selects style, tempo, instruments
        - "song_received": User has received the final text version of the song
        - "feedback": User has received the audio version and left feedback
        - "continue_song": User returns to an unfinished song
        - "other": Any other intent
        
        Analyze the following message and determine the intent.
        Respond with a JSON object containing:
        {
            "intent": "one of the above intents",
            "confidence": 0-100,
            "reason": "brief explanation"
        }
        """
        
        try:
            response = self.llm.llm_response(
                user_message=message_content,
                system_message=system_prompt,
                is_json_response=True
            )
            return response
        except Exception as e:
            self.logger.error("Failed to classify message: %s", e)
            return {"intent": "other", "confidence": 0, "reason": "classification failed"}

    def _is_start_of_song_process(self, intent_classification: Dict[str, Any]) -> bool:
        """
        Determine if a message indicates the start of a song creation process.

        Args:
            intent_classification: The classification result from _classify_message_intent

        Returns:
            True if this is the start of a song process, False otherwise
        """
        start_intents = ["create_song", "continue_song"]
        intent = intent_classification.get("intent", "")
        confidence = intent_classification.get("confidence", 0)
        return intent in start_intents and confidence > 70

    def _is_end_of_song_process(self, intent_classification: Dict[str, Any]) -> bool:
        """
        Determine if a message indicates the end of a song creation process.

        Args:
            intent_classification: The classification result from _classify_message_intent

        Returns:
            True if this is the end of a song process, False otherwise
        """
        end_intents = ["finalize_song", "song_received", "feedback"]
        intent = intent_classification.get("intent", "")
        confidence = intent_classification.get("confidence", 0)
        return intent in end_intents and confidence > 70

    def read_messages_by_user_uuid(self, user_uuid: str) -> List[Dict[str, Any]]:
        """
        Read all messages for a specific user, ordered by creation time.

        Args:
            user_uuid: The UUID of the user

        Returns:
            List of messages sorted by creation time
        """
        try:
            messages = self.db.query_all(
                "SELECT id, session_id, role, content, created_at, analysis "
                "FROM messages WHERE user_id = %s ORDER BY created_at ASC",
                (user_uuid,)
            )
            return messages
        except Exception as e:
            self.logger.error("Failed to read messages for user %s: %s", user_uuid, e)
            return []

    def identify_song_processes(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify song creation processes from a list of messages.

        Args:
            messages: List of messages sorted by creation time

        Returns:
            List of song creation processes with start and end messages
        """
        processes = []
        current_process = None

        for message in messages:
            # Classify the message intent
            intent_classification = self._classify_message_intent(message["content"])
            message["intent_classification"] = intent_classification

            # Check if this is the start of a new song process
            if self._is_start_of_song_process(intent_classification):
                # If we were already tracking a process, save it
                if current_process:
                    processes.append(current_process)
                
                # Start a new process
                current_process = {
                    "id": str(uuid.uuid4()),
                    "start_message_id": message["id"],
                    "start_timestamp": message["created_at"],
                    "messages": [message],
                    "status": "in_progress"
                }
            
            # If we're tracking a process, add this message to it
            elif current_process:
                current_process["messages"].append(message)
                
                # Check if this is the end of the current process
                if self._is_end_of_song_process(intent_classification):
                    current_process["end_message_id"] = message["id"]
                    current_process["end_timestamp"] = message["created_at"]
                    current_process["status"] = "completed"
                    processes.append(current_process)
                    current_process = None

        # If we still have an in-progress process, save it
        if current_process:
            processes.append(current_process)

        return processes

    def group_messages_into_jsons(self, user_uuid: str, messages_per_json: int = 50) -> List[Dict[str, Any]]:
        """
        Read messages by user UUID and create JSONs grouped by song creation processes.
        Each JSON contains approximately 50 messages from one song creation process.

        Args:
            user_uuid: The UUID of the user
            messages_per_json: Target number of messages per JSON (default 50)

        Returns:
            List of JSON objects containing grouped messages
        """
        # Read all messages for the user
        all_messages = self.read_messages_by_user_uuid(user_uuid)
        
        if not all_messages:
            self.logger.info("No messages found for user %s", user_uuid)
            return []

        # Identify song creation processes
        song_processes = self.identify_song_processes(all_messages)
        
        json_groups = []
        
        for process in song_processes:
            messages = process["messages"]
            
            # Split messages into chunks of approximately messages_per_json
            for i in range(0, len(messages), messages_per_json):
                chunk = messages[i:i + messages_per_json]
                
                # Create a JSON object for this chunk
                json_obj = {
                    "process_id": process["id"],
                    "chunk_id": str(uuid.uuid4()),
                    "start_message_id": chunk[0]["id"] if chunk else None,
                    "end_message_id": chunk[-1]["id"] if chunk else None,
                    "start_timestamp": chunk[0]["created_at"].isoformat() if chunk and chunk[0]["created_at"] else None,
                    "end_timestamp": chunk[-1]["created_at"].isoformat() if chunk and chunk[-1]["created_at"] else None,
                    "message_count": len(chunk),
                    "messages": [
                        {
                            "id": msg["id"],
                            "session_id": msg["session_id"],
                            "role": msg["role"],
                            "content": msg["content"],
                            "created_at": msg["created_at"].isoformat() if msg["created_at"] else None,
                            "intent": msg.get("intent_classification", {}).get("intent", "unknown"),
                            "intent_confidence": msg.get("intent_classification", {}).get("confidence", 0)
                        }
                        for msg in chunk
                    ]
                }
                
                json_groups.append(json_obj)
        
        self.logger.info("Created %d JSON groups for user %s", len(json_groups), user_uuid)
        return json_groups