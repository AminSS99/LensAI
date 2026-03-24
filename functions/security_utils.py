import asyncio
import socket
import ipaddress
import urllib.parse
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
    Validate if a URL is safe to fetch, preventing SSRF.
    Checks scheme, hostname, and resolves IP to block private/local ranges.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Resolve hostname to IP asynchronously
        loop = asyncio.get_running_loop()
        # getaddrinfo returns a list of tuples: (family, type, proto, canonname, sockaddr)
        # sockaddr for IPv4 is (address, port)
        # sockaddr for IPv6 is (address, port, flow info, scope id)
        addrs = await loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)

        if not addrs:
            return False

        for addr_info in addrs:
            ip_str = addr_info[4][0]
            ip = ipaddress.ip_address(ip_str)

            # Block private, loopback, link-local, multicast, and unspecified addresses
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_multicast or ip.is_unspecified or ip.is_reserved):
                return False

        return True
    except Exception as e:
        # On any error (parsing, resolution, invalid IP), consider unsafe
        print(f"URL validation error: {e}")
        return False
