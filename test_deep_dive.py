import pytest
from functions.deep_dive import extract_github_repo

def test_extract_github_repo_valid():
    assert extract_github_repo("https://github.com/foo/bar") == "foo/bar"
    assert extract_github_repo("http://github.com/foo/bar/baz") == "foo/bar"
    assert extract_github_repo("https://github.com/foo/bar/") == "foo/bar"
    assert extract_github_repo("github.com/foo/bar") == "foo/bar"

def test_extract_github_repo_invalid():
    assert extract_github_repo("https://google.com/foo/bar") is None
    assert extract_github_repo("https://github.com/foo") is None
    assert extract_github_repo("") is None
    assert extract_github_repo(None) is None

def test_extract_github_repo_error_handling():
    # Test that it gracefully handles non-string inputs
    assert extract_github_repo(123) is None
    assert extract_github_repo(["https://github.com/foo/bar"]) is None
    assert extract_github_repo({"url": "https://github.com/foo/bar"}) is None
