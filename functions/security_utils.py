"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import asyncio
import urllib.parse
import ipaddress

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


async def is_safe_url(url: str) -> bool:
    """
    Validate that a URL is safe to fetch (prevents SSRF).
    Rejects local, loopback, private IP ranges, and internal hostnames.

    Args:
        url: The URL to validate

    Returns:
        True if safe, False otherwise
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        loop = asyncio.get_running_loop()
        addrs = await loop.getaddrinfo(hostname, None)

        for addr in addrs:
            ip = ipaddress.ip_address(addr[4][0])
            if not ip.is_global or ip.is_link_local or ip.is_unspecified:
                return False

        return True
    except Exception:
        return False
