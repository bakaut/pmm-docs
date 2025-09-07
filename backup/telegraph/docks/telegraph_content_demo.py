#!/usr/bin/env python3
"""
Demo script showing the JSON structure for all Telegraph formatting tags.
This script outputs the exact JSON content structure used for Telegraph articles.
"""

import json

def create_comprehensive_test_content():
    """Create content with all possible formatting tags supported by Telegraph API."""
    
    # Comprehensive content with all formatting options
    content = [
        # Title/Heading
        {"tag": "h3", "children": ["Comprehensive Telegraph Formatting Guide"]},
        {"tag": "p", "children": ["This page demonstrates all formatting options available in the Telegraph API."]},
        
        # Text formatting
        {"tag": "p", "children": ["This is normal text with ", {"tag": "b", "children": ["bold text"]}, ", ", 
                                {"tag": "i", "children": ["italic text"]}, ", and ", 
                                {"tag": "s", "children": ["strikethrough text"]}, "."]},
        
        {"tag": "p", "children": [{"tag": "code", "children": ["Inline code example: print('Hello World')"]}]},
        
        {"tag": "p", "children": ["This is ", {"tag": "a", "attrs": {"href": "https://example.com"}, 
                                             "children": ["a hyperlink"]}, " to example.com."]},
        
        # Blockquote
        {"tag": "blockquote", "children": ["This is a blockquote. It can contain multiple lines of text and even ", 
                                         {"tag": "b", "children": ["formatted text"]}, "."]},
        
        # Code block
        {"tag": "pre", "children": [{"tag": "code", "children": [
            "def hello_world():\n",
            "    print('Hello, Telegraph!')\n",
            "    return True"
        ]}]},
        
        # Lists
        {"tag": "h4", "children": ["Unordered List"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": ["First item"]},
            {"tag": "li", "children": ["Second item with ", {"tag": "b", "children": ["bold text"]}]},
            {"tag": "li", "children": ["Third item"]}
        ]},
        
        {"tag": "h4", "children": ["Ordered List"]},
        {"tag": "ol", "children": [
            {"tag": "li", "children": ["First step"]},
            {"tag": "li", "children": ["Second step"]},
            {"tag": "li", "children": ["Third step"]}
        ]},
        
        # Horizontal rule
        {"tag": "hr"},
        
        # Images
        {"tag": "h4", "children": ["Image Example"]},
        {"tag": "p", "children": ["Below is an example image:"]},
        {"tag": "figure", "children": [
            {"tag": "img", "attrs": {"src": "https://telegra.ph/images/logo.png", "alt": "Telegraph Logo"}},
            {"tag": "figcaption", "children": ["Telegraph Logo"]}
        ]},
        
        # Video
        {"tag": "h4", "children": ["Video Example"]},
        {"tag": "p", "children": ["Below is an example video:"]},
        {"tag": "figure", "children": [
            {"tag": "video", "attrs": {"src": "https://telegra.ph/videos/sample.mp4", "controls": True}},
            {"tag": "figcaption", "children": ["Sample Video"]}
        ]},
        
        # Complex formatting
        {"tag": "h4", "children": ["Complex Formatting Example"]},
        {"tag": "p", "children": [
            "This paragraph contains ", 
            {"tag": "b", "children": ["bold"]}, 
            ", ", 
            {"tag": "i", "children": ["italic"]}, 
            ", ", 
            {"tag": "s", "children": ["strikethrough"]},
            ", and ",
            {"tag": "code", "children": ["code"]},
            " all in one sentence."
        ]},
        
        # Nested lists
        {"tag": "h4", "children": ["Nested Lists"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": ["Main item 1"]},
            {"tag": "li", "children": [
                "Main item 2 with nested list:",
                {"tag": "ul", "children": [
                    {"tag": "li", "children": ["Sub-item 2.1"]},
                    {"tag": "li", "children": ["Sub-item 2.2"]}
                ]}
            ]},
            {"tag": "li", "children": ["Main item 3"]}
        ]},
        
        # Final section
        {"tag": "h4", "children": ["Conclusion"]},
        {"tag": "p", "children": ["This page demonstrates all formatting options supported by the Telegraph API."]},
        {"tag": "p", "children": [
            "For more information, visit the ",
            {"tag": "a", "attrs": {"href": "https://telegra.ph/api"}, "children": ["Telegraph API documentation"]},
            "."
        ]}
    ]
    
    return content

def main():
    """Main function to display the JSON structure."""
    
    content = create_comprehensive_test_content()
    
    print("=== Telegraph Content JSON Structure ===")
    print(json.dumps(content, indent=2, ensure_ascii=False))
    
    print("\n=== Supported Tags Summary ===")
    tags = [
        "h3, h4 (Headers)",
        "p (Paragraph)",
        "b (Bold)",
        "i (Italic)",
        "s (Strikethrough)",
        "code (Inline code)",
        "pre (Code block)",
        "a (Link)",
        "blockquote (Blockquote)",
        "ul, ol, li (Lists)",
        "hr (Horizontal rule)",
        "img (Image)",
        "video (Video)",
        "figure, figcaption (Figure with caption)"
    ]
    
    for tag in tags:
        print(f"- {tag}")

if __name__ == "__main__":
    main()