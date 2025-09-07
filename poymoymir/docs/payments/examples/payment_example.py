"""
Example script demonstrating how to use the payment functionality.

This script shows how to send a locked audio message that users can unlock with Telegram Stars.
"""

import sys
import os

# Add the parent directory to the path so we can import the mindset modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.config import Config
from mindset.telegram_bot import TelegramBot
from mindset.database import DatabaseManager


def send_locked_audio_example():
    """
    Example of sending a locked audio message.
    """
    # Load configuration
    config = Config.from_env()
    
    # Initialize Telegram bot
    telegram_bot = TelegramBot(config)
    
    # Initialize database
    db = DatabaseManager(config)
    
    # Chat ID to send the message to (this would typically come from the user interaction)
    chat_id = 123456789  # Replace with actual chat ID
    
    # Send locked audio message
    message_id = telegram_bot.send_locked_audio_message(
        chat_id, 
        "🔒 Эксклюзивный аудиотрек, отправьте 10 звезд, чтобы открыть его."
    )
    
    if message_id:
        print(f"Locked audio message sent successfully with message ID: {message_id}")
        
        # Create payment record in database
        # In a real implementation, you would store the actual audio file path
        success = db.create_payment_record(
            chat_id=chat_id,
            message_id=message_id,
            invoice_payload=f"unlock_audio_{message_id}",
            amount_stars=10,
            audio_path="/path/to/exclusive_audio.mp3",  # Replace with actual path
            user_id="user-uuid-here",  # Replace with actual user UUID
            payer_user_id=chat_id
        )
        
        if success:
            print("Payment record created successfully")
        else:
            print("Failed to create payment record")
    else:
        print("Failed to send locked audio message")


if __name__ == "__main__":
    send_locked_audio_example()