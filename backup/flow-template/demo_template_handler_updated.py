#!/usr/bin/env python3
"""
Demo script showing how to use the template handler with the updated file names.
"""

import os
import sys
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mindset.template_handler import TemplateHandler


def demo_updated_file_names():
    """Demo the template handler with updated file names."""
    print("=== Demo: Updated File Names ===")
    
    # Create a temporary directory for this demo
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1) Create a tiny YAML DSL config in arch.yaml
        handler = TemplateHandler(temp_dir)
        
        config_yaml = {
            "vars": {
                "title": "ARCH mini-demo from files",
                "show_userflow": True,
                "show_intents": True,
                "show_arch_intro": True
            },
            "files": {
                "arch_txt": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/arch.txt",
                "classification_schema": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/json-schemas/archClassificationResult.json",
                "uncertain_schema": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/json-schemas/archUncertainResult.json",
                "user_flow_md": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/user_flow.md",
                "state_json": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/state.json",
                "analyze_dialog_txt": "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases/analyze_dialog.txt"
            }
        }
        
        # Save config as arch.yaml
        config_path = handler.create_config(config_yaml, os.path.join(temp_dir, "arch.yaml"))
        
        # 2) Write a minimal Jinja2 template as arch.txt.j2
        template_text = """# {{ title }}

{% if show_arch_intro %}
> Архитектурные указания (фрагмент):
>
> {{ read_file(files.arch_txt)[:200] }}...
{% endif %}

{% if show_userflow %}
## User Flow (mermaid из файла)
{{ read_file(files.user_flow_md) }}
{% endif %}

{% if show_intents %}
## Intents (из state.json)
{% set st = load_json(files.state_json) %}
{% for key, desc in st.intents.items() %}
- **{{ key }}** — {{ desc }}
{% endfor %}
{% endif %}

## Проверка наличия схем
- ClassificationResult.json: {{ 'OK' if file_exists(files.classification_schema) else 'missing' }}
- UncertainResult.json: {{ 'OK' if file_exists(files.uncertain_schema) else 'missing' }}

## Пример подстановки содержимого другого файла
<details><summary>analyze_dialog.txt (первые 160 символов)</summary>

{{ read_file(files.analyze_dialog_txt)[:160] }}...

</details>"""
        
        # Save template as arch.txt.j2
        tpl_path = handler.create_template(template_text, "arch.txt.j2")
        
        # 3) Load config from arch.yaml and render
        cfg = handler.load_config(os.path.join(temp_dir, "arch.yaml"))
        
        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}
        
        # Render template from arch.txt.j2 (without saving output)
        rendered = handler.render_template("arch.txt.j2", ctx)
        
        print(f"Config saved to: {config_path}")
        print(f"Template saved to: {tpl_path}")
        print("--- Preview (first 20 lines) ---")
        print("\n".join(rendered.splitlines()[:20]))
        
        return rendered


if __name__ == "__main__":
    content = demo_updated_file_names()
    print("\nDemo with updated file names completed successfully!")