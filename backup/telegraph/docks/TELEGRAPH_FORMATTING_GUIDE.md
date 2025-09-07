# Telegraph Formatting Guide

This document demonstrates all possible formatting tags supported by the Telegraph API.

## Created Test Page

We've successfully created a comprehensive test page demonstrating all formatting options:

**Page URL:** https://telegra.ph/Telegraph-Formatting-Test-Page-09-06-3

## Supported Tags

### Text Formatting
- `<b>` - Bold text
- `<i>` - Italic text
- `<s>` - Strikethrough text
- `<code>` - Inline code
- `<pre>` - Preformatted text (code blocks)

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

## JSON Content Structure

The content for Telegraph pages is structured as an array of node objects:

```json
[
  {
    "tag": "h3",
    "children": ["Heading Text"]
  },
  {
    "tag": "p",
    "children": [
      "This is normal text with ",
      {
        "tag": "b",
        "children": ["bold text"]
      },
      " and other elements."
    ]
  }
]
```

### Key Points:
1. Each element is an object with a `tag` property and a `children` array
2. Text content is represented as strings in the `children` array
3. Nested formatting is achieved by including objects within the `children` array
4. Attributes (like `href` for links or `src` for images) are specified in an `attrs` object

## Examples

### Simple Paragraph
```json
{
  "tag": "p",
  "children": ["This is a simple paragraph."]
}
```

### Formatted Text
```json
{
  "tag": "p",
  "children": [
    "This text has ",
    {
      "tag": "b",
      "children": ["bold"]
    },
    " and ",
    {
      "tag": "i",
      "children": ["italic"]
    },
    " formatting."
  ]
}
```

### Link
```json
{
  "tag": "p",
  "children": [
    "Visit ",
    {
      "tag": "a",
      "attrs": {
        "href": "https://example.com"
      },
      "children": ["this website"]
    },
    " for more information."
  ]
}
```

### Image
```json
{
  "tag": "figure",
  "children": [
    {
      "tag": "img",
      "attrs": {
        "src": "https://example.com/image.jpg",
        "alt": "Description"
      }
    },
    {
      "tag": "figcaption",
      "children": ["Image caption"]
    }
  ]
}
```

This guide covers all formatting options available in the Telegraph API.