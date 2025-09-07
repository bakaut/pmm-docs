# Telegraph API Formatting Test Suite

This repository contains a comprehensive test suite for all formatting options supported by the Telegraph API.

## Overview

The project demonstrates how to use the Telegraph API to create richly formatted articles with all supported HTML-like tags. It includes multiple implementations and examples to showcase different approaches.

## Created Test Pages

1. **Comprehensive Formatting Guide**: https://telegra.ph/Telegraph-Formatting-Test-Page-09-06-3
2. **Telegraph Manager Test**: https://telegra.ph/Telegraph-Formatting-Test-09-06
3. **Simple API Test**: https://telegra.ph/Telegraph-Formatting-Test-Page-09-06-2
4. **Individual Examples**:
   - Simple Text: https://telegra.ph/Telegraph-Simple-Text-Example-09-06
   - Formatted Text: https://telegra.ph/Telegraph-Formatted-Text-Example-09-06
   - Lists: https://telegra.ph/Telegraph-Lists-Example-09-06
   - Media: https://telegra.ph/Telegraph-Media-Example-09-06
   - Links: https://telegra.ph/Telegraph-Links-Example-09-06
   - Code Block: https://telegra.ph/Telegraph-Code-Block-Example-09-06
   - Complex Layout: https://telegra.ph/Telegraph-Complex-Layout-Example-09-06

## Supported Tags

### Text Formatting
- `<b>` - Bold text
- `<i>` - Italic text
- `<s>` - Strikethrough text
- `<code>` - Inline code
- `<pre>` - Preformatted text blocks

### Structure
- `<h3>` - Heading level 3
- `<h4>` - Heading level 4
- `<p>` - Paragraph
- `<blockquote>` - Blockquote
- `<hr>` - Horizontal rule

### Lists
- `<ul>` - Unordered list
- `<ol>` - Ordered list
- `<li>` - List item

### Media
- `<img>` - Image
- `<video>` - Video
- `<figure>` - Figure container
- `<figcaption>` - Figure caption

### Links
- `<a>` - Hyperlink

## Files

### Test Scripts
1. `telegraph_test.py` - Full test using the existing TelegraphManager class
2. `simple_telegraph_test.py` - Simplified version using direct API calls
3. `telegraph_manager_test.py` - Test using the TelegraphManager with proper config
4. `telegraph_examples.py` - Multiple examples of different content types
5. `telegraph_content_demo.py` - Shows the JSON structure of content

### Documentation
1. `TELEGRAPH_FORMATTING_GUIDE.md` - Comprehensive documentation of all formatting tags
2. `TELEGRAPH_TEST_SUMMARY.md` - Summary of test results
3. `README_TELEGRAPH_TEST.md` - This file

## Usage

### Prerequisites
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r flow/requirements.txt
```

### Running Tests
```bash
# Run comprehensive test
python3 telegraph_test.py

# Run simple API test
python3 simple_telegraph_test.py

# Run examples
python3 telegraph_examples.py
```

## JSON Content Structure

Telegraph content follows this structure:
```json
[
  {
    "tag": "element_type",
    "children": [
      "text content",
      {
        "tag": "nested_element",
        "children": ["nested content"]
      }
    ]
  }
]
```

### Attributes
Attributes are specified using an `attrs` object:
```json
{
  "tag": "a",
  "attrs": {"href": "https://example.com"},
  "children": ["link text"]
}
```

## Implementation Approaches

### 1. Direct API Calls
Simple HTTP requests to the Telegraph API endpoints.

### 2. TelegraphManager Class
Using the existing wrapper class from the project.

### 3. Environment-based Configuration
Properly configured using the project's configuration system.

## Conclusion

This test suite demonstrates all formatting capabilities of the Telegraph API and provides practical examples that can be used as references for implementing Telegraph integration in other projects.