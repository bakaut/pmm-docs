#!/usr/bin/env python3
"""
Demo script showing how to use the template functionality in the Utils class.
"""

import os
import sys
import tempfile
import logging

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils
from mindset.config import Config


def demo_utils_template():
    """Demo the template functionality in the Utils class."""
    print("=== Demo: Template Functionality in Utils Class ===")
    
    # Create a temporary directory for this demo
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
        
        # 1) Create a config file (arch.yaml)
        config_data = {
            "vars": {
                "title": "Utils Template Demo",
                "show_section": True
            },
            "files": {
                "example_file": os.path.join(temp_dir, "example.txt")
            }
        }
        
        # Create an example file to include
        with open(config_data["files"]["example_file"], "w", encoding="utf-8") as f:
            f.write("This content is loaded from an external file!")
        
        # Save config as arch.yaml
        config_path = os.path.join(temp_dir, "arch.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        # 2) Create a template file (arch.txt.j2)
        template_text = """# {{ title }}

{% if show_section %}
## Dynamic Content
Content from external file: {{ read_file(files.example_file) }}

File existence check: {{ 'File exists' if file_exists(files.example_file) else 'File missing' }}
{% endif %}

## Configuration Data
This template was rendered using the Utils class template functionality.
"""
        
        # Save template as arch.txt.j2
        template_dir = os.path.join(temp_dir, "templates")
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, "arch.txt.j2")
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        # 3) Use the template functionality from Utils class
        print(f"Config file: {config_path}")
        print(f"Template file: {template_path}")
        
        # Render using the universal function
        rendered = utils.render_template_with_config(config_path, template_path)
        
        print("\n--- Rendered Content ---")
        print(rendered)
        
        # 4) Use the ARCH-specific function
        print("\n--- Using ARCH-specific function ---")
        arch_rendered = utils.render_arch_document(config_path, template_path)
        print(arch_rendered)
        
        return rendered


if __name__ == "__main__":
    content = demo_utils_template()
    print("\nDemo with Utils template functionality completed successfully!")