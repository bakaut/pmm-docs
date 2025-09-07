# Template Handler Documentation

**Note**: This documentation has been updated to reflect the new file naming convention where configuration files use `.yaml` extension and template files use `.j2` extension.

The Template Handler is a dynamic template rendering system built on Jinja2 that allows for flexible generation of documentation and other text-based content by incorporating files, conditional logic, and data from various sources.

## Features

- **Dynamic File Inclusion**: Include content from external files directly in templates
- **Conditional Rendering**: Show or hide sections based on variables
- **JSON Data Loading**: Load and iterate through JSON data structures
- **File Existence Checking**: Conditionally render content based on file availability
- **Flexible Configuration**: Use YAML configuration files to manage template variables
- **Separate File Storage**: Store configuration in `.yaml` files and templates in `.j2` files

## Installation

The template handler requires the following dependencies:
- `jinja2` - Template engine
- Standard library modules: `os`, `json`, `yaml`, `textwrap`

## Usage

### Basic Usage

```python
from mindset.template_handler import TemplateHandler

# Initialize the handler
handler = TemplateHandler(base_path="/path/to/templates")

# Create a configuration in a separate YAML file
config_data = {
    "vars": {
        "title": "My Document",
        "show_section": True
    },
    "files": {
        "example_file": "/path/to/example.txt"
    }
}
handler.create_config(config_data, "/path/to/config.yaml")

# Create a template in a separate file
template_text = """
# {{ title }}

{% if show_section %}
## Included Content
{{ read_file(files.example_file) }}
{% endif %}

## File Check
The example file {{ 'exists' if file_exists(files.example_file) else 'does not exist' }}.
"""
handler.create_template(template_text, "example.j2")

# Load config from YAML file
config = handler.load_config("/path/to/config.yaml")

# Prepare context from loaded config
context = {
    "title": config["vars"]["title"],
    "show_section": config["vars"]["show_section"],
    "files": config["files"]
}

# Render the template (without saving output)
rendered = handler.render_template("example.j2", context)
```

### Universal Template Usage

For working with any template and configuration file combination:

```python
from mindset.template_handler import (
    TemplateHandler, 
    render_template_with_config, 
    render_arch_document
)

# Method 1: Using the universal function directly
content = render_template_with_config(
    config_path="/path/to/config.yaml",
    template_path="/path/to/template.j2"
)

# Method 2: Using the ARCH-specific convenience function
content = render_arch_document(
    config_path="/path/to/arch.yaml",
    template_path="/path/to/arch.txt.j2"
)

# Method 3: Manual approach with TemplateHandler
handler = TemplateHandler()

# Load config and prepare context
config = handler.load_config("/path/to/config.yaml")
context = handler.load_config_context("/path/to/config.yaml")

# Render template (without saving output)
rendered = handler.render_template("template.j2", context)
```

## Template Functions

The following functions are available within templates:

### `read_file(path, default="")`
Reads content from a file.
- `path`: Path to the file
- `default`: Default value if file is not found

### `load_json(path)`
Loads and parses a JSON file.
- `path`: Path to the JSON file

### `file_exists(path)`
Checks if a file exists.
- `path`: Path to check

## Example Templates

### Basic Template
```jinja2
# {{ title }}

{% if show_introduction %}
> {{ read_file(files.introduction_file)[:200] }}...
{% endif %}

{% if show_details %}
## Details
{% set data = load_json(files.data_file) %}
{% for key, value in data.items() %}
- **{{ key }}**: {{ value }}
{% endfor %}
{% endif %}

## File Status
- Introduction file: {{ 'OK' if file_exists(files.introduction_file) else 'missing' }}
```

### ARCH Template
```jinja2
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
```

## Testing

Run the test suite:
```bash
cd /path/to/flow
python3 -m mindset.test_template_handler
```

Run the examples:
```bash
cd /path/to/flow
python3 -m mindset.example_template_usage

# Run examples with updated file names
python3 -m mindset.example_template_usage_updated

# Run demo with updated file names
python3 -m mindset.demo_template_handler_updated
```

## Integration

The template handler is integrated into the mindset module and can be imported as:
```python
from mindset import TemplateHandler
```

## Error Handling

The template handler includes comprehensive error handling:
- File not found errors return default values
- JSON parsing errors return empty dictionaries
- Template rendering errors are caught and returned as error messages
- All operations are logged for debugging purposes

## Customization

To customize the template handler for your specific needs:
1. Create a new template with your desired structure
2. Define the appropriate context variables
3. Use the available functions to include dynamic content
4. Add any additional functions by extending the Jinja2 environment