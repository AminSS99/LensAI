"""
Caching Module
Simple in-memory cache with TTL for news digests.
"""

import time
from typing import Any, Optional
from datetime import datetime


class Cache:
    """Simple in-memory cache with time-to-live (TTL)."""
    
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                # Expired, remove it
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set value in cache with TTL (default 5 minutes)."""
        expiry = time.time() + ttl_seconds
        self._cache[key] = (value, expiry)
    
    def clear(self):
        """Clear all cached values."""
        self._cache = {}
    
    def is_valid(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None


# Global cache instance
_cache = Cache()


def get_cached_digest() -> Optional[str]:
    """Get cached news digest if available."""
    return _cache.get('news_digest')


def set_cached_digest(digest: str, ttl_minutes: int = 15):
    """
    Cache news digest.
    Default TTL is 15 minutes - news doesn't change that fast.
    """
    _cache.set('news_digest', digest, ttl_seconds=ttl_minutes * 60)
    _cache.set('digest_timestamp', datetime.now().isoformat(), ttl_seconds=ttl_minutes * 60)


def get_digest_timestamp() -> Optional[str]:
    """Get when the cached digest was created."""
    return _cache.get('digest_timestamp')


def is_digest_cached() -> bool:
    """Check if we have a valid cached digest."""
    return _cache.is_valid('news_digest')
