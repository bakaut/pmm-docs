# Template Functionality in Utils Class

## Overview

The template functionality has been successfully integrated into the Utils class, eliminating the need for a separate TemplateHandler class. This implementation provides a robust and flexible system for rendering templates with dynamic content from various knowledge base files.

## Key Features

### Template Functions in Utils Class

1. **`render_template_with_config()`** - Universal function that can render any template with any configuration file
2. **`render_arch_document()`** - Convenience function for ARCH documents with default file paths
3. **Extra Arguments Support** - Pass additional key-value pairs to templates
3. **`load_config()`** - Function to load YAML configuration files
4. **`load_config_context()`** - Helper function to load configuration and prepare context for templates
5. **Private helper functions**:
   - `_read_file()` - Read content from files
   - `_load_json()` - Load JSON data from files
   - `_file_exists()` - Check if a file exists

### No File Creation
- Functions only read existing files
- No automatic file creation in code
- Results returned as variables, not saved to file system

### Flexible File Handling
- Can work with any YAML configuration file
- Can work with any Jinja2 template file
- Supports custom file paths for both config and template

## Implementation Details

### Dependencies
The implementation requires the following dependencies which are already included in the project:
- `jinja2` - Template engine
- `PyYAML` - YAML parsing
- Standard library modules: `os`, `json`, `textwrap`, `logging`

### Methods Added to Utils Class

#### `render_template_with_config(config_path: str, template_path: str, extra_args: Optional[Dict[str, Any]] = None) -> str`
Universal function that can handle any template and configuration file combination. Supports optional extra arguments that will be passed to the template context.

#### `render_arch_document(config_path: str = "/mnt/data/arch.yaml", template_path: str = "/mnt/data/templates/arch.txt.j2", extra_args: Optional[Dict[str, Any]] = None) -> str`
ARCH-specific convenience function with default file paths. Supports optional extra arguments that will be passed to the template context.

#### `load_config(config_path: str) -> Dict[str, Any]`
Load a YAML configuration file.

#### `load_config_context(config_path: str) -> Dict[str, Any]`
Load a YAML configuration file and return context for template rendering.

#### Private Helper Methods
- `_read_file(path: str, default: str = "") -> str`
- `_load_json(path: str) -> Dict[str, Any]`
- `_file_exists(path: str) -> bool`

## Usage Examples

### Basic Usage
```python
from mindset.utils import Utils

# Create a config-like object (simplified for this example)
class SimpleConfig:
    def __init__(self):
        self.retry_total = 3
        self.retry_backoff_factor = 2
        self.enable_conversation_reset = True
        self.system_prompt = "Test system prompt"

config = SimpleConfig()
utils = Utils(config)

# Render any template with any configuration file
content = utils.render_template_with_config(
    config_path="/path/to/your-config.yaml",
    template_path="/path/to/your-template.j2"
)

# Render with extra arguments
extra_args = {
    "custom_key": "Custom Value",
    "custom_number": 42,
    "custom_list": ["item1", "item2", "item3"]
}
content = utils.render_template_with_config(
    config_path="/path/to/your-config.yaml",
    template_path="/path/to/your-template.j2",
    extra_args=extra_args
)
```

### ARCH-Specific Usage
```python
from mindset.utils import Utils

# Create Utils instance with proper config
utils = Utils(config)

# Render ARCH template with configuration
content = utils.render_arch_document(
    config_path="/path/to/arch.yaml",
    template_path="/path/to/arch.txt.j2"
)

# Render ARCH template with configuration and extra arguments
extra_args = {
    "custom_key": "Custom Value",
    "timestamp": "2023-01-01 12:00:00",
    "user_name": "John Doe"
}
content = utils.render_arch_document(
    config_path="/path/to/arch.yaml",
    template_path="/path/to/arch.txt.j2",
    extra_args=extra_args
)
```

### Manual Approach
```python
from mindset.utils import Utils

# Create Utils instance
utils = Utils(config)

# Load config and prepare context
context = utils.load_config_context("/path/to/config.yaml")

# Note: For manual rendering, you would need to create a Jinja2 environment
# This is handled automatically in the render_template_with_config method
```

## Template Example

A typical template might look like this:
```jinja2
# {{ title }}

Generated on: {{ timestamp|default("Unknown date") }}
For user: {{ user_name|default("Anonymous") }}

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

Custom data: {{ custom_key|default("Not provided") }}
```

With a corresponding YAML configuration file:
```yaml
vars:
  title: "ARCH Documentation"
  show_userflow: true
  show_intents: true
  show_arch_intro: true
files:
  arch_txt: "/path/to/flow/knowledge_bases/arch.txt"
  user_flow_md: "/path/to/flow/knowledge_bases/user_flow.md"
  state_json: "/path/to/flow/knowledge_bases/state.json"
```

And extra arguments passed at runtime:
```python
extra_args = {
    "timestamp": "2023-01-01 12:00:00",
    "user_name": "John Doe",
    "custom_key": "Custom Value"
}
```

## Benefits

1. **Integration**: Template functionality is now part of the existing Utils class
2. **Simplicity**: No need to manage a separate TemplateHandler class
3. **Universality**: Works with any template and configuration file combination
4. **No Side Effects**: No automatic file creation or saving
5. **Flexibility**: Supports custom file paths
6. **Compatibility**: Maintains backward compatibility with existing code
7. **Control**: Results returned as variables for further processing

## Testing

The implementation has been tested with:
- Universal function with various template/config combinations
- ARCH-specific function with default file paths
- File reading and JSON loading functions
- Config loading and context preparation
- Integration with actual knowledge base files

## Integration

The template functionality integrates seamlessly with the existing Utils class:
1. **No Breaking Changes**: Existing code continues to work
2. **Extended Functionality**: New template capabilities added
3. **Consistent Interface**: Follows the same patterns as other Utils methods

## Conclusion

The template functionality has been successfully integrated into the Utils class, providing a flexible, powerful solution for rendering templates with configuration files without any side effects. The implementation maintains full compatibility with existing code while adding new universal capabilities that can work with any template and configuration file combination.
