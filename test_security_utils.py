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

from unittest import mock
from functions.security_utils import sanitize_html

def test_sanitize_html_empty_string():
    """Test sanitize_html with empty strings and None."""
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""

def test_sanitize_html_no_html():
    """Test sanitize_html with plain text without HTML."""
    assert sanitize_html("Just some plain text.") == "Just some plain text."

def test_sanitize_html_simple_tags():
    """Test sanitize_html with simple HTML tags."""
    assert sanitize_html("<p>Paragraph</p> <br/> Text") == "Paragraph Text"

def test_sanitize_html_script_style():
    """Test sanitize_html removes contents of script and style tags."""
    html = "Hello <script>alert('xss');</script> World <style>body { color: red; }</style>!"
    # The BeautifulSoup parser replaces tags with a space separator and strips edges
    assert sanitize_html(html) == "Hello World !"

def test_sanitize_html_fallback():
    """Test sanitize_html fallback logic when bs4 is not available."""
    html = "<div>Text with <b>bold</b> and <script>alert('1')</script></div>"

    # Mock sys.modules to simulate bs4 import error
    with mock.patch.dict('sys.modules', {'bs4': None}):
        # In the regex fallback, the script tag is stripped but its content remains
        assert sanitize_html(html) == "Text with bold and alert('1')"
