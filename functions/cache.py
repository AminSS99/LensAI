"""
Caching Module
Firestore-based cache with TTL for news digests.
"""

import time
from typing import Any, Optional, List
from datetime import datetime, timezone
from functions.security_utils import stable_hash
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        from google.cloud import firestore as firestore_module
        import os
        project_id = os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return firestore_module.Client(project=project_id)
        return firestore_module.Client()
    except Exception:
        return None


def build_digest_cache_key(language: str = "en", sources: Optional[List[str]] = None, scope: str = "global") -> str:
    """
    Build a deterministic cache key for digest variants.
    
    Args:
        language: User language code
        sources: Enabled source list
        scope: Optional segment (e.g., "news", "scheduled")
    """
    normalized_sources = ",".join(sorted((sources or [])))
    payload = f"{scope}|{language}|{normalized_sources}"
    suffix = stable_hash(payload)[:16]
    return f"news_digest_{suffix}"


def get_cached_digest(cache_key: str = "news_digest") -> Optional[str]:
    """Get cached news digest if available and valid."""
    db = get_firestore_client()
    if not db:
        return None
        
    try:
        doc = db.collection('cache').document(cache_key).get()
        if not doc.exists:
            return None
            
        data = doc.to_dict()
        expiry = data.get('expires_at', 0)
        
        if time.time() < expiry:
            return data.get('content')
            
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None


def set_cached_digest(digest: str, ttl_minutes: int = 15, cache_key: str = "news_digest"):
    """
    Cache news digest in Firestore.
    Default TTL is 15 minutes.
    """
    db = get_firestore_client()
    if not db:
        return
        
    try:
        now_ts = time.time()
        expiry = now_ts + (ttl_minutes * 60)
        
        db.collection('cache').document(cache_key).set({
            'content': digest,
            'expires_at': expiry,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'cache_key': cache_key,
            'updated_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now()
        })
    except Exception as e:
        print(f"Cache set error: {e}")


def get_digest_timestamp(cache_key: str = "news_digest") -> Optional[str]:
    """Get when the cached digest was created."""
    db = get_firestore_client()
    if not db:
        return None
        
    try:
        doc = db.collection('cache').document(cache_key).get()
        if doc.exists:
            data = doc.to_dict()
            if time.time() < data.get('expires_at', 0):
                return data.get('created_at')
        return None
    except Exception:
        return None


def is_digest_cached(cache_key: str = "news_digest") -> bool:
    """Check if we have a valid cached digest."""
    return get_cached_digest(cache_key=cache_key) is not None


def clear_cached_digest(cache_key: str = "news_digest"):
    """
    Clear cached digest(s).
    
    Set cache_key="*" to clear all cache docs.
    """
    db = get_firestore_client()
    if not db:
        return
    try:
        if cache_key == "*":
            for doc in db.collection('cache').stream():
                doc.reference.delete()
            return
        db.collection('cache').document(cache_key).delete()
    except Exception as e:
        print(f"Cache clear error: {e}")
