# Extra Arguments Feature for Template Rendering

## Overview

The template rendering functionality in the Utils class has been enhanced to support passing extra arguments to templates. This allows users to provide additional key-value pairs that will be available in the template context during rendering.

## Key Changes

### Updated Method Signatures

1. **`render_template_with_config()`**:
   ```python
   def render_template_with_config(self, config_path: str, template_path: str, extra_args: Optional[Dict[str, Any]] = None) -> str:
   ```

2. **`render_arch_document()`**:
   ```python
   def render_arch_document(self, config_path: str = "/mnt/data/arch.yaml", template_path: str = "/mnt/data/templates/arch.txt.j2", extra_args: Optional[Dict[str, Any]] = None) -> str:
   ```

### Implementation Details

The extra arguments are merged with the template context after loading the configuration file. This allows the extra arguments to override configuration values if there are conflicts.

```python
# Load config from YAML file
cfg = self.load_config(config_path)

ctx = (cfg.get("vars") or {})
ctx["files"] = cfg.get("files") or {}

# Add extra arguments if provided
if extra_args:
    ctx.update(extra_args)
```

## Usage Examples

### Basic Usage with Extra Arguments

```python
from mindset.utils import Utils

# Create Utils instance
utils = Utils(config)

# Define extra arguments
extra_args = {
    "timestamp": "2023-01-01 12:00:00",
    "user_name": "John Doe",
    "request_id": "REQ-12345",
    "custom_data": {"key": "value"}
}

# Render template with extra arguments
content = utils.render_template_with_config(
    config_path="/path/to/config.yaml",
    template_path="/path/to/template.j2",
    extra_args=extra_args
)
```

### ARCH-Specific Usage with Extra Arguments

```python
from mindset.utils import Utils

# Create Utils instance
utils = Utils(config)

# Define extra arguments
extra_args = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "user_name": "Jane Smith",
    "version": "1.2.3"
}

# Render ARCH template with extra arguments
content = utils.render_arch_document(
    config_path="/path/to/arch.yaml",
    template_path="/path/to/arch.txt.j2",
    extra_args=extra_args
)
```

## Template Usage

In the Jinja2 templates, extra arguments can be accessed directly by their key names:

```jinja2
# {{ title }}

Generated on: {{ timestamp|default("Unknown date") }}
For user: {{ user_name|default("Anonymous") }}
Version: {{ version|default("N/A") }}

{% if show_arch_intro %}
> Architectural instructions (fragment):
>
> {{ read_file(files.arch_txt)[:200] }}...
{% endif %}

Custom data: {{ custom_data.key|default("Not provided") }}
```

Note the use of the `default` filter to handle cases where extra arguments might not be provided.

## Benefits

1. **Flexibility**: Users can pass runtime data to templates without modifying configuration files
2. **Dynamic Content**: Templates can include dynamic information like timestamps, user names, request IDs, etc.
3. **Backward Compatibility**: Existing code continues to work without changes
4. **Optional Parameters**: Extra arguments are optional and default to None

## Testing

The feature has been tested with:
- Rendering templates with and without extra arguments
- Verifying that extra arguments are correctly passed to templates
- Testing the ARCH-specific function with extra arguments
- Ensuring backward compatibility

## Integration

The extra arguments feature integrates seamlessly with the existing template rendering functionality:
1. **No Breaking Changes**: Existing code continues to work
2. **Extended Functionality**: New capabilities added without affecting existing behavior
3. **Consistent Interface**: Follows the same patterns as other Utils methods

## Conclusion

The extra arguments feature enhances the template rendering functionality by allowing users to pass additional data to templates at runtime. This provides greater flexibility and enables more dynamic template generation without requiring changes to configuration files.
