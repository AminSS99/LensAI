"""
Rate Limiting Module
Prevents abuse by limiting requests per user using Firestore for persistence.
"""

import time
from typing import Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
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

# Rate limit configurations
LIMITS = {
    'news': {'max': 5, 'window': 300},      # 5 per 5 minutes
    'search': {'max': 10, 'window': 60},    # 10 per minute
    'ai_chat': {'max': 5, 'window': 300},   # 5 per 5 minutes
    'save': {'max': 30, 'window': 60},      # 30 per minute
    'default': {'max': 30, 'window': 60}    # Default
}

def check_rate_limit(user_id: int, action: str = 'default') -> Tuple[bool, str]:
    """
    Check if user is rate limited for an action using Firestore.
    
    Args:
        user_id: User's Telegram ID
        action: Action type ('news', 'search', 'ai_chat', 'save', 'default')
        
    Returns:
        Tuple of (is_allowed, message)
    """
    db = get_firestore_client()
    
    # Fail open if no DB (local dev without creds)
    if not db:
        return True, "No database connection"
        
    config = LIMITS.get(action, LIMITS['default'])
    max_requests = config['max']
    window_seconds = config['window']
    
    # Document ID: rate_limit_{user_id}_{action}
    doc_id = f"rate_limit_{user_id}_{action}"
    doc_ref = db.collection('rate_limits').document(doc_id)
    
    try:
        if g_firestore is None:
            return True, "Firestore SDK unavailable"

        # Transactional update to ensure consistency
        @g_firestore.transactional
        def update_rate_limit(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            now_ts = time.time()
            window_start = now_ts - window_seconds
            
            timestamps = []
            
            if snapshot.exists:
                data = snapshot.to_dict()
                # Filter old timestamps
                timestamps = [ts for ts in data.get('timestamps', []) if ts > window_start]
            
            # Check limit
            current_count = len(timestamps)
            
            if current_count >= max_requests:
                # Calculate wait time
                if timestamps:
                    oldest = min(timestamps)
                    wait_time = int(oldest + window_seconds - now_ts)
                    return False, wait_time
                return False, window_seconds
            
            # Add new request
            timestamps.append(now_ts)
            
            # Update document with TTL (expires_at for potential cleanup)
            transaction.set(doc_ref, {
                'timestamps': timestamps,
                'user_id': user_id,
                'action': action,
                'updated_at': datetime.utcnow()
            })
            
            return True, max_requests - len(timestamps)

        # Run transaction
        trans = db.transaction()
        allowed, result = update_rate_limit(trans, doc_ref)
        
        if not allowed:
            return False, f"Rate limit reached. Please wait {result} seconds."
            
        return True, f"Remaining: {result}"
        
    except Exception as e:
        print(f"Rate limit error: {e}")
        # Fail closed for high-abuse actions.
        if action in {"news", "search", "ai_chat", "save"}:
            return False, "Rate limit check failed. Please try again in 30 seconds."
        return True, "Error checking limit"


def reset_limits(user_id: int):
    """Reset all limits for a user (admin only)."""
    db = get_firestore_client()
    if not db:
        return
        
    try:
        # Find all rate limit docs for this user
        docs = db.collection('rate_limits').where('user_id', '==', user_id).stream()
        
        batch = db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            
        if count > 0:
            batch.commit()
            print(f"Reset {count} rate limit counters for user {user_id}")
            
    except Exception as e:
        print(f"Error resetting limits: {e}")

