"""
Firestore Database Module
Handles all database operations for users, articles, and digests.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.oauth2 import service_account


def get_db() -> firestore.Client:
    """Get Firestore client."""
    # In Cloud Functions, this uses default credentials
    # For local development, set GOOGLE_APPLICATION_CREDENTIALS env var
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
    schedule_time: str = None,
    timezone: str = "Asia/Baku"
) -> Dict[str, Any]:
    """
    Create or update a user.
    
    Args:
        telegram_id: User's Telegram ID
        username: Telegram username
        schedule_time: Time for daily digest (HH:MM format)
        timezone: User's timezone
        
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
        if schedule_time:
            update_data['schedule_time'] = schedule_time
        if timezone:
            update_data['timezone'] = timezone
        
        user_ref.update(update_data)
        return {**existing.to_dict(), **update_data}
    else:
        # Create new user
        user_data = {
            'telegram_id': telegram_id,
            'username': username,
            'schedule_time': schedule_time or "18:00",
            'timezone': timezone,
            'sources': ['hackernews', 'techcrunch', 'ai_blogs'],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'is_active': True
        }
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
        'updated_at': datetime.utcnow()
    })
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
    user = user_ref.get().to_dict()
    
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
        doc_id = str(hash(url))
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
