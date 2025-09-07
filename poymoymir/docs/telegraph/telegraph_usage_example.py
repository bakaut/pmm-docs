"""
Comprehensive example of Telegraph integration usage
"""

import json
from typing import Dict, Any, List

# Local imports (assuming this is run from the project root)
try:
    from .config import Config
    from .database import DatabaseManager
    from .telegraph import TelegraphManager
    from .telegram_bot import TelegramBot
except ImportError:
    from config import Config
    from database import DatabaseManager
    from telegraph import TelegraphManager
    from telegram_bot import TelegramBot


class TelegraphPageBuilder:
    """Helper class to build Telegraph page content"""

    @staticmethod
    def create_menu_page(user_name: str, options: List[Dict[str, str]]) -> List[Dict]:
        """
        Create a menu page with user name and options.

        Args:
            user_name: Name of the user
            options: List of menu options with 'text' and 'link' keys

        Returns:
            Formatted content for Telegraph page
        """
        content = [
            {"tag": "h2", "children": [f"Привет, {user_name}!"]},
            {"tag": "p", "children": ["Это ваше персональное меню."]},
            {"tag": "h3", "children": ["Доступные опции:"]}
        ]

        # Add menu options as a list
        list_items = []
        for option in options:
            list_items.append({
                "tag": "li",
                "children": [
                    {"tag": "a", "attrs": {"href": option["link"]}, "children": [option["text"]]}
                ]
            })

        content.append({"tag": "ul", "children": list_items})
        content.append({"tag": "p", "children": ["Страница обновлена: " + "сегодня"]})

        return content

    @staticmethod
    def create_history_page(user_name: str, history_items: List[str]) -> List[Dict]:
        """
        Create a history page with user conversation history.

        Args:
            user_name: Name of the user
            history_items: List of history items

        Returns:
            Formatted content for Telegraph page
        """
        content = [
            {"tag": "h2", "children": [f"История разговоров, {user_name}"]},
            {"tag": "p", "children": ["Здесь хранится история ваших разговоров."]},
            {"tag": "h3", "children": ["Последние записи:"]}
        ]

        # Add history items
        for item in history_items:
            content.append({"tag": "p", "children": [item]})

        content.append({"tag": "p", "children": ["Страница обновлена: " + "сегодня"]})

        return content


def integrate_telegraph_with_user(db: DatabaseManager, telegraph: TelegraphManager,
                                bot: TelegramBot, tg_user_id: int, chat_id: int,
                                user_name: str) -> str:
    """
    Complete integration example: create or update a user's Telegraph page with a menu.

    Args:
        db: Database manager instance
        telegraph: Telegraph manager instance
        bot: Telegram bot instance
        tg_user_id: Telegram user ID
        chat_id: Chat ID
        user_name: User's name

    Returns:
        URL of the created/updated page
    """
    # Define menu options
    menu_options = [
        {"text": "Мои разговоры", "link": "https://example.com/history"},
        {"text": "Настройки", "link": "https://example.com/settings"},
        {"text": "Помощь", "link": "https://example.com/help"},
        {"text": "Обратная связь", "link": "https://example.com/feedback"}
    ]

    # Create page content
    page_content = TelegraphPageBuilder.create_menu_page(user_name, menu_options)

    # Create or update the user's Telegraph page
    page_url = bot.create_or_update_user_telegraph_page(
        db=db,
        telegraph_manager=telegraph,
        tg_user_id=tg_user_id,
        chat_id=chat_id,
        page_content=json.dumps(page_content)  # Convert to JSON string for storage
    )

    return page_url


def update_user_history_page(db: DatabaseManager, telegraph: TelegraphManager,
                           tg_user_id: int, chat_id: int, user_name: str,
                           history_items: List[str]) -> str:
    """
    Update a user's history page.

    Args:
        db: Database manager instance
        telegraph: Telegraph manager instance
        tg_user_id: Telegram user ID
        chat_id: Chat ID
        user_name: User's name
        history_items: List of history items

    Returns:
        URL of the updated page
    """
    # Get user UUID
    user_record = db.query_one("SELECT id FROM users WHERE chat_id = %s LIMIT 1", (tg_user_id,))
    if not user_record:
        raise ValueError(f"User not found for tg_user_id: {tg_user_id}")

    user_uuid = user_record["id"]

    # Get existing page info
    page_record = db.get_telegraph_page_by_user(user_uuid, chat_id)
    if not page_record or not page_record.get("page_id"):
        raise ValueError("Telegraph page not found for user")

    # Create history page content
    page_content = TelegraphPageBuilder.create_history_page(user_name, history_items)

    # Update the page
    page_data = telegraph.edit_page(
        page_path=page_record["page_id"],
        title=f"История разговоров {user_name}",
        content=page_content
    )

    if page_data:
        page_path = page_data.get("path")
        page_url = f"https://telegra.ph/{page_path}"

        # Update database with new content
        db.update_telegraph_page_content(user_uuid, chat_id, json.dumps(page_content), None)

        return page_url
    else:
        raise RuntimeError("Failed to update Telegraph page")


# Example usage
if __name__ == "__main__":
    # Note: This example assumes you have proper environment variables set
    # and a working database connection

    try:
        # Initialize components
        config = Config.from_env()
        db = DatabaseManager(config)
        telegraph = TelegraphManager(config)
        bot = TelegramBot(config)

        # Example user data
        tg_user_id = 123456789
        chat_id = 987654321
        user_name = "Александр"

        # Create or update menu page
        menu_page_url = integrate_telegraph_with_user(
            db=db,
            telegraph=telegraph,
            bot=bot,
            tg_user_id=tg_user_id,
            chat_id=chat_id,
            user_name=user_name
        )

        print(f"Menu page created/updated: {menu_page_url}")

        # Update history page
        history_items = [
            "Разговор о музыке - 1 сентября 2025",
            "Обсуждение поэзии - 31 августа 2025",
            "Философский диалог - 25 августа 2025"
        ]

        history_page_url = update_user_history_page(
            db=db,
            telegraph=telegraph,
            tg_user_id=tg_user_id,
            chat_id=chat_id,
            user_name=user_name,
            history_items=history_items
        )

        print(f"History page updated: {history_page_url}")

    except Exception as e:
        print(f"Error in example: {e}")
