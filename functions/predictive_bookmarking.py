"""
Predictive Bookmarking Module
Predicts which articles a user will want to save based on their historical preferences.
Leverages existing user_profile weights (source_weights, topic_weights).
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

try:
    from google.cloud import firestore
except Exception:
    firestore = None

from .user_storage import get_firestore_client
from .topic_clustering import extract_topic


def _get_db():
    return get_firestore_client()


def get_user_profile(user_id: int) -> Dict[str, Any]:
    """Fetch user's preference profile with source/topic weights."""
    db = _get_db()
    if not db:
        return {}
    try:
        doc = db.collection('user_profiles').document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict() or {}
    except Exception as e:
        print(f"Error fetching user profile: {e}")
    return {}


def score_article_for_user(user_id: int, article: Dict[str, Any]) -> float:
    """
    Score an article from 0.0 to 1.0 based on how likely the user is to save it.
    Uses topic weights, source weights, and recency factors.
    """
    profile = get_user_profile(user_id)
    if not profile:
        return 0.0

    source_weights = profile.get('source_weights', {})
    topic_weights = profile.get('topic_weights', {})
    feedback_count = int(profile.get('feedback_count', 0))

    # Not enough data to make good predictions
    if feedback_count < 3:
        return 0.0

    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', 'Unknown')
    topic = extract_topic(title, url)

    score = 0.0

    # Source affinity (normalized to roughly 0-0.4 range)
    src_w = float(source_weights.get(source, 0.0))
    score += max(0.0, min(0.4, (src_w + 8.0) / 40.0))

    # Topic affinity (normalized to roughly 0-0.4 range)
    top_w = float(topic_weights.get(topic, 0.0))
    score += max(0.0, min(0.4, (top_w + 8.0) / 40.0))

    # Bonus for articles from sources the user explicitly keeps enabled
    # (already reflected in source_weights but give a small nudge)
    if src_w > 2.0:
        score += 0.1
    if top_w > 2.0:
        score += 0.1

    return min(1.0, score)


def predict_saves_for_user(user_id: int, articles: List[Dict[str, Any]], top_n: int = 3, threshold: float = 0.35) -> List[Dict[str, Any]]:
    """
    Return the top N articles predicted to be saved by the user.
    Only includes articles scoring above the threshold.
    """
    scored = []
    for article in articles:
        s = score_article_for_user(user_id, article)
        if s >= threshold:
            scored.append({**article, '_predicted_score': round(s, 2)})

    scored.sort(key=lambda x: x['_predicted_score'], reverse=True)
    return scored[:top_n]


def format_predicted_saves(predicted: List[Dict[str, Any]], lang: str = 'en') -> str:
    """Format a short message with predicted saves for inline keyboard use."""
    if not predicted:
        return ""

    if lang == 'ru':
        lines = ["🔮 *Вам может понравиться:*"]
    else:
        lines = ["🔮 *You might like:*"]

    for i, article in enumerate(predicted, 1):
        title = article.get('title', 'Untitled')[:50]
        score = article.get('_predicted_score', 0)
        lines.append(f"{i}. {title} `({score})`")

    return "\n".join(lines)


def record_prediction_interaction(user_id: int, article_hash: str, action: str):
    """
    Record whether a user accepted or ignored a prediction.
    action: 'accepted' or 'ignored'
    """
    db = _get_db()
    if not db:
        return
    try:
        db.collection('prediction_feedback').add({
            'user_id': user_id,
            'article_hash': article_hash,
            'action': action,
            'timestamp': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
        })
    except Exception as e:
        print(f"Error recording prediction feedback: {e}")


def store_predicted_articles(articles: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Store predicted articles temporarily for callback retrieval.
    Returns a dict mapping url_hash -> article title for button labels.
    """
    db = _get_db()
    if not db:
        return {}

    from .security_utils import stable_hash
    mapping = {}
    try:
        batch = db.batch()
        for article in articles:
            url = article.get('url', '')
            if not url:
                continue
            url_hash = stable_hash(url)[:8]
            doc_ref = db.collection('predicted_articles_temp').document(url_hash)
            batch.set(doc_ref, {
                'title': article.get('title', 'Untitled')[:100],
                'url': url,
                'source': article.get('source', ''),
                'created_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc).timestamp() + (24 * 3600),
            }, merge=True)
            mapping[url_hash] = article.get('title', 'Untitled')[:30]
        batch.commit()
    except Exception as e:
        print(f"Error storing predicted articles: {e}")
    return mapping


def get_prediction_accuracy(user_id: int, days: int = 7) -> Dict[str, Any]:
    """Get prediction accuracy stats for a user."""
    db = _get_db()
    if not db:
        return {'accuracy': 0.0, 'total': 0}
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        docs = db.collection('prediction_feedback')\
            .where('user_id', '==', user_id)\
            .where('timestamp', '>=', cutoff)\
            .stream()

        accepted = 0
        total = 0
        for doc in docs:
            data = doc.to_dict()
            total += 1
            if data.get('action') == 'accepted':
                accepted += 1

        accuracy = round(accepted / total, 2) if total > 0 else 0.0
        return {'accuracy': accuracy, 'total': total, 'accepted': accepted}
    except Exception as e:
        print(f"Error getting prediction accuracy: {e}")
        return {'accuracy': 0.0, 'total': 0}
