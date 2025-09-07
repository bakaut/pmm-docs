#!/usr/bin/env python3
"""
Test script for the template functionality in the Utils class.
"""

import os
import sys
import tempfile
import logging
import yaml

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def test_utils_template():
    """Test the template functionality in the Utils class."""
    print("Testing Utils template functionality...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a minimal config-like object for testing
        class SimpleConfig:
            def __init__(self):
                self.retry_total = 3
                self.retry_backoff_factor = 2
                self.enable_conversation_reset = True
                self.system_prompt = "Test system prompt"
        
        config = SimpleConfig()
        
        # Create Utils instance
        utils = Utils(config, logging.getLogger(__name__))
        
        # Test file reading function
        test_file_path = os.path.join(temp_dir, "test.txt")
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write("Hello, World!")
        
        content = utils._read_file(test_file_path)
        assert content == "Hello, World!", f"Expected 'Hello, World!', got '{content}'"
        
        # Test file exists function
        assert utils._file_exists(test_file_path) == True
        assert utils._file_exists(os.path.join(temp_dir, "nonexistent.txt")) == False
        
        # Test JSON loading function
        json_file_path = os.path.join(temp_dir, "test.json")
        with open(json_file_path, "w", encoding="utf-8") as f:
            f.write('{"key": "value"}')
        
        json_data = utils._load_json(json_file_path)
        assert json_data == {"key": "value"}, f"Expected {{'key': 'value'}}, got {json_data}"
        
        # Test config loading function
        config_data = {
            "vars": {"title": "Test Title"},
            "files": {"test_file": test_file_path}
        }
        config_path = os.path.join(temp_dir, "test_config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        loaded_config = utils.load_config(config_path)
        assert loaded_config == config_data, f"Expected {config_data}, got {loaded_config}"
        
        # Test config context loading function
        context = utils.load_config_context(config_path)
        expected_context = {"title": "Test Title", "files": {"test_file": test_file_path}}
        assert context == expected_context, f"Expected {expected_context}, got {context}"
        
        # Test template rendering with config
        template_text = "Title: {{ title }}\nContent: {{ read_file(files.test_file) }}"
        template_dir = os.path.join(temp_dir, "templates")
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, "test.j2")
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        rendered = utils.render_template_with_config(config_path, template_path)
        expected = "Title: Test Title\nContent: Hello, World!"
        assert rendered == expected, f"Expected '{expected}', got '{rendered}'"
        
        print("All tests passed!")


if __name__ == "__main__":
    test_utils_template()
    print("Utils template functionality tests completed!")