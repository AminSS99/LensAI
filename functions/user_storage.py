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
    """Get user's preferred language."""
    prefs = get_user_preferences(telegram_id)
    return prefs.get('language', 'en')


def set_user_language(telegram_id: int, language: str):
    """Set user's preferred language."""
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
