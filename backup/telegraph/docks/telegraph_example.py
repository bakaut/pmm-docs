"""
Example usage of Telegraph integration
"""

from .config import Config
from .database import DatabaseManager
from .telegraph import TelegraphManager
from .telegram_bot import TelegramBot


def example_telegraph_usage():
    """
    Example of how to use the Telegraph integration
    """
    # Initialize components
    config = Config.from_env()
    db = DatabaseManager(config)
    telegraph = TelegraphManager(config)
    bot = TelegramBot(config)

    # Example user data
    tg_user_id = 123456789  # Example Telegram user ID
    chat_id = 987654321     # Example chat ID

    # Example page content (HTML format as required by Telegraph API)
    page_content = [
        {"tag": "p", "children": ["Welcome to your personal menu!"]},
        {"tag": "h3", "children": ["Your Options"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": ["Option 1: View your history"]},
            {"tag": "li", "children": ["Option 2: Settings"]},
            {"tag": "li", "children": ["Option 3: Help"]}
        ]},
        {"tag": "p", "children": ["Last updated: Today"]}
    ]

    # Create or update user's Telegraph page
    page_url = bot.create_or_update_user_telegraph_page(
        db=db,
        telegraph_manager=telegraph,
        tg_user_id=tg_user_id,
        chat_id=chat_id,
        page_content=str(page_content)  # In a real implementation, this would be properly formatted
    )

    if page_url:
        print(f"Successfully created/updated Telegraph page: {page_url}")
        return page_url
    else:
        print("Failed to create/update Telegraph page")
        return None


if __name__ == "__main__":
    example_telegraph_usage()
