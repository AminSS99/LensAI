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

# ==================== HMAC SECURITY TESTS ====================
import os
import sys
from unittest.mock import patch, MagicMock

# Create mock function framework environment to import main
mock_ff = MagicMock()
mock_ff.http = lambda f: f
sys.modules['functions_framework'] = mock_ff
sys.path.insert(0, os.path.abspath('functions'))

# Create stubs for telegram_bot and telegram
sys.modules['functions.telegram_bot'] = MagicMock()
import importlib
# Hack to mock the relative import
class MockFunctions:
    telegram_bot = MagicMock()
sys.modules['functions'] = MockFunctions()
import main
main.__package__ = "functions"

sys.modules['telegram'] = MagicMock()
sys.modules['flask'] = MagicMock()
sys.modules['functions.breaking_news'] = MagicMock()
sys.modules['functions.database'] = MagicMock()
sys.modules['functions.user_storage'] = MagicMock()
sys.modules['functions.deep_dive'] = MagicMock()
sys.modules['functions.stalker'] = MagicMock()
sys.modules['functions.scrapers.hackernews'] = MagicMock()
sys.modules['functions.scrapers.techcrunch'] = MagicMock()
sys.modules['functions.scrapers.ai_blogs'] = MagicMock()
sys.modules['functions.scrapers.theverge'] = MagicMock()
sys.modules['functions.scrapers.github_trending'] = MagicMock()
sys.modules['functions.scrapers.producthunt'] = MagicMock()
sys.modules['functions.cache'] = MagicMock()

import main

class MockRequest:
    def __init__(self, headers=None, method='POST', json_data=None):
        self.headers = headers or {}
        self.method = method
        self.json_data = json_data

    def get_json(self):
        return self.json_data

@patch.dict(os.environ, {"WEBHOOK_SECRET_TOKEN": "my-secret-token"})
def test_telegram_webhook_hmac():
    # Missing header should use empty string and fail safely
    req = MockRequest(headers={})
    res, status = main.telegram_webhook(req)
    assert status == 403
    assert res == "Unauthorized"

    # Incorrect header should fail
    req = MockRequest(headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-token"})
    res, status = main.telegram_webhook(req)
    assert status == 403
    assert res == "Unauthorized"

@patch.dict(os.environ, {"INTERNAL_SECRET": "internal-secret"})
def test_internal_secret_hmac():
    # Missing header
    req = MockRequest(headers={})
    ok, error = main._require_internal_secret(req)
    assert not ok
    assert error[1] == 403

    # Incorrect header
    req = MockRequest(headers={"X-Internal-Secret": "wrong-secret"})
    ok, error = main._require_internal_secret(req)
    assert not ok
    assert error[1] == 403

    # Correct header
    req = MockRequest(headers={"X-Internal-Secret": "internal-secret"})
    ok, error = main._require_internal_secret(req)
    assert ok
    assert error == ()
