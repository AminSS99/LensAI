"""
Firestore Database Module
Handles all database operations for users, articles, and digests.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from .security_utils import stable_hash


_UNSET = object()


def get_firestore_project_id() -> Optional[str]:
    """
    Resolve Firestore project ID from environment.
    
    Prefers FIRESTORE_PROJECT_ID, then GOOGLE_CLOUD_PROJECT.
    """
    return os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")


def get_db() -> firestore.Client:
    """Get Firestore client."""
    # In Cloud Functions, this uses default credentials
    # For local development, set GOOGLE_APPLICATION_CREDENTIALS env var
    project_id = get_firestore_project_id()
    if project_id:
        return firestore.Client(project=project_id)
    return firestore.Client()


# ============ USER OPERATIONS ============

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram ID."""
    db = get_db()
    doc = db.collection('users').document(str(telegram_id)).get()
    return doc.to_dict() if doc.exists else None


def create_or_update_user(
    telegram_id: int,
    username: str = None,
    schedule_time: Any = _UNSET,
    timezone: Optional[str] = None,
    is_active: Optional[bool] = None,
    quiet_hours: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create or update a user.
    
    Args:
        telegram_id: User's Telegram ID
        username: Telegram username
        schedule_time: Time for daily digest (HH:MM format), None to disable
        timezone: User's timezone
        is_active: Explicit active state override
        quiet_hours: Optional dict with keys start/end (HH:MM)
        
    Returns:
        User document data
    """
    db = get_db()
    user_ref = db.collection('users').document(str(telegram_id))
    
    # Check if user exists
    existing = user_ref.get()
    
    if existing.exists:
        # Update existing user
        update_data = {'updated_at': datetime.utcnow()}
        if username:
            update_data['username'] = username
        if schedule_time is not _UNSET:
            update_data['schedule_time'] = schedule_time
            if is_active is None:
                update_data['is_active'] = bool(schedule_time)
        if timezone is not None:
            update_data['timezone'] = timezone
        if is_active is not None:
            update_data['is_active'] = is_active
        if quiet_hours is not None:
            update_data['quiet_hours'] = quiet_hours
        
        user_ref.update(update_data)
        return {**existing.to_dict(), **update_data}
    else:
        # Create new user
        resolved_schedule = "18:00" if schedule_time is _UNSET else schedule_time
        resolved_timezone = timezone or "Asia/Baku"
        resolved_active = bool(resolved_schedule) if is_active is None else is_active
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'schedule_time': resolved_schedule,
            'timezone': resolved_timezone,
            'sources': ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github', 'producthunt'],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'is_active': resolved_active
        }
        if quiet_hours is not None:
            user_data['quiet_hours'] = quiet_hours
        user_ref.set(user_data)
        return user_data


def set_user_schedule(telegram_id: int, schedule_time: str) -> bool:
    """
    Set user's daily digest time.
    
    Args:
        telegram_id: User's Telegram ID
        schedule_time: Time in HH:MM format
        
    Returns:
        True if successful
    """
    db = get_db()
    user_ref = db.collection('users').document(str(telegram_id))
    
    user_ref.update({
        'schedule_time': schedule_time,
        'is_active': bool(schedule_time),
        'updated_at': datetime.utcnow()
    })
    return True


def set_user_timezone(telegram_id: int, timezone_name: str) -> bool:
    """Set user's timezone string (IANA format, e.g., Europe/Berlin)."""
    db = get_db()
    user_ref = db.collection('users').document(str(telegram_id))
    user_ref.set({
        'timezone': timezone_name,
        'updated_at': datetime.utcnow()
    }, merge=True)
    return True


def set_user_quiet_hours(telegram_id: int, quiet_hours: Optional[Dict[str, str]]) -> bool:
    """
    Set quiet hours for a user.
    
    quiet_hours format:
      {'start': '23:00', 'end': '07:00'}
    or None to disable.
    """
    db = get_db()
    user_ref = db.collection('users').document(str(telegram_id))
    user_ref.set({
        'quiet_hours': quiet_hours,
        'updated_at': datetime.utcnow()
    }, merge=True)
    return True


def get_users_for_time(schedule_time: str) -> List[Dict[str, Any]]:
    """
    Get all users who should receive digest at a given time.
    
    Args:
        schedule_time: Time in HH:MM format
        
    Returns:
        List of users scheduled for this time
    """
    db = get_db()
    users = db.collection('users')\
        .where(filter=FieldFilter('schedule_time', '==', schedule_time))\
        .where(filter=FieldFilter('is_active', '==', True))\
        .stream()
    
    return [user.to_dict() for user in users]


def get_all_active_users() -> List[Dict[str, Any]]:
    """
    Get ALL active users regardless of schedule time.
    Used for one-time notifications and broadcasts.
    
    Returns:
        List of all active users
    """
    db = get_db()
    users = db.collection('users')\
        .where(filter=FieldFilter('is_active', '==', True))\
        .stream()
    
    return [user.to_dict() for user in users]


def toggle_user_source(telegram_id: int, source: str) -> List[str]:
    """
    Toggle a news source for a user.
    
    Args:
        telegram_id: User's Telegram ID
        source: Source name to toggle
        
    Returns:
        Updated list of sources
    """
    db = get_db()
    user_ref = db.collection('users').document(str(telegram_id))
    user_doc = user_ref.get()
    user = user_doc.to_dict() if user_doc.exists else None
    if not user:
        user = create_or_update_user(telegram_id)
    
    sources = user.get('sources', [])
    
    if source in sources:
        sources.remove(source)
    else:
        sources.append(source)
    
    user_ref.update({
        'sources': sources,
        'updated_at': datetime.utcnow()
    })
    
    return sources


# ============ ARTICLE OPERATIONS ============

def save_articles(articles: List[Dict[str, Any]]) -> int:
    """
    Save articles to database (for caching/deduplication).
    
    Args:
        articles: List of article dicts
        
    Returns:
        Number of new articles saved
    """
    db = get_db()
    batch = db.batch()
    new_count = 0
    
    for article in articles:
        url = article.get('url', '')
        if not url:
            continue
        
        # Use URL hash as document ID for deduplication
        doc_id = stable_hash(url)
        doc_ref = db.collection('articles').document(doc_id)
        
        # Check if already exists
        if not doc_ref.get().exists:
            article_data = {
                **article,
                'fetched_at': datetime.utcnow()
            }
            batch.set(doc_ref, article_data)
            new_count += 1
    
    batch.commit()
    return new_count


def get_recent_articles(hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recently fetched articles.
    
    Args:
        hours: How many hours back to look
        limit: Maximum articles to return
        
    Returns:
        List of articles
    """
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    articles = db.collection('articles')\
        .where(filter=FieldFilter('fetched_at', '>=', cutoff))\
        .order_by('fetched_at', direction=firestore.Query.DESCENDING)\
        .limit(limit)\
        .stream()
    
    return [article.to_dict() for article in articles]


# ============ DIGEST OPERATIONS ============

def save_digest(telegram_id: int, content: str) -> str:
    """
    Save a sent digest for history.
    
    Args:
        telegram_id: User's Telegram ID
        content: Digest content
        
    Returns:
        Digest document ID
    """
    db = get_db()
    digest_ref = db.collection('digests').document()
    
    digest_ref.set({
        'user_id': telegram_id,
        'content': content,
        'sent_at': datetime.utcnow()
    })
    
    return digest_ref.id


def get_user_digests(telegram_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent digests for a user."""
    db = get_db()
    
    digests = db.collection('digests')\
        .where(filter=FieldFilter('user_id', '==', telegram_id))\
        .order_by('sent_at', direction=firestore.Query.DESCENDING)\
        .limit(limit)\
        .stream()
    
    return [digest.to_dict() for digest in digests]


# ============ CLEANUP OPERATIONS ============

def cleanup_old_articles(days: int = 7) -> int:
    """
    Delete articles older than specified days.
    
    Args:
        days: Delete articles older than this
        
    Returns:
        Number of deleted articles
    """
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    old_articles = db.collection('articles')\
        .where(filter=FieldFilter('fetched_at', '<', cutoff))\
        .stream()
    
    batch = db.batch()
    count = 0
    
    for article in old_articles:
        batch.delete(article.reference)
        count += 1
        
        # Firestore batch limit is 500
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
    
    if count % 400 != 0:
        batch.commit()
    
    return count
