"""
Telegraph integration module

Provides a TelegraphManager class that encapsulates all Telegraph API interactions.
"""

import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Union
import requests
from requests import HTTPError

# Use absolute imports
try:
    from mindset.config import Config
    from mindset.logger import get_default_logger
except ImportError:
    # Fallback for direct execution
    from config import Config
    from logger import get_default_logger


class TelegraphManager:
    """
    Telegraph Manager class that handles all Telegraph API interactions.
    """

    def __init__(self, config: Config):
        """
        Initialize TelegraphManager with configuration.

        Args:
            config: Config object containing telegraph settings
        """
        self.config = config
        self.timeout = (config.connect_timeout, config.read_timeout)

        # Setup logger
        self.logger = get_default_logger('telegraph')

        # Setup HTTP session
        self.session = requests.Session()

        # Telegraph API base URL
        self.api_base_url = "https://api.telegra.ph"

        self.logger.debug("TelegraphManager initialized")

    def _generate_page_slug(self, tg_id: int, chat_id: int) -> str:
        """
        Generate a unique page slug based on Telegram user ID and chat ID.

        Args:
            tg_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: MD5 hash of tg_id + chat_id
        """
        combined = f"{tg_id}{chat_id}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def format_content(self, content: Union[str, List[Dict]]) -> List[Dict]:
        """
        Format content for Telegraph API.

        Args:
            content: Content as string or list of nodes

        Returns:
            List of formatted nodes
        """
        if isinstance(content, str):
            # Simple string content - wrap in paragraph
            return [{"tag": "p", "children": [content]}]
        elif isinstance(content, list):
            # Already formatted content
            return content
        else:
            # Convert to string and wrap
            return [{"tag": "p", "children": [str(content)]}]

    def create_page(self, tg_id: int, chat_id: int, title: str = "Меню пользователя",
                   content: Union[str, List[Dict]] = "", return_content: bool = True) -> Optional[Dict[str, Any]]:
        """
        Create a new Telegraph page for a user.

        Args:
            tg_id: Telegram user ID
            chat_id: Telegram chat ID
            title: Page title
            content: Page content in HTML format or as Telegraph nodes
            return_content: Whether to return content in response

        Returns:
            Dict with page information or None if failed
        """
        url = f"{self.api_base_url}/createPage"

        # Format content for Telegraph API
        formatted_content = self.format_content(content)

        payload = {
            "title": title,
            "content": formatted_content,
            "return_content": return_content,
            "author_name": self.config.telegraph_author_name,
            "author_url": f"https://t.me/{self.config.telegraph_bot_username}" if self.config.telegraph_bot_username else "https://t.me/PoyMoyMirBot"
        }

        # Add API key if available
        if self.config.telegraph_api_key:
            payload["access_token"] = self.config.telegraph_api_key

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                page_data = result.get("result", {})
                self.logger.debug("Telegraph page created successfully: %s", page_data.get("path"))
                return page_data
            else:
                self.logger.error("Failed to create Telegraph page: %s", result.get("error"))
                return None

        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("HTTP error while creating Telegraph page: %s | response=%s", e, resp_text)
            return None
        except Exception as e:
            self.logger.error("Exception while creating Telegraph page: %s", e)
            return None

    def edit_page(self, page_path: str, title: str = None, content: Union[str, List[Dict]] = None,
                 return_content: bool = True) -> Optional[Dict[str, Any]]:
        """
        Edit an existing Telegraph page.

        Args:
            page_path: Path to the page (from page URL)
            title: New page title (optional)
            content: New page content in HTML format or as Telegraph nodes (optional)
            return_content: Whether to return content in response

        Returns:
            Dict with updated page information or None if failed
        """
        url = f"{self.api_base_url}/editPage"

        payload = {
            "path": page_path,
            "return_content": return_content
        }

        if title:
            payload["title"] = title

        if content:
            payload["content"] = self.format_content(content)

        # Add API key if available
        if self.config.telegraph_api_key:
            payload["access_token"] = self.config.telegraph_api_key

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                page_data = result.get("result", {})
                self.logger.debug("Telegraph page edited successfully: %s", page_data.get("path"))
                return page_data
            else:
                self.logger.error("Failed to edit Telegraph page: %s", result.get("error"))
                return None

        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("HTTP error while editing Telegraph page: %s | response=%s", e, resp_text)
            return None
        except Exception as e:
            self.logger.error("Exception while editing Telegraph page: %s", e)
            return None

    def get_page(self, page_path: str, return_content: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get information about a Telegraph page.

        Args:
            page_path: Path to the page (from page URL)
            return_content: Whether to return content in response

        Returns:
            Dict with page information or None if failed
        """
        url = f"{self.api_base_url}/getPage"

        params = {
            "path": page_path,
            "return_content": return_content
        }

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                page_data = result.get("result", {})
                self.logger.debug("Telegraph page retrieved successfully: %s", page_data.get("path"))
                return page_data
            else:
                self.logger.error("Failed to get Telegraph page: %s", result.get("error"))
                return None

        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("HTTP error while getting Telegraph page: %s | response=%s", e, resp_text)
            return None
        except Exception as e:
            self.logger.error("Exception while getting Telegraph page: %s", e)
            return None

    def get_page_list(self, offset: int = 0, limit: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get a list of pages belonging to a Telegraph account.

        Args:
            offset: Sequential number of the first page to be returned
            limit: Limits the number of pages to be retrieved (0-200)

        Returns:
            Dict with pages list or None if failed
        """
        url = f"{self.api_base_url}/getPageList"

        params = {
            "offset": offset,
            "limit": min(limit, 20)  # API limit is 200
        }

        # Add API key if available
        if self.config.telegraph_api_key:
            params["access_token"] = self.config.telegraph_api_key

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                pages_data = result.get("result", {})
                self.logger.debug("Telegraph pages list retrieved successfully")
                return pages_data
            else:
                self.logger.error("Failed to get Telegraph pages list: %s", result.get("error"))
                return None

        except HTTPError as e:
            resp_text = getattr(getattr(e, "response", None), "text", "")
            self.logger.error("HTTP error while getting Telegraph pages list: %s | response=%s", e, resp_text)
            return None
        except Exception as e:
            self.logger.error("Exception while getting Telegraph pages list: %s", e)
            return None
