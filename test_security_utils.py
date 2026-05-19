import pytest
from functions.security_utils import escape_markdown_v1, sanitize_markdown_url

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


def test_sanitize_markdown_url_empty():
    """Test with empty string."""
    assert sanitize_markdown_url("") == ""

def test_sanitize_markdown_url_no_special_chars():
    """Test with a normal URL."""
    assert sanitize_markdown_url("https://example.com/path") == "https://example.com/path"

def test_sanitize_markdown_url_spaces():
    """Test with spaces in the URL."""
    assert sanitize_markdown_url("https://example.com/my path") == "https://example.com/my%20path"

def test_sanitize_markdown_url_parentheses():
    """Test with parentheses in the URL."""
    assert sanitize_markdown_url("https://example.com/path(1)") == "https://example.com/path%281%29"

def test_sanitize_markdown_url_brackets():
    """Test with brackets in the URL."""
    assert sanitize_markdown_url("https://example.com/path[2]") == "https://example.com/path%5B2%5D"

def test_sanitize_markdown_url_mixed():
    """Test with a mix of special characters in the URL."""
    assert sanitize_markdown_url("https://example.com/my [weird] (path)") == "https://example.com/my%20%5Bweird%5D%20%28path%29"
