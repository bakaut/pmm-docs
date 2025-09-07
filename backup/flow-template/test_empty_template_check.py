#!/usr/bin/env python3
"""
Test script to verify that empty template checking works correctly.
"""

import os
import sys
import tempfile
import yaml

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def test_empty_template_check():
    """Test that empty template checking works correctly."""
    print("Testing empty template check...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an empty template file
        empty_template_path = os.path.join(temp_dir, "empty.j2")
        with open(empty_template_path, "w", encoding="utf-8") as f:
            f.write("")  # Empty template
        
        # Create a config file for the empty template
        empty_config_data = {
            "vars": {"title": "Empty Template Test"},
            "files": {}
        }
        empty_config_path = os.path.join(temp_dir, "empty.yaml")
        with open(empty_config_path, "w", encoding="utf-8") as f:
            yaml.dump(empty_config_data, f, allow_unicode=True, sort_keys=False)
        
        # Test that rendering an empty template raises ValueError
        try:
            result = Utils.render_template(empty_config_path)
            assert False, "Expected ValueError for empty template, but got result: " + result
        except ValueError as e:
            assert "Rendered template is empty" in str(e)
            print("✓ Empty template correctly raised ValueError:", str(e))
        
        # Create a template with only whitespace
        whitespace_template_path = os.path.join(temp_dir, "whitespace.j2")
        with open(whitespace_template_path, "w", encoding="utf-8") as f:
            f.write("   \n\t\n  ")  # Only whitespace
        
        # Create a config file for the whitespace template
        whitespace_config_data = {
            "vars": {"title": "Whitespace Template Test"},
            "files": {}
        }
        whitespace_config_path = os.path.join(temp_dir, "whitespace.yaml")
        with open(whitespace_config_path, "w", encoding="utf-8") as f:
            yaml.dump(whitespace_config_data, f, allow_unicode=True, sort_keys=False)
        
        # Test that rendering a whitespace-only template raises ValueError
        try:
            result = Utils.render_template(whitespace_config_path)
            assert False, "Expected ValueError for whitespace-only template, but got result: " + result
        except ValueError as e:
            assert "Rendered template is empty" in str(e)
            print("✓ Whitespace-only template correctly raised ValueError:", str(e))
        
        # Create a valid template file
        valid_template_path = os.path.join(temp_dir, "valid.j2")
        with open(valid_template_path, "w", encoding="utf-8") as f:
            f.write("Valid template content: {{ title }}")
        
        # Create a config file for the valid template
        valid_config_data = {
            "vars": {"title": "Valid Template Test"},
            "files": {}
        }
        valid_config_path = os.path.join(temp_dir, "valid.yaml")
        with open(valid_config_path, "w", encoding="utf-8") as f:
            yaml.dump(valid_config_data, f, allow_unicode=True, sort_keys=False)
        
        # Test that rendering a valid template works correctly
        result = Utils.render_template(valid_config_path)
        expected = "Valid template content: Valid Template Test"
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print("✓ Valid template rendered correctly:", result[:50] + "..." if len(result) > 50 else result)
        
        print("All empty template checks passed!")


if __name__ == "__main__":
    test_empty_template_check()
    print("Empty template check tests completed!")