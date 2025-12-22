"""
User Storage Module
Simple file-based storage for user data (saved articles, preferences).
Works locally and in cloud environments.
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime


# Storage directory
STORAGE_DIR = os.path.join(os.path.dirname(__file__), '.user_data')


def _ensure_storage_dir():
    """Ensure storage directory exists."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def _get_user_file(telegram_id: int) -> str:
    """Get path to user's data file."""
    _ensure_storage_dir()
    return os.path.join(STORAGE_DIR, f"user_{telegram_id}.json")


def _load_user_data(telegram_id: int) -> Dict[str, Any]:
    """Load user data from file."""
    filepath = _get_user_file(telegram_id)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'telegram_id': telegram_id,
        'saved_articles': [],
        'preferences': {
            'language': 'en',
            'sources': ['hackernews', 'techcrunch', 'ai_blogs'],
            'schedule_time': '18:00'
        },
        'created_at': datetime.now().isoformat()
    }


def _save_user_data(telegram_id: int, data: Dict[str, Any]):
    """Save user data to file."""
    filepath = _get_user_file(telegram_id)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ SAVED ARTICLES ============

def save_article(telegram_id: int, title: str, url: str, source: str = "") -> bool:
    """
    Save an article for a user.
    
    Args:
        telegram_id: User's Telegram ID
        title: Article title
        url: Article URL
        source: News source name
        
    Returns:
        True if saved, False if already exists
    """
    data = _load_user_data(telegram_id)
    
    # Check if already saved
    for article in data['saved_articles']:
        if article['url'] == url:
            return False  # Already saved
    
    # Add new article
    data['saved_articles'].append({
        'title': title,
        'url': url,
        'source': source,
        'saved_at': datetime.now().isoformat()
    })
    
    # Keep only last 50 articles
    data['saved_articles'] = data['saved_articles'][-50:]
    
    _save_user_data(telegram_id, data)
    return True


def get_saved_articles(telegram_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get user's saved articles, most recent first."""
    data = _load_user_data(telegram_id)
    articles = data.get('saved_articles', [])
    return list(reversed(articles[-limit:]))


def delete_saved_article(telegram_id: int, url: str) -> bool:
    """Delete a saved article by URL."""
    data = _load_user_data(telegram_id)
    original_count = len(data['saved_articles'])
    data['saved_articles'] = [a for a in data['saved_articles'] if a['url'] != url]
    
    if len(data['saved_articles']) < original_count:
        _save_user_data(telegram_id, data)
        return True
    return False


def clear_saved_articles(telegram_id: int):
    """Clear all saved articles for a user."""
    data = _load_user_data(telegram_id)
    data['saved_articles'] = []
    _save_user_data(telegram_id, data)


# ============ USER PREFERENCES ============

def get_user_preferences(telegram_id: int) -> Dict[str, Any]:
    """Get user preferences."""
    data = _load_user_data(telegram_id)
    return data.get('preferences', {})


def set_user_preference(telegram_id: int, key: str, value: Any):
    """Set a user preference."""
    data = _load_user_data(telegram_id)
    if 'preferences' not in data:
        data['preferences'] = {}
    data['preferences'][key] = value
    _save_user_data(telegram_id, data)


def get_user_language(telegram_id: int) -> str:
    """Get user's preferred language from Firestore (with local fallback)."""
    # Try Firestore first (for cloud deployment)
    try:
        from google.cloud import firestore
        db = firestore.Client()
        doc = db.collection('user_preferences').document(str(telegram_id)).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('language', 'en')
    except Exception as e:
        # Firestore not available (local development) - fall back to file storage
        pass
    
    # Fall back to local file storage
    prefs = get_user_preferences(telegram_id)
    return prefs.get('language', 'en')


def set_user_language(telegram_id: int, language: str):
    """Set user's preferred language to Firestore (with local fallback)."""
    # Try Firestore first (for cloud deployment)
    try:
        from google.cloud import firestore
        db = firestore.Client()
        db.collection('user_preferences').document(str(telegram_id)).set({
            'language': language,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)
        print(f"Language set to {language} for user {telegram_id} in Firestore")
        return
    except Exception as e:
        # Firestore not available (local development) - fall back to file storage
        print(f"Firestore not available, using local storage: {e}")
    
    # Fall back to local file storage
    set_user_preference(telegram_id, 'language', language)


# ============ SEARCH HISTORY ============

def add_search_history(telegram_id: int, query: str):
    """Add a search query to history."""
    data = _load_user_data(telegram_id)
    if 'search_history' not in data:
        data['search_history'] = []
    
    data['search_history'].append({
        'query': query,
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only last 20 searches
    data['search_history'] = data['search_history'][-20:]
    _save_user_data(telegram_id, data)


def get_search_history(telegram_id: int, limit: int = 5) -> List[str]:
    """Get recent search queries."""
    data = _load_user_data(telegram_id)
    history = data.get('search_history', [])
    return [h['query'] for h in reversed(history[-limit:])]


# ============ ARTICLE RATINGS ============

def rate_article(telegram_id: int, article_url: str, rating: str) -> bool:
    """
    Rate an article (thumbs up/down).
    
    Args:
        telegram_id: User's Telegram ID
        article_url: URL of the article
        rating: 'up' or 'down'
        
    Returns:
        True if saved successfully
    """
    # Store in Firestore for analytics
    try:
        from google.cloud import firestore
        db = firestore.Client()
        
        # Store in user ratings collection
        db.collection('article_ratings').add({
            'telegram_id': telegram_id,
            'article_url': article_url,
            'rating': rating,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Error saving rating: {e}")
        # Fall back to local storage
        data = _load_user_data(telegram_id)
        if 'ratings' not in data:
            data['ratings'] = []
        data['ratings'].append({
            'url': article_url,
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        })
        data['ratings'] = data['ratings'][-100:]  # Keep last 100
        _save_user_data(telegram_id, data)
        return True


def get_article_stats(article_url: str) -> Dict[str, int]:
    """Get aggregated ratings for an article."""
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
        db = firestore.Client()
        
        ratings = db.collection('article_ratings')\
            .where(filter=FieldFilter('article_url', '==', article_url))\
            .stream()
        
        ups = downs = 0
        for r in ratings:
            data = r.to_dict()
            if data.get('rating') == 'up':
                ups += 1
            else:
                downs += 1
        
        return {'up': ups, 'down': downs}
    except Exception:
        return {'up': 0, 'down': 0}

