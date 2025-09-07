#!/usr/bin/env python3
"""
Demo script showing how to use the universal template handler functions.
"""

import os
import sys
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.template_handler import (
    TemplateHandler, 
    render_template_with_config, 
    render_arch_document
)


def demo_universal_functions():
    """Demo the universal template handler functions."""
    print("=== Demo: Universal Template Handler Functions ===")
    
    # Create a temporary directory for this demo
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1) Create a config file (arch.yaml)
        handler = TemplateHandler(temp_dir)
        
        config_data = {
            "vars": {
                "title": "Universal Template Demo",
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
        config_path = handler.create_config(config_data, os.path.join(temp_dir, "arch.yaml"))
        
        # 2) Create a template file (arch.txt.j2)
        template_text = """# {{ title }}

{% if show_section %}
## Dynamic Content
Content from external file: {{ read_file(files.example_file) }}

File existence check: {{ 'File exists' if file_exists(files.example_file) else 'File missing' }}
{% endif %}

## Configuration Data
This template was rendered using a universal function that can handle any 
template and configuration file combination.
"""
        
        # Save template as arch.txt.j2
        template_path = handler.create_template(template_text, "arch.txt.j2")
        full_template_path = os.path.join(temp_dir, "templates", "arch.txt.j2")
        
        # 3) Use the universal function to render the template
        print(f"Config file: {config_path}")
        print(f"Template file: {full_template_path}")
        
        # Render using the universal function
        rendered = render_template_with_config(config_path, full_template_path)
        
        print("\n--- Rendered Content ---")
        print(rendered)
        
        # 4) Use the ARCH-specific function
        print("\n--- Using ARCH-specific function ---")
        arch_rendered = render_arch_document(config_path, full_template_path)
        print(arch_rendered)
        
        return rendered


if __name__ == "__main__":
    content = demo_universal_functions()
    print("\nDemo with universal functions completed successfully!")