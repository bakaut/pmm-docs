#!/usr/bin/env python3
"""
Test script for the extra arguments feature in template rendering.
"""

import os
import sys
import tempfile
import logging
import yaml

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def test_extra_args_template():
    """Test the extra arguments feature in template rendering."""
    print("Testing extra arguments in template rendering...")
    
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
        
        # Create a config file
        config_data = {
            "vars": {"title": "Test Title"},
            "files": {}
        }
        config_path = os.path.join(temp_dir, "test_config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        # Create a simple template that uses extra arguments
        template_text = "Title: {{ title }}\nCustom Key: {{ custom_key|default('') }}\nCustom Number: {{ custom_number|default('') }}"
        template_dir = os.path.join(temp_dir, "templates")
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, "test.j2")
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        # Test rendering with extra arguments using render_template_with_config
        extra_args = {
            "custom_key": "Custom Value",
            "custom_number": 42
        }
        rendered_with_extra = utils.render_template_with_config(config_path, template_path, extra_args)
        expected_with_extra = "Title: Test Title\nCustom Key: Custom Value\nCustom Number: 42"
        assert rendered_with_extra == expected_with_extra, f"Expected '{expected_with_extra}', got '{rendered_with_extra}'"
        
        # Test rendering with extra arguments using static render_template method
        # First copy the template to have the correct naming convention
        static_template_path = config_path.replace(".yaml", ".j2")
        with open(static_template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        rendered_static = Utils.render_template(config_path, extra_args)
        assert rendered_static == expected_with_extra, f"Expected '{expected_with_extra}', got '{rendered_static}'"
        
        print("All tests passed!")


if __name__ == "__main__":
    test_extra_args_template()
    print("Extra arguments template tests completed!")