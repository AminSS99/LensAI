"""
Distributed Lock Module
Implements a Firestore-based distributed lock to prevent duplicate processing across Cloud Function instances.
"""

from datetime import datetime, timedelta
from typing import Optional


def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        from google.cloud import firestore
        return firestore.Client()
    except Exception:
        return None


class DistributedLock:
    """Firestore-based distributed lock with TTL."""
    
    def __init__(self, lock_name: str, user_id: int, ttl_seconds: int = 300):
        """
        Initialize a distributed lock.
        
        Args:
            lock_name: Name of the lock (e.g., 'news_generation')
            user_id: User ID to lock for
            ttl_seconds: Time-to-live in seconds (default 5 minutes)
        """
        self.lock_name = lock_name
        self.user_id = user_id
        self.ttl_seconds = ttl_seconds
        self.db = get_firestore_client()
        self.lock_id = f"{lock_name}_{user_id}"
        
    def acquire(self) -> bool:
        """
        Try to acquire the lock.
        
        Returns:
            True if lock acquired, False if already locked
        """
        if not self.db:
            # No Firestore, skip locking (local development)
            return True
            
        try:
            from google.cloud import firestore
            
            lock_ref = self.db.collection('locks').document(self.lock_id)
            lock_doc = lock_ref.get()
            
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.ttl_seconds)
            
            # Check if lock exists and is still valid
            if lock_doc.exists:
                lock_data = lock_doc.to_dict()
                lock_expires = lock_data.get('expires_at')
                
                if lock_expires and lock_expires.replace(tzinfo=None) > now:
                    # Lock is still valid - cannot acquire
                    return False
            
            # Either lock doesn't exist or has expired - acquire it
            lock_ref.set({
                'user_id': self.user_id,
                'lock_name': self.lock_name,
                'acquired_at': firestore.SERVER_TIMESTAMP,
                'expires_at': expires_at
            })
            
            return True
            
        except Exception as e:
            print(f"Lock acquire error: {e}")
            # On error, assume we can proceed (fail-open)
            return True
    
    def release(self):
        """Release the lock."""
        if not self.db:
            return
            
        try:
            lock_ref = self.db.collection('locks').document(self.lock_id)
            lock_ref.delete()
        except Exception as e:
            print(f"Lock release error: {e}")
    
    def __enter__(self):
        """Context manager enter."""
        if not self.acquire():
            raise LockAcquireError(f"Lock '{self.lock_name}' for user {self.user_id} is already held")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


class LockAcquireError(Exception):
    """Raised when lock cannot be acquired."""
    pass


def is_locked(lock_name: str, user_id: int) -> bool:
    """
    Check if a lock is currently held.
    
    Args:
        lock_name: Name of the lock
        user_id: User ID
        
    Returns:
        True if locked, False otherwise
    """
    db = get_firestore_client()
    if not db:
        return False
        
    try:
        lock_id = f"{lock_name}_{user_id}"
        lock_ref = db.collection('locks').document(lock_id)
        lock_doc = lock_ref.get()
        
        if not lock_doc.exists:
            return False
            
        lock_data = lock_doc.to_dict()
        lock_expires = lock_data.get('expires_at')
        
        if lock_expires and lock_expires.replace(tzinfo=None) > datetime.utcnow():
            return True
            
        return False
        
    except Exception:
        return False
