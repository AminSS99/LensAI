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


def sanitize_markdown_url(url: str) -> str:
    """
    Sanitize a URL before embedding it in Markdown link syntax.
    Encodes characters that could break out of the link context.
    """
    if not url:
        return ""
    # Encode Markdown-breaking and whitespace characters
    replacements = {
        " ": "%20",
        "(": "%28",
        ")": "%29",
        "[": "%5B",
        "]": "%5D",
    }
    for old, new in replacements.items():
        url = url.replace(old, new)
    return url


def sanitize_markdown_links(text: str) -> str:
    """
    Post-process text containing Markdown links and sanitize every URL.
    """
    if not text:
        return text

    def _replace_link(match):
        prefix = match.group(1)
        url = match.group(2)
        return f"{prefix}{sanitize_markdown_url(url)})"

    return re.sub(r"(\[[^\]]+\]\()(https?://[^\)]+)", _replace_link, text)


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
    Sanitize HTML content by stripping tags and removing script/style contents.
    Replaces tags with spaces to prevent text merging.
    """
    if not text:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, 'html.parser')
        for element in soup(['script', 'style']):
            element.decompose()
        return soup.get_text(separator=' ', strip=True)
    except ImportError:
        # Fallback if BeautifulSoup is not available
        import re
        return " ".join(re.sub(r'<[^>]+>', ' ', text).split())
