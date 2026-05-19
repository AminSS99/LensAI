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

from functions.security_utils import sanitize_markdown_links

def test_sanitize_markdown_links_empty():
    """Test with empty strings and None."""
    assert sanitize_markdown_links("") == ""
    assert sanitize_markdown_links(None) is None

def test_sanitize_markdown_links_no_links():
    """Test with a string containing no markdown links."""
    assert sanitize_markdown_links("Hello World 123") == "Hello World 123"

def test_sanitize_markdown_links_basic():
    """Test with a valid basic markdown link."""
    input_str = "[OpenAI](https://openai.com)"
    expected_str = "[OpenAI](https://openai.com)"
    assert sanitize_markdown_links(input_str) == expected_str

def test_sanitize_markdown_links_with_spaces_and_brackets():
    """Test with a link that needs sanitization."""
    input_str = "[Test](http://example.com/a [b])"
    expected_str = "[Test](http://example.com/a%20%5Bb%5D)"
    assert sanitize_markdown_links(input_str) == expected_str

def test_sanitize_markdown_links_multiple():
    """Test with a string containing multiple links."""
    input_str = "Check out [Link1](https://example.com/a b) and [Link2](https://test.com/c d)."
    expected_str = "Check out [Link1](https://example.com/a%20b) and [Link2](https://test.com/c%20d)."
    assert sanitize_markdown_links(input_str) == expected_str
