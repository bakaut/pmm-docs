#!/usr/bin/env python3
"""
Examples of different content types for Telegraph articles.
"""

import sys
import os

# Add the mindset module to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'flow'))

from flow.mindset.telegraph import TelegraphManager
from flow.mindset.config import Config

def example_simple_text():
    """Simple text content example."""
    return [
        {"tag": "h3", "children": ["Simple Text Example"]},
        {"tag": "p", "children": ["This is a simple paragraph with no formatting."]}
    ]

def example_formatted_text():
    """Text with various formatting options."""
    return [
        {"tag": "h3", "children": ["Formatted Text Example"]},
        {"tag": "p", "children": [
            "This paragraph contains ",
            {"tag": "b", "children": ["bold text"]},
            ", ",
            {"tag": "i", "children": ["italic text"]},
            ", ",
            {"tag": "s", "children": ["strikethrough text"]},
            ", and ",
            {"tag": "code", "children": ["inline code"]},
            "."
        ]}
    ]

def example_lists():
    """Example with different list types."""
    return [
        {"tag": "h3", "children": ["List Examples"]},
        {"tag": "h4", "children": ["Unordered List"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": ["First item"]},
            {"tag": "li", "children": ["Second item"]},
            {"tag": "li", "children": ["Third item"]}
        ]},
        {"tag": "h4", "children": ["Ordered List"]},
        {"tag": "ol", "children": [
            {"tag": "li", "children": ["First step"]},
            {"tag": "li", "children": ["Second step"]},
            {"tag": "li", "children": ["Third step"]}
        ]}
    ]

def example_media():
    """Example with media elements."""
    return [
        {"tag": "h3", "children": ["Media Examples"]},
        {"tag": "figure", "children": [
            {"tag": "img", "attrs": {"src": "https://telegra.ph/images/logo.png"}},
            {"tag": "figcaption", "children": ["Telegraph Logo"]}
        ]},
        {"tag": "p", "children": ["This is a paragraph after the image."]}
    ]

def example_links():
    """Example with hyperlinks."""
    return [
        {"tag": "h3", "children": ["Link Examples"]},
        {"tag": "p", "children": [
            "Visit the ",
            {"tag": "a", "attrs": {"href": "https://telegra.ph"}, "children": ["Telegraph website"]},
            " for more information."
        ]}
    ]

def example_code_block():
    """Example with code blocks."""
    return [
        {"tag": "h3", "children": ["Code Block Example"]},
        {"tag": "pre", "children": [{"tag": "code", "children": [
            "def hello_world():\n",
            "    print('Hello, Telegraph!')\n",
            "    return True"
        ]}]},
        {"tag": "p", "children": ["This is a Python code example."]}
    ]

def example_complex_layout():
    """Complex layout with multiple elements."""
    return [
        {"tag": "h3", "children": ["Complex Layout Example"]},
        {"tag": "p", "children": ["This example combines multiple formatting options."]},
        {"tag": "blockquote", "children": ["This is an important quote to remember."]},
        {"tag": "h4", "children": ["Key Features"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": [{"tag": "b", "children": ["Bold item"]}]},
            {"tag": "li", "children": [{"tag": "i", "children": ["Italic item"]}]},
            {"tag": "li", "children": [{"tag": "s", "children": ["Strikethrough item"]}]}
        ]},
        {"tag": "hr"},
        {"tag": "p", "children": [
            "For more details, see the ",
            {"tag": "a", "attrs": {"href": "https://telegra.ph/api"}, "children": ["API documentation"]},
            "."
        ]}
    ]

def main():
    """Run all examples."""

    # Create config using environment variables approach
    config_dict = {
        "bot_token": "dummy_token",
        "database_url": "postgresql://dummy:dummy@localhost/dummy",
        "operouter_key": "dummy_key",
        "suno_api_key": "dummy_suno_key",
        "telegraph_api_key": "3e52657449f1054c210291c7a2e5712eff217c8b129d27996a92c6603ad3",
        "telegraph_bot_username": "test",
        "telegraph_short_name": "test",
        "telegraph_author_name": "sandbox"
    }

    config = Config.from_env(config_dict)
    telegraph = TelegraphManager(config)

    examples = [
        ("Simple Text", example_simple_text),
        ("Formatted Text", example_formatted_text),
        ("Lists", example_lists),
        ("Media", example_media),
        ("Links", example_links),
        ("Code Block", example_code_block),
        ("Complex Layout", example_complex_layout)
    ]

    for name, example_func in examples:
        print(f"Creating page for: {name}")
        content = example_func()
        page = telegraph.create_page(
            tg_id=123456789,
            chat_id=987654321,
            title=f"Telegraph {name} Example",
            content=content
        )

        if page:
            print(f"✅ Created: https://telegra.ph/{page['path']}")
        else:
            print(f"❌ Failed to create {name} example")
        print()

if __name__ == "__main__":
    main()
