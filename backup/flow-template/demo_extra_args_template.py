#!/usr/bin/env python3
"""
Demo script showing how to use the extra arguments feature in template rendering.
"""

import os
import sys
import tempfile
import logging
import yaml

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def demo_extra_args_template():
    """Demo the extra arguments feature in template rendering."""
    print("=== Demo: Extra Arguments in Template Rendering ===")
    
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
    
    # Create a temporary directory for this demo
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1) Create a config file
        config_data = {
            "vars": {
                "title": "Extra Args Demo",
                "show_section": True
            },
            "files": {
                "example_file": os.path.join(temp_dir, "example.txt")
            }
        }
        
        # Create an example file to include
        with open(config_data["files"]["example_file"], "w", encoding="utf-8") as f:
            f.write("This content is loaded from an external file!")
        
        # Save config as config.yaml
        config_path = os.path.join(temp_dir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        # 2) Create a template file that uses both config vars and extra args
        template_text = """# {{ title }}

{% if show_section %}
## Dynamic Content
Content from external file: {{ read_file(files.example_file) }}

File existence check: {{ 'File exists' if file_exists(files.example_file) else 'File missing' }}

Extra argument 'custom_key': {{ custom_key }}
Extra argument 'custom_number': {{ custom_number }}
Extra argument 'custom_list': {{ custom_list }}
{% endif %}

## Configuration Data
This template was rendered using the Utils class with extra arguments.
"""
        
        # Save template
        template_dir = os.path.join(temp_dir, "templates")
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, "demo.j2")
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        # 3) Use the template functionality with extra arguments
        print(f"Config file: {config_path}")
        print(f"Template file: {template_path}")
        
        # Define extra arguments to pass to the template
        extra_args = {
            "custom_key": "Custom Value",
            "custom_number": 42,
            "custom_list": ["item1", "item2", "item3"]
        }
        
        # Render using the universal function with extra args
        rendered = utils.render_template_with_config(config_path, template_path, extra_args)
        
        print("\n--- Rendered Content ---")
        print(rendered)
        
        # 4) Use the ARCH-specific function with extra arguments
        print("\n--- Using ARCH-specific function with extra args ---")
        arch_rendered = utils.render_arch_document(config_path, template_path, extra_args)
        print(arch_rendered)
        
        return rendered


if __name__ == "__main__":
    content = demo_extra_args_template()
    print("\nDemo with extra arguments completed successfully!")