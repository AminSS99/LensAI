import pytest
from functions.semantic_search import _tokenize

def test_tokenize_standard_text():
    """Test standard alphanumeric text tokenization."""
    assert _tokenize("Hello World") == ["hello", "world"]

def test_tokenize_punctuation():
    """Test that punctuation is ignored."""
    assert _tokenize("hello, world! this-is a test.") == ["hello", "world", "this", "is", "test"]

def test_tokenize_numbers():
    """Test tokenization of numbers."""
    assert _tokenize("GPT 3.5 and 4.0") == ["gpt", "and"]

def test_tokenize_single_letter_words():
    """Test that words with fewer than 2 characters are ignored."""
    assert _tokenize("a an I is on at") == ["an", "is", "on", "at"]

def test_tokenize_none_and_empty():
    """Test handling of None and empty strings."""
    assert _tokenize(None) == []
    assert _tokenize("") == []
    assert _tokenize("   ") == []

def test_tokenize_special_chars_only():
    """Test handling of strings with only special characters."""
    assert _tokenize("!@#$%^&*()") == []
