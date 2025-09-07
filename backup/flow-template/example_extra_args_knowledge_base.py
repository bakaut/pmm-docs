#!/usr/bin/env python3
"""
Example showing how to use extra arguments with knowledge base templates.
"""

import os
import sys
import tempfile
import logging
import yaml
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def example_extra_args_knowledge_base():
    """Example of using extra arguments with knowledge base templates."""
    print("=== Example: Extra Arguments with Knowledge Base Templates ===")
    
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
    
    # Get the knowledge base directory
    kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_bases")
    kb_path = os.path.abspath(kb_path)
    
    # Check if the knowledge base directory exists
    if not os.path.exists(kb_path):
        print(f"Knowledge base directory not found: {kb_path}")
        return
    
    # Create a config file that references the knowledge base files
    config_data = {
        "vars": {
            "title": "ARCH Documentation with Extra Data",
            "show_userflow": True,
            "show_intents": True,
            "show_arch_intro": True
        },
        "files": {
            "arch_txt": os.path.join(kb_path, "templates", "arch.txt"),
            "classification_schema": os.path.join(kb_path, "templates", "json-schemas", "archClassificationResult.json"),
            "uncertain_schema": os.path.join(kb_path, "templates", "json-schemas", "archUncertainResult.json"),
            "user_flow_md": os.path.join(kb_path, "templates", "user_flow.md"),
            "state_json": os.path.join(kb_path, "templates", "state.json"),
            "analyze_dialog_txt": os.path.join(kb_path, "templates", "analyze_dialog.txt")
        }
    }
    
    # Create a temporary directory for the config and template
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save config as arch.yaml
        config_path = os.path.join(temp_dir, "arch.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        # Create a template that uses the knowledge base files and extra arguments
        template_text = """# {{ title }}

Generated on: {{ timestamp|default("Unknown date") }}
For user: {{ user_name|default("Anonymous") }}
Request ID: {{ request_id|default("N/A") }}

{% if show_arch_intro %}
> Architectural instructions (fragment):
>
> {{ read_file(files.arch_txt)[:200] }}...
{% endif %}

{% if show_userflow %}
## User Flow (mermaid from file)
{{ read_file(files.user_flow_md) }}
{% endif %}

{% if show_intents %}
## Intents (from state.json)
{% set st = load_json(files.state_json) %}
{% for key, desc in st.intents.items() %}
- **{{ key }}** — {{ desc }}
{% endfor %}
{% endif %}

## Schema Availability Check
- ClassificationResult.json: {{ 'OK' if file_exists(files.classification_schema) else 'missing' }}
- UncertainResult.json: {{ 'OK' if file_exists(files.uncertain_schema) else 'missing' }}

## Custom Data
Custom key: {{ custom_key|default("Not provided") }}
Custom number: {{ custom_number|default("Not provided") }}

## Example of Including Another File
<details><summary>analyze_dialog.txt (first 160 characters)</summary>

{{ read_file(files.analyze_dialog_txt)[:160] }}...

</details>
"""
        
        # Save template as arch.txt.j2
        template_dir = os.path.join(temp_dir, "templates")
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, "arch.txt.j2")
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
        
        # Define extra arguments to pass to the template
        extra_args = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": "John Doe",
            "request_id": "REQ-12345",
            "custom_key": "Custom Value",
            "custom_number": 42
        }
        
        # Render the template using the config and extra arguments
        print(f"Config file: {config_path}")
        print(f"Template file: {template_path}")
        
        rendered = utils.render_template_with_config(config_path, template_path, extra_args)
        
        print("\n--- Rendered Content (first 50 lines) ---")
        print("\n".join(rendered.splitlines()[:50]))
        
        # Also demonstrate the ARCH-specific function with extra arguments
        print("\n--- Using ARCH-specific function with extra args ---")
        arch_rendered = utils.render_arch_document(config_path, template_path, extra_args)
        print("\n".join(arch_rendered.splitlines()[:30]))
        
        return rendered


if __name__ == "__main__":
    content = example_extra_args_knowledge_base()
    print("\nKnowledge base template example with extra arguments completed successfully!")