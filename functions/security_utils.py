"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import urllib.parse
import ipaddress
import asyncio
import socket

async def is_safe_url(url: str) -> bool:
    """
    Validates a URL to prevent Server-Side Request Forgery (SSRF).
    Resolves the hostname asynchronously and rejects private, loopback,
    multicast, and reserved IP addresses.
    Only allows 'http' and 'https' schemes.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Asynchronously resolve the hostname
        loop = asyncio.get_running_loop()
        try:
            addrinfo = await loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False

        # Check all resolved IP addresses
        for res in addrinfo:
            ip_str = res[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                # Reject if the IP is not globally routable or is explicitly reserved/private
                if (ip_obj.is_loopback or
                    ip_obj.is_private or
                    ip_obj.is_multicast or
                    ip_obj.is_link_local or
                    ip_obj.is_reserved or
                    ip_obj.is_unspecified or
                    not ip_obj.is_global):
                    return False
            except ValueError:
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
