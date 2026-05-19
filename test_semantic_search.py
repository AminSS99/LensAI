import pytest
from functions.semantic_search import _expand_query_terms

def test_expand_query_terms_empty():
    assert _expand_query_terms("") == set()
    assert _expand_query_terms(None) == set()

def test_expand_query_terms_no_synonyms():
    assert _expand_query_terms("hello world") == {"hello", "world"}

def test_expand_query_terms_with_synonyms():
    # 'ai' expands to multiple words
    expanded = _expand_query_terms("ai news")
    expected = {"ai", "news", "artificial intelligence", "llm", "gpt", "model", "machine learning"}
    assert expanded == expected

def test_expand_query_terms_multiple_synonyms():
    expanded = _expand_query_terms("startup crypto")
    expected = {"startup", "crypto", "funding", "vc", "investment", "series a", "series b", "bitcoin", "ethereum", "blockchain", "web3", "defi"}
    assert expanded == expected

def test_expand_query_terms_case_insensitive():
    expanded = _expand_query_terms("AI NeWs")
    expected = {"ai", "news", "artificial intelligence", "llm", "gpt", "model", "machine learning"}
    assert expanded == expected

def test_expand_query_terms_ignores_short_words():
    # 'a' is length 1, so ignored by _tokenize
    assert _expand_query_terms("a startup") == {"startup", "funding", "vc", "investment", "series a", "series b"}
