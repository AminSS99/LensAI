"""
Distributed Lock Module
Implements a Firestore-based distributed lock to prevent duplicate processing across Cloud Function instances.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
try:
    from google.cloud import firestore as g_firestore
except Exception:
    g_firestore = None


def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        if g_firestore is None:
            return None
        import os
        project_id = os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return g_firestore.Client(project=project_id)
        return g_firestore.Client()
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
            lock_ref = self.db.collection('locks').document(self.lock_id)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=self.ttl_seconds)

            if g_firestore is None:
                return False

            @g_firestore.transactional
            def acquire_transaction(transaction, ref):
                snap = ref.get(transaction=transaction)
                if snap.exists:
                    data = snap.to_dict()
                    lock_expires = data.get('expires_at')
                    if lock_expires:
                        try:
                            # Handle both offset-aware and naive datetimes
                            if lock_expires.tzinfo is None:
                                lock_expires = lock_expires.replace(tzinfo=timezone.utc)
                            if lock_expires > now:
                                return False
                        except Exception:
                            return False

                transaction.set(ref, {
                    'user_id': self.user_id,
                    'lock_name': self.lock_name,
                    'acquired_at': g_firestore.SERVER_TIMESTAMP,
                    'expires_at': expires_at,
                    'updated_at': g_firestore.SERVER_TIMESTAMP
                })
                return True

            transaction = self.db.transaction()
            return acquire_transaction(transaction, lock_ref)
            
        except Exception as e:
            print(f"Lock acquire error: {e}")
            # Fail closed in production to avoid duplicate processing.
            return False
    
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


def cleanup_expired_locks() -> int:
    """
    Remove expired lock documents from Firestore.
    Returns the number of deleted documents.
    """
    db = get_firestore_client()
    if not db:
        return 0

    try:
        now = datetime.now(timezone.utc)
        docs = db.collection('locks').stream()
        batch = db.batch()
        count = 0

        for doc in docs:
            data = doc.to_dict()
            expires = data.get('expires_at')
            if not expires:
                continue
            try:
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires < now:
                    batch.delete(doc.reference)
                    count += 1
                    if count % 400 == 0:
                        batch.commit()
                        batch = db.batch()
            except Exception:
                continue

        if count % 400 != 0:
            batch.commit()

        return count
    except Exception as e:
        print(f"Lock cleanup error: {e}")
        return 0


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

        if lock_expires:
            try:
                if lock_expires.tzinfo is None:
                    lock_expires = lock_expires.replace(tzinfo=timezone.utc)
                if lock_expires > datetime.now(timezone.utc):
                    return True
            except Exception:
                return False
            
        return False
        
    except Exception:
        return False
