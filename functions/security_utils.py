"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import asyncio
import ipaddress
import urllib.parse
import socket

async def is_safe_url(url: str) -> bool:
    """
    Validates a URL to prevent SSRF by resolving its hostname and checking
    the IP address against private, loopback, and other restricted ranges.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        loop = asyncio.get_running_loop()
        try:
            info = await loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC)
        except socket.gaierror:
            return False

        for record in info:
            ip_str = record[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_link_local:
                return False

        return True
    except Exception:
        return False

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
