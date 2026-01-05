"""
Security Utility Functions
"""

import re

def escape_markdown_v1(text: str) -> str:
    """
    Helper function to escape telegram markup symbols.
    Escapes: '_', '*', '`', '['
    """
    if not text:
        return ""
    # Escape markdown characters
    escape_chars = r'[_*`\[]'
    return re.sub(f'({escape_chars})', r'\\\1', str(text))

def sanitize_html(text: str) -> str:
    """
    Sanitize HTML tags from text.
    """
    return re.sub(r'<[^>]*>', '', text)
