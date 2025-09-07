"""
Import tests to verify that all required modules can be imported correctly.
"""

import pytest
import sys
from pathlib import Path

# Add flow directory to path
FLOW_DIR = Path(__file__).parent.parent / "flow"
sys.path.insert(0, str(FLOW_DIR))


def test_import_index():
    """Test that the main index module can be imported."""
    # Mock environment variables to avoid config validation errors
    import os
    os.environ["bot_token"] = "test_token"
    os.environ["database_url"] = "postgresql://test:test@localhost:5432/test"
    os.environ["operouter_key"] = "test_key"
    
    try:
        from flow.index import handler
        assert handler is not None
    except ImportError as e:
        pytest.fail(f"Failed to import flow.index: {e}")
    finally:
        # Clean up environment variables
        os.environ.pop("bot_token", None)
        os.environ.pop("database_url", None)
        os.environ.pop("operouter_key", None)


def test_import_telegram_bot():
    """Test that the Telegram bot module can be imported."""
    try:
        from flow.mindset.telegram_bot import TelegramBot
        assert TelegramBot is not None
    except ImportError as e:
        pytest.fail(f"Failed to import flow.mindset.telegram_bot: {e}")


def test_import_llm_manager():
    """Test that the LLM manager module can be imported."""
    try:
        from flow.mindset.llm_manager import LLMManager
        assert LLMManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import flow.mindset.llm_manager: {e}")


def test_import_config():
    """Test that the config module can be imported."""
    try:
        from flow.mindset.config import Config
        assert Config is not None
    except ImportError as e:
        pytest.fail(f"Failed to import flow.mindset.config: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])