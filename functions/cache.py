"""
Caching Module
Firestore-based cache with TTL for news digests.
"""

import time
from typing import Any, Optional
from datetime import datetime
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        from google.cloud import firestore
        return firestore.Client()
    except Exception:
        return None

def get_cached_digest() -> Optional[str]:
    """Get cached news digest if available and valid."""
    db = get_firestore_client()
    if not db:
        return None
        
    try:
        doc = db.collection('cache').document('news_digest').get()
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


def set_cached_digest(digest: str, ttl_minutes: int = 15):
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
        
        db.collection('cache').document('news_digest').set({
            'content': digest,
            'expires_at': expiry,
            'created_at': datetime.now().isoformat(),
            'updated_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now()
        })
    except Exception as e:
        print(f"Cache set error: {e}")


def get_digest_timestamp() -> Optional[str]:
    """Get when the cached digest was created."""
    db = get_firestore_client()
    if not db:
        return None
        
    try:
        doc = db.collection('cache').document('news_digest').get()
        if doc.exists:
            data = doc.to_dict()
            if time.time() < data.get('expires_at', 0):
                return data.get('created_at')
        return None
    except Exception:
        return None


def is_digest_cached() -> bool:
    """Check if we have a valid cached digest."""
    return get_cached_digest() is not None
