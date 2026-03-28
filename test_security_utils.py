import pytest
from functions.security_utils import escape_markdown_v1

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

@pytest.mark.asyncio
async def test_is_safe_url():
    """Test is_safe_url function for SSRF prevention."""
    from functions.security_utils import is_safe_url

    # Safe URLs
    assert await is_safe_url("https://google.com") is True
    assert await is_safe_url("http://example.com/path") is True

    # Invalid schemes
    assert await is_safe_url("ftp://example.com") is False
    assert await is_safe_url("file:///etc/passwd") is False
    assert await is_safe_url("javascript:alert(1)") is False

    # Localhost/Loopback
    assert await is_safe_url("http://localhost") is False
    assert await is_safe_url("http://127.0.0.1") is False
    assert await is_safe_url("http://[::1]") is False
    assert await is_safe_url("http://localhost.localdomain") is False

    # Private IP ranges
    assert await is_safe_url("http://192.168.1.1") is False
    assert await is_safe_url("http://10.0.0.1") is False
    assert await is_safe_url("http://172.16.0.1") is False

    # Link-local / AWS metadata
    assert await is_safe_url("http://169.254.169.254") is False
    assert await is_safe_url("http://169.254.169.254/latest/meta-data/") is False
