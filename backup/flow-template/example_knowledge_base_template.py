#!/usr/bin/env python3
"""
Example showing how to use the template functionality with actual knowledge base files.
"""

import os
import sys
import tempfile
import logging
import yaml

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils


def example_knowledge_base_template():
    """Example of using the template functionality with knowledge base files."""
    print("=== Example: Knowledge Base Template Usage ===")
    
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
    kb_path = "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases"
    
    # Check if the knowledge base directory exists
    if not os.path.exists(kb_path):
        print(f"Knowledge base directory not found: {kb_path}")
        return
    
    # Create a config file that references the knowledge base files
    config_data = {
        "vars": {
            "title": "ARCH Documentation",
            "show_userflow": True,
            "show_intents": True,
            "show_arch_intro": True
        },
        "files": {
            "arch_txt": os.path.join(kb_path, "arch.txt"),
            "classification_schema": os.path.join(kb_path, "json-schemas", "archClassificationResult.json"),
            "uncertain_schema": os.path.join(kb_path, "json-schemas", "archUncertainResult.json"),
            "user_flow_md": os.path.join(kb_path, "user_flow.md"),
            "state_json": os.path.join(kb_path, "state.json"),
            "analyze_dialog_txt": os.path.join(kb_path, "analyze_dialog.txt")
        }
    }
    
    # Create a temporary directory for the config and template
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save config as arch.yaml
        config_path = os.path.join(temp_dir, "arch.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        
        # Create a template that uses the knowledge base files
        template_text = """# {{ title }}

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
        
        # Render the template using the config
        print(f"Config file: {config_path}")
        print(f"Template file: {template_path}")
        
        rendered = utils.render_template_with_config(config_path, template_path)
        
        print("\n--- Rendered Content (first 50 lines) ---")
        print("\n".join(rendered.splitlines()[:50]))
        
        # Also demonstrate the ARCH-specific function
        print("\n--- Using ARCH-specific function ---")
        arch_rendered = utils.render_arch_document(config_path, template_path)
        print("\n".join(arch_rendered.splitlines()[:30]))
        
        return rendered


if __name__ == "__main__":
    content = example_knowledge_base_template()
    print("\nKnowledge base template example completed successfully!")