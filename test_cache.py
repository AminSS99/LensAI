import pytest
from functions.cache import build_digest_cache_key
from functions.security_utils import stable_hash

def test_build_digest_cache_key_defaults():
    key = build_digest_cache_key()
    assert key.startswith("news_digest_")

    # Calculate the expected hash
    payload = "global|en|"
    expected_suffix = stable_hash(payload)[:16]
    assert key == f"news_digest_{expected_suffix}"

def test_build_digest_cache_key_custom_args():
    sources = ["techcrunch", "hackernews"]
    key = build_digest_cache_key(language="ru", sources=sources, scope="scheduled")

    # Calculate expected hash
    # sources are sorted, so "hackernews,techcrunch"
    payload = "scheduled|ru|hackernews,techcrunch"
    expected_suffix = stable_hash(payload)[:16]
    assert key == f"news_digest_{expected_suffix}"

def test_build_digest_cache_key_empty_sources():
    key = build_digest_cache_key(sources=[])
    payload = "global|en|"
    expected_suffix = stable_hash(payload)[:16]
    assert key == f"news_digest_{expected_suffix}"

def test_build_digest_cache_key_sorting():
    key1 = build_digest_cache_key(sources=["a", "b", "c"])
    key2 = build_digest_cache_key(sources=["c", "a", "b"])
    assert key1 == key2
