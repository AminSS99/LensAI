"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import asyncio
import socket
import ipaddress
import urllib.parse

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
    Check if a URL is safe to fetch, preventing SSRF.
    Validates scheme and asynchronously resolves hostname to verify IP is public.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        loop = asyncio.get_running_loop()
        addr_info = await loop.getaddrinfo(hostname, None)

        for info in addr_info:
            ip_str = info[4][0]
            ip = ipaddress.ip_address(ip_str)

            # Reject if the IP is not a globally routable public IP
            if not ip.is_global:
                return False
            # Fallback checks (though is_global usually covers these)
            if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_link_local or ip.is_unspecified:
                return False

        return True
    except Exception:
        return False
