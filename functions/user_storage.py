"""
User Storage Module
Handles storing user data (saved articles, preferences) in Firestore.
Falls back to local file storage for development if Firestore is unavailable.
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Local storage directory (fallback)
STORAGE_DIR = os.path.join(os.path.dirname(__file__), '.user_data')


def _ensure_storage_dir():
    """Ensure storage directory exists."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)


def _get_user_file(telegram_id: int) -> str:
    """Get path to user's local data file."""
    _ensure_storage_dir()
    return os.path.join(STORAGE_DIR, f"user_{telegram_id}.json")


def _load_local_data(telegram_id: int) -> Dict[str, Any]:
    """Load user data from local file."""
    filepath = _get_user_file(telegram_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
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


def _save_local_data(telegram_id: int, data: Dict[str, Any]):
    """Save user data to local file."""
    filepath = _get_user_file(telegram_id)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ FIRESTORE HELPERS ============

def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        from google.cloud import firestore
        return firestore.Client()
    except Exception:
        return None


# ============ ARTICLE CATEGORIES ============

CATEGORY_KEYWORDS = {
    'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning', 'neural', 'gpt', 'llm', 'openai', 'anthropic', 'deepmind', 'mistral', 'gemini', 'claude', 'chatgpt', 'transformer', 'diffusion'],
    'security': ['security', 'hack', 'breach', 'vulnerability', 'cyber', 'malware', 'ransomware', 'privacy', 'encryption', 'exploit', 'attack'],
    'crypto': ['crypto', 'bitcoin', 'ethereum', 'blockchain', 'web3', 'nft', 'defi', 'token', 'wallet'],
    'startups': ['startup', 'funding', 'series a', 'series b', 'vc', 'venture', 'unicorn', 'valuation', 'raised', 'investment'],
    'hardware': ['hardware', 'chip', 'cpu', 'gpu', 'nvidia', 'amd', 'intel', 'apple silicon', 'processor', 'semiconductor', 'device'],
    'software': ['software', 'app', 'update', 'release', 'version', 'feature', 'tool', 'platform', 'saas']
}

def categorize_article(title: str, url: str = "") -> str:
    """
    Auto-detect article category based on title and URL.
    """
    text = (title + " " + url).lower()
    
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return 'tech'


# ============ SAVED ARTICLES ============

def save_article(telegram_id: int, title: str, url: str, source: str = "", category: str = "") -> bool:
    """
    Save an article for a user to Firestore (or local).
    """
    # Auto-detect category
    if not category:
        category = categorize_article(title, url)

    article_data = {
        'title': title,
        'url': url,
        'source': source,
        'category': category,
        'saved_at': datetime.now().isoformat()
    }
    
    # Try Firestore
    db = get_firestore_client()
    if db:
        try:
            # Use a subcollection 'saved_articles' inside the user document
            doc_ref = db.collection('users').document(str(telegram_id)).collection('saved_articles').document(str(hash(url)))
            
            # Check if exists
            if doc_ref.get().exists:
                return False
                
            doc_ref.set(article_data)
            return True
        except Exception as e:
            print(f"Firestore save error: {e}")
            # Fall through to local
            
    # Fallback to local
    data = _load_local_data(telegram_id)
    
    for article in data.get('saved_articles', []):
        if article['url'] == url:
            return False
    
    if 'saved_articles' not in data:
        data['saved_articles'] = []
        
    data['saved_articles'].append(article_data)
    # Keep last 50 locally
    data['saved_articles'] = data['saved_articles'][-50:]
    
    _save_local_data(telegram_id, data)
    return True


