import pytest
from functions.security_utils import escape_markdown_v1, is_safe_url
from unittest.mock import patch

@pytest.mark.asyncio
async def test_is_safe_url_valid_urls():
    """Test valid URLs that should be considered safe."""
    # Ensure google.com resolves to a safe IP
    assert await is_safe_url("https://www.google.com") is True
    assert await is_safe_url("http://github.com/test") is True

@pytest.mark.asyncio
async def test_is_safe_url_invalid_schemes():
    """Test URLs with invalid schemes like ftp, file."""
    assert await is_safe_url("ftp://test.com") is False
    assert await is_safe_url("file:///etc/passwd") is False
    assert await is_safe_url("javascript:alert(1)") is False

@pytest.mark.asyncio
@patch('socket.getaddrinfo')
async def test_is_safe_url_unsafe_ips(mock_getaddrinfo):
    """Test URLs resolving to unsafe internal IPs."""

    # Loopback
    mock_getaddrinfo.return_value = [(2, 1, 6, '', ('127.0.0.1', 80))]
    assert await is_safe_url("http://localhost") is False

    # Private
    mock_getaddrinfo.return_value = [(2, 1, 6, '', ('192.168.1.5', 80))]
    assert await is_safe_url("http://internal-server") is False

    mock_getaddrinfo.return_value = [(2, 1, 6, '', ('10.0.0.1', 80))]
    assert await is_safe_url("http://database") is False

    # Link-local AWS metadata
    mock_getaddrinfo.return_value = [(2, 1, 6, '', ('169.254.169.254', 80))]
    assert await is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    # 0.0.0.0
    mock_getaddrinfo.return_value = [(2, 1, 6, '', ('0.0.0.0', 80))]
    assert await is_safe_url("http://0.0.0.0:8080") is False

    # IPv6 loopback
    mock_getaddrinfo.return_value = [(10, 1, 6, '', ('::1', 80, 0, 0))]
    assert await is_safe_url("http://[::1]") is False

@pytest.mark.asyncio
async def test_is_safe_url_unresolvable():
    """Test unresolvable domains."""
    assert await is_safe_url("http://this-domain-does-not-exist.example.com") is False

@pytest.mark.asyncio
async def test_is_safe_url_empty():
    assert await is_safe_url("") is False
    assert await is_safe_url(None) is False


def test_escape_markdown_v1_empty_string():
    """Test with empty strings and None."""
    assert escape_markdown_v1("") == ""
    assert escape_markdown_v1(None) == ""

def test_escape_markdown_v1_no_special_chars():
    """Test with a string containing no markdown characters."""
    assert escape_markdown_v1("Hello World 123") == "Hello World 123"

def test_escape_markdown_v1_special_chars():
    """Test with all target markdown characters."""
    # Escapes: _ * [ ] ( ) ~ ` > # + - = | { } . !
    input_str = "Hello _*[]()~`>#+-=|{}.! World"
    expected_str = r"Hello \_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\! World"
    assert escape_markdown_v1(input_str) == expected_str

def test_escape_markdown_v1_urls():
    """Test with a realistic URL markdown."""
    input_str = "[OpenAI](https://openai.com)"
    expected_str = r"\[OpenAI\]\(https://openai\.com\)"
    assert escape_markdown_v1(input_str) == expected_str

def test_escape_markdown_v1_bold_italic():
    """Test with realistic bold and italic markdown."""
    input_str = "*Bold* and _Italic_"
    expected_str = r"\*Bold\* and \_Italic\_"
    assert escape_markdown_v1(input_str) == expected_str

def test_escape_markdown_v1_multiple_occurrences():
    """Test with multiple occurrences of the same special character."""
    input_str = "___***"
    expected_str = r"\_\_\_\*\*\*"
    assert escape_markdown_v1(input_str) == expected_str

def test_escape_markdown_v1_mixed_text():
    """Test with a mix of text and special characters simulating a real message."""
    input_str = "Check out this *awesome* repo: [Link](https://github.com/test)! It's 100% free."
    expected_str = r"Check out this \*awesome\* repo: \[Link\]\(https://github\.com/test\)\! It's 100% free\."
    assert escape_markdown_v1(input_str) == expected_str
