"""
Dynamic template handler for knowledge bases using Jinja2.
This module provides functionality to render templates with dynamic content
from various knowledge base files.
"""

import os
import json
import yaml
import textwrap
import logging
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from .logger import get_default_logger

logger = get_default_logger(__name__, logging.DEBUG)


class TemplateHandler:
    """Handles dynamic template rendering with file inclusion and conditional logic."""

    def __init__(self, base_path: str = "/mnt/data"):
        """
        Initialize the template handler.
        
        Args:
            base_path: Base path for templates and files
        """
        self.base_path = base_path
        self.templates_dir = os.path.join(base_path, "templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            undefined=StrictUndefined,  # Fail if a variable is missing
            autoescape=False
        )
        
        # Register custom functions
        self.env.globals.update(
            read_file=self._read_file,
            load_json=self._load_json,
            file_exists=self._file_exists
        )

    def _read_file(self, path: str, default: str = "") -> str:
        """
        Read content from a file.
        
        Args:
            path: Path to the file
            default: Default value if file is not found
            
        Returns:
            Content of the file or default value
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {path}")
            return default
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return default

    def _load_json(self, path: str) -> Dict[str, Any]:
        """
        Load JSON from a file.
        
        Args:
            path: Path to the JSON file
            
        Returns:
            Parsed JSON data or empty dict on error
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON from {path}: {e}")
            return {}

    def _file_exists(self, path: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            path: Path to check
            
        Returns:
            True if file exists, False otherwise
        """
        return os.path.exists(path)

    def create_config(self, config_data: Dict[str, Any], config_path: Optional[str] = None) -> str:
        """
        Create a YAML configuration file.
        
        Args:
            config_data: Configuration data to write
            config_path: Path to save config (default: {base_path}/config.yml)
            
        Returns:
            Path to the created config file
        """
        if config_path is None:
            config_path = os.path.join(self.base_path, "config.yml")
            
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
            
        logger.info(f"Config saved to: {config_path}")
        return config_path

    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load a YAML configuration file.
        
        Args:
            config_path: Path to config file (default: {base_path}/config.yml)
            
        Returns:
            Configuration data
        """
        if config_path is None:
            config_path = os.path.join(self.base_path, "config.yml")
            
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return {}
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return {}

    def load_config_context(self, config_path: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file and return context for template rendering.
        
        Args:
            config_path: Path to config file
            
        Returns:
            Context dictionary for template rendering
        """
        cfg = self.load_config(config_path)
        ctx = (cfg.get("vars") or {})
        ctx["files"] = cfg.get("files") or {}
        return ctx

    def create_template(self, template_text: str, template_name: str = "main.md.j2") -> str:
        """
        Create a Jinja2 template file.
        
        Args:
            template_text: Template content
            template_name: Name of the template file
            
        Returns:
            Path to the created template file
        """
        template_path = os.path.join(self.templates_dir, template_name)
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(template_text)
            
        logger.info(f"Template saved to: {template_path}")
        return template_path

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.
        
        Args:
            template_name: Name of the template to render
            context: Context variables for the template
            
        Returns:
            Rendered template content
        """
        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**context)
            logger.info(f"Template {template_name} rendered successfully")
            return rendered
        except TemplateError as e:
            error_msg = f"Template rendering error: {e}"
            logger.error(error_msg)
            return f"[render error] {e}"
        except Exception as e:
            error_msg = f"Unexpected error during template rendering: {e}"
            logger.error(error_msg)
            return f"[render error] {e}"

    def save_output(self, content: str, output_path: Optional[str] = None) -> str:
        """
        Save rendered content to a file.
        
        Args:
            content: Content to save
            output_path: Path to save output (default: {base_path}/out.md)
            
        Returns:
            Path to the saved output file
        """
        if output_path is None:
            output_path = os.path.join(self.base_path, "out.md")
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"Output saved to: {output_path}")
        return output_path


def create_arch_template_handler(kb_path: str = "/Users/nlebedev@tempo.io/pers/poymoymir/flow/knowledge_bases", base_path: str = "/mnt/data") -> TemplateHandler:
    """
    Create a template handler specifically for ARCH templates.
    
    Args:
        kb_path: Path to knowledge bases directory
        base_path: Base path for templates and config
        
    Returns:
        Configured TemplateHandler instance
    """
    handler = TemplateHandler(base_path)
    
    # Create default config for ARCH templates in arch.yaml
    config_yaml = {
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
    
    config_path = handler.create_config(config_yaml, os.path.join(base_path, "arch.yaml"))
    
    # Create default ARCH template as arch.txt.j2
    template_text = textwrap.dedent("""\
        # {{ title }}

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
    """)
    
    handler.create_template(template_text, "arch.txt.j2")
    
    return handler


def render_template_with_config(config_path: str, template_path: str) -> str:
    """
    Render a template with the given configuration file.
    Universal function that can handle any template and config file.
    
    Args:
        config_path: Path to YAML configuration file
        template_path: Path to Jinja2 template file
        
    Returns:
        Rendered document content (not saved to file)
    """
    # Create a temporary handler with the directory of the template as base
    template_dir = os.path.dirname(template_path)
    handler = TemplateHandler(template_dir if template_dir else "/tmp")
    
    # Update environment to load template from the exact path
    handler.env = Environment(
        loader=FileSystemLoader(template_dir if template_dir else "."),
        undefined=StrictUndefined,
        autoescape=False
    )
    handler.env.globals.update(
        read_file=handler._read_file,
        load_json=handler._load_json,
        file_exists=handler._file_exists
    )
    
    # Load config from YAML file
    cfg = handler.load_config(config_path)
    
    ctx = (cfg.get("vars") or {})
    ctx["files"] = cfg.get("files") or {}
    
    # Extract template name from path
    template_name = os.path.basename(template_path)
    
    # Render template (without saving output)
    rendered = handler.render_template(template_name, ctx)
    
    return rendered

def render_arch_document(config_path: str = "/mnt/data/arch.yaml", template_path: str = "/mnt/data/templates/arch.txt.j2") -> str:
    """
    Render an ARCH template with the given configuration file.
    
    Args:
        config_path: Path to YAML configuration file (default: /mnt/data/arch.yaml)
        template_path: Path to Jinja2 template file (default: /mnt/data/templates/arch.txt.j2)
        
    Returns:
        Rendered document content (not saved to file)
    """
    return render_template_with_config(config_path, template_path)


# Example usage
if __name__ == "__main__":
    # This would typically be called from another module
    content = render_arch_document()
    print("Rendered to:", os.path.join("/mnt/data", "out.md"))
    print("--- Preview (first 40 lines) ---")
    print("\n".join(content.splitlines()[:40]))