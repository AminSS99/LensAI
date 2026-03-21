"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import asyncio
import socket
import ipaddress
from urllib.parse import urlparse

async def is_safe_url(url: str) -> bool:
    """
    Validate that a URL is safe to fetch, preventing Server-Side Request Forgery (SSRF).
    Rejects non-HTTP(S) schemes, local network IPs, loopback, and private IPs.
    Also validates IPv6 addresses.

    Args:
        url: The URL to validate.

    Returns:
        True if the URL is safe to fetch, False otherwise.
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # 1. Restrict schemes to http and https
    if parsed.scheme.lower() not in ('http', 'https'):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # 2. Resolve hostname to IP addresses (IPv4 and IPv6) without blocking the event loop
    try:
        addrinfo = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except Exception:
        # If it cannot be resolved, it's unsafe or unreachable
        return False

    # 3. Check all resolved IPs to ensure NONE are internal
    for res in addrinfo:
        ip_str = res[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        # Block loopback, private, and link-local IP addresses
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            return False

        # Additional check: 0.0.0.0 and :: are blocked
        if ip_str in ('0.0.0.0', '::'):
            return False

    return True


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
