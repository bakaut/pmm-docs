#!/usr/bin/env python3
"""
Example usage of the template handler with updated file names.
"""

import os
import sys
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.template_handler import TemplateHandler, create_arch_template_handler, render_arch_document


def example_basic_usage_with_files():
    """Example of basic template handler usage with separate config and template files."""
    print("=== Basic Template Handler Usage with Separate Files ===")
    
    # Create a temporary directory for this example
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize the template handler
        handler = TemplateHandler(temp_dir)
        
        # Create a simple config in a separate YAML file
        config_data = {
            "vars": {
                "title": "My Document",
                "show_section": True
            },
            "files": {
                "example_file": os.path.join(temp_dir, "example.txt")
            }
        }
        
        # Create an example file to include
        with open(config_data["files"]["example_file"], "w", encoding="utf-8") as f:
            f.write("This is content from an included file!")
        
        # Save the config as a separate YAML file
        config_path = handler.create_config(config_data, os.path.join(temp_dir, "my_config.yaml"))
        print(f"Config saved to: {config_path}")
        
        # Create a template as a separate file
        template_text = """# {{ title }}

{% if show_section %}
## Included Content
{{ read_file(files.example_file) }}
{% endif %}

## File Check
The example file {{ 'exists' if file_exists(files.example_file) else 'does not exist' }}.
"""
        
        # Save the template as a separate file
        template_path = handler.create_template(template_text, "my_template.j2")
        print(f"Template saved to: {template_path}")
        
        # Load the config from the YAML file
        cfg = handler.load_config(os.path.join(temp_dir, "my_config.yaml"))
        
        # Prepare context from the loaded config
        context = {
            "title": cfg["vars"]["title"],
            "show_section": cfg["vars"]["show_section"],
            "files": cfg["files"]
        }
        
        # Render the template (without saving output)
        rendered = handler.render_template("my_template.j2", context)
        
        print("\nRendered content:")
        print(rendered)
        print("\n" + "="*50 + "\n")


def example_arch_usage_with_files():
    """Example of ARCH-specific template usage with separate files."""
    print("=== ARCH Template Handler Usage with Separate Files ===")
    
    # Create a temporary directory for this example
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create ARCH template handler with custom file names
        handler = create_arch_template_handler(
            kb_path="/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases",
            base_path=temp_dir
        )
        
        # The create_arch_template_handler function has already created:
        # 1. arch.yaml - the configuration file
        # 2. arch.txt.j2 - the template file
        
        # Load the config from arch.yaml
        cfg = handler.load_config(os.path.join(temp_dir, "arch.yaml"))
        
        # Prepare context
        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}
        
        # Render the template from arch.txt.j2 (without saving output)
        rendered = handler.render_template("arch.txt.j2", ctx)
        
        print(f"Config loaded from: {os.path.join(temp_dir, 'arch.yaml')}")
        print(f"Template loaded from: {os.path.join(temp_dir, 'templates', 'arch.txt.j2')}")
        print("\nRendered content (first 20 lines):")
        print("\n".join(rendered.splitlines()[:20]))
        print("\n" + "="*50 + "\n")


def example_render_arch_document_function():
    """Example of using the convenience function to render an ARCH document."""
    print("=== Render ARCH Document Function ===")
    
    # Create a temporary directory for this example
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Render an ARCH document using the convenience function
            content = render_arch_document(
                kb_path="/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases",
                base_path=temp_dir
            )
            
            print("ARCH document rendered successfully!")
            print(f"Content length: {len(content)} characters")
            print("\nFirst 20 lines:")
            print("\n".join(content.splitlines()[:20]))
            
        except Exception as e:
            print(f"Could not render ARCH document: {e}")
    
    print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    example_basic_usage_with_files()
    example_arch_usage_with_files()
    example_render_arch_document_function()
    
    print("All examples with updated file names completed!")