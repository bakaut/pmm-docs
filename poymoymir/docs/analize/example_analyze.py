"""
Example usage of the MessageAnalyzer class.
"""

import uuid
from mindset.analyze import MessageAnalyzer
from mindset.database import DatabaseManager
from mindset.llm_manager import LLMManager
from mindset.config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Initialize components
    config = Config.from_env()
    db = DatabaseManager(config, logger)
    llm = LLMManager(config, None, logger)  # We'll need to pass utils for full functionality
    
    # Create analyzer
    analyzer = MessageAnalyzer(db, llm, logger)
    
    # Example: Group messages for a specific user
    user_uuid = "example-user-uuid"  # Replace with actual user UUID
    json_groups = analyzer.group_messages_into_jsons(user_uuid, messages_per_json=50)
    
    # Print results
    print(f"Created {len(json_groups)} JSON groups for user {user_uuid}")
    for i, group in enumerate(json_groups):
        print(f"Group {i+1}: {group['message_count']} messages")
        print(f"  Process ID: {group['process_id']}")
        print(f"  Time range: {group['start_timestamp']} to {group['end_timestamp']}")
        print()

if __name__ == "__main__":
    main()