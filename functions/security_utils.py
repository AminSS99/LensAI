"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib

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


import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

async def is_safe_url(url: str) -> bool:
    """
    Validate a URL to prevent Server-Side Request Forgery (SSRF) attacks.
    Checks for local, loopback, private IP ranges, and internal hostnames
    without blocking the event loop.

    Args:
        url: The URL string to validate

    Returns:
        True if the URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Check if the hostname is directly an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            if not ip.is_global or ip.is_unspecified or ip.is_link_local or ip.is_loopback or ip.is_private or ip.is_multicast or ip.is_reserved:
                return False
        except ValueError:
            # It's a domain name, resolve it asynchronously
            loop = asyncio.get_running_loop()
            try:
                # getaddrinfo returns a list of 5-tuples:
                # (family, type, proto, canonname, sockaddr)
                # sockaddr for IPv4 is a 2-tuple (address, port)
                # sockaddr for IPv6 is a 4-tuple (address, port, flow info, scope id)
                addr_info = await loop.getaddrinfo(hostname, None)
                for info in addr_info:
                    ip_str = info[4][0]
                    ip = ipaddress.ip_address(ip_str)
                    if not ip.is_global or ip.is_unspecified or ip.is_link_local or ip.is_loopback or ip.is_private or ip.is_multicast or ip.is_reserved:
                        return False
            except socket.gaierror:
                return False # DNS resolution failed or invalid hostname

        return True
    except Exception:
        return False


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
