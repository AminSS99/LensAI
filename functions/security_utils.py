"""
Security Utilities Module
Contains helper functions for input sanitization and security.
"""

import re
import hashlib
import asyncio
import urllib.parse
import ipaddress

async def is_safe_url(url: str) -> bool:
    """
    Check if a URL is safe to fetch (prevents SSRF).
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
            ip_str = addr[4][0]
            if '%' in ip_str:
                ip_str = ip_str.split('%')[0]
            ip = ipaddress.ip_address(ip_str)
            if not ip.is_global or ip.is_link_local or ip.is_unspecified:
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

def sanitize_html(text: str) -> str:
    """
    Sanitizes HTML content by stripping tags and properly spacing text.
    Removes <script> and <style> content entirely to prevent XSS.

    Args:
        text: Input HTML string

    Returns:
        Cleaned plain text string
    """
    if not text:
        return ""

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, 'html.parser')

        # Remove script and style elements completely
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract text with space separator to prevent words from merging
        return soup.get_text(separator=' ', strip=True)
    except ImportError:
        # Fallback if bs4 is not available (should not happen in prod)
        return " ".join(re.sub(r'<[^>]+>', ' ', text).split())
    except Exception as e:
        print(f"HTML sanitization error: {e}")
        return " ".join(re.sub(r'<[^>]+>', ' ', text).split())
