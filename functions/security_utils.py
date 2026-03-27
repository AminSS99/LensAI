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
    Validates a URL against Server-Side Request Forgery (SSRF) attacks.
    Checks that the URL scheme is http/https and the resolved IP address is public.

    Args:
        url: The URL to validate

    Returns:
        True if the URL is safe, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Initial quick check for obvious internal names
        if hostname.lower() in ('localhost', 'metadata.google.internal') or hostname.lower().endswith(('.local', '.internal')):
            return False

        # Try to parse as an IP address first
        try:
            ip_obj = ipaddress.ip_address(hostname)
            # If it's a direct IP, check if it's private/loopback/etc
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                return False
        except ValueError:
            # It's a domain name, resolve it
            loop = asyncio.get_running_loop()
            try:
                # getaddrinfo returns (family, type, proto, canonname, sockaddr)
                addr_info = await loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
                for item in addr_info:
                    ip_str = item[4][0]
                    ip_obj = ipaddress.ip_address(ip_str)
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                        return False
            except socket.gaierror:
                return False # Could not resolve

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