def get_saved_articles(telegram_id: int, limit: int = 10, category: str = None) -> List[Dict[str, Any]]:
    """Get user's saved articles from Firestore (or local)."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            from google.cloud.firestore_v1.base_query import FieldFilter
            
            query = db.collection('users').document(str(telegram_id)).collection('saved_articles')
            
            if category:
                query = query.where(filter=FieldFilter('category', '==', category))
                
            # Order by saved_at desc
            docs = query.order_by('saved_at', direction=firestore.Query.DESCENDING).limit(limit).stream()
            
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Firestore get error: {e}")
            # Fall through
            
    # Fallback to local
    data = _load_local_data(telegram_id)
    articles = data.get('saved_articles', [])
    
    if category:
        articles = [a for a in articles if a.get('category', 'tech') == category]
        
    return list(reversed(articles[-limit:]))


def delete_saved_article(telegram_id: int, url: str) -> bool:
    """Delete a saved article by URL."""
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection('users').document(str(telegram_id)).collection('saved_articles').document(str(hash(url)))
            doc_ref.delete()
            return True
        except Exception as e:
            print(f"Firestore delete error: {e}")
            
    # Fallback to local
    data = _load_local_data(telegram_id)
    original_count = len(data.get('saved_articles', []))
    data['saved_articles'] = [a for a in data.get('saved_articles', []) if a['url'] != url]
    
    if len(data['saved_articles']) < original_count:
        _save_local_data(telegram_id, data)
        return True
    return False


def clear_saved_articles(telegram_id: int):
    """Clear all saved articles for a user."""
    db = get_firestore_client()
    if db:
        try:
            docs = db.collection('users').document(str(telegram_id)).collection('saved_articles').list_documents()
            for doc in docs:
                doc.delete()
            return
        except Exception as e:
            print(f"Firestore clear error: {e}")
            
    # Fallback to local
    data = _load_local_data(telegram_id)
    data['saved_articles'] = []
    _save_local_data(telegram_id, data)


# ============ USER PREFERENCES ============

def get_user_preferences(telegram_id: int) -> Dict[str, Any]:
    """Get user preferences."""
    # Try Firestore
    db = get_firestore_client()
    if db:
        try:
            doc = db.collection('users').document(str(telegram_id)).get()
            if doc.exists:
                return doc.to_dict()
        except Exception:
            pass
            
    data = _load_local_data(telegram_id)
    return data.get('preferences', {})


def set_user_preference(telegram_id: int, key: str, value: Any):
    """Set a user preference."""
    # Try Firestore
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            db.collection('users').document(str(telegram_id)).set({
                key: value,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            return
        except Exception:
            pass
            
    data = _load_local_data(telegram_id)
    if 'preferences' not in data:
        data['preferences'] = {}
    data['preferences'][key] = value
    _save_local_data(telegram_id, data)


def get_user_language(telegram_id: int) -> str:
    """Get user's preferred language."""
    # Try Firestore directly first (most common path)
    db = get_firestore_client()
    if db:
        try:
            doc = db.collection('user_preferences').document(str(telegram_id)).get()
            if doc.exists:
                return doc.to_dict().get('language', 'en')
        except Exception:
            pass
            
    prefs = get_user_preferences(telegram_id)
    return prefs.get('language', 'en')


def set_user_language(telegram_id: int, language: str):
    """Set user's preferred language."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            db.collection('user_preferences').document(str(telegram_id)).set({
                'language': language,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            return
        except Exception:
            pass
            
    set_user_preference(telegram_id, 'language', language)


# ============ SEARCH HISTORY ============

def add_search_history(telegram_id: int, query: str):
    """Add a search query to history."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            db.collection('users').document(str(telegram_id)).collection('search_history').add({
                'query': query,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            return
        except Exception:
            pass

    data = _load_local_data(telegram_id)
    if 'search_history' not in data:
        data['search_history'] = []
    
    data['search_history'].append({
        'query': query,
        'timestamp': datetime.now().isoformat()
    })
    data['search_history'] = data['search_history'][-20:]
    _save_local_data(telegram_id, data)


def get_search_history(telegram_id: int, limit: int = 5) -> List[str]:
    """Get recent search queries."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            docs = db.collection('users').document(str(telegram_id)).collection('search_history')\
                .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()
            return [doc.to_dict().get('query') for doc in docs]
        except Exception:
            pass

    data = _load_local_data(telegram_id)
    history = data.get('search_history', [])
    return [h['query'] for h in reversed(history[-limit:])]


# ============ ARTICLE RATINGS ============

def rate_article(telegram_id: int, article_url: str, rating: str) -> bool:
    """Rate an article (thumbs up/down)."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud import firestore
            db.collection('article_ratings').add({
                'telegram_id': telegram_id,
                'article_url': article_url,
                'rating': rating,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception:
            pass
            
    data = _load_local_data(telegram_id)
    if 'ratings' not in data:
        data['ratings'] = []
        
    data['ratings'].append({
        'url': article_url,
        'rating': rating,
        'timestamp': datetime.now().isoformat()
    })
    data['ratings'] = data['ratings'][-100:]
    _save_local_data(telegram_id, data)
    return True


def get_article_stats(article_url: str) -> Dict[str, int]:
    """Get aggregated ratings for an article."""
    db = get_firestore_client()
    if db:
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
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
            pass
            
    return {'up': 0, 'down': 0}

