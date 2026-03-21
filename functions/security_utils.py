"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import ipaddress
from urllib.parse import urlparse

def escape_markdown_v1(text: str) -> str:
    """
    Escape special characters for Telegram Markdown V1.
    Escapes: _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Args:
        text: Input text string
        
    Returns:
        Escaped text safe for Markdown V1
    """
    if not text:
        return ""
        
    # List of special characters in Markdown V1 that need escaping
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


def stable_hash(value: str) -> str:
    """
    Create a deterministic hash suitable for document IDs.
    
    Args:
        value: Input string
        
    Returns:
        64-char lowercase hex SHA-256 digest
    """
    if not value:
        value = ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def is_safe_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks.
    Ensures URL uses http/https scheme and is not pointing to
    local, private, or loopback network addresses.

    Args:
        url: The URL to validate

    Returns:
        True if safe, False if potentially malicious
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        try:
            # Check if hostname is an IP address
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP address, check for localhost/local domains
            if hostname == 'localhost' or hostname.endswith('.local') or hostname == 'metadata.google.internal':
                return False

        return True
    except Exception:
        return False
