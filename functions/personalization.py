"""
Personalization Module
Learns simple user topic/source preferences from digest ratings
and uses them to rank candidate articles.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


def get_firestore_client():
    """Get Firestore client or None if unavailable."""
    try:
        from google.cloud import firestore
        import os
        project_id = os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return firestore.Client(project=project_id)
        return firestore.Client()
    except Exception:
        return None


def _get_topic(article: Dict[str, Any]) -> str:
    """Infer a topic label for an article."""
    topic = article.get("topic")
    if topic:
        return topic
    try:
        from .topic_clustering import extract_topic
        return extract_topic(article.get("title", ""), article.get("url", ""))
    except Exception:
        return "general"


def _get_source(article: Dict[str, Any]) -> str:
    """Normalize source name."""
    source = article.get("source", "Unknown")
    return source.strip() or "Unknown"


def rank_articles_for_user(telegram_id: int, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank articles using stored per-user preferences.
    
    If profile doesn't exist, returns original order.
    """
    if not articles:
        return []

    db = get_firestore_client()
    if not db:
        return articles

    try:
        profile_doc = db.collection("user_profiles").document(str(telegram_id)).get()
        if not profile_doc.exists:
            return articles
        profile = profile_doc.to_dict() or {}
    except Exception:
        return articles

    source_weights = profile.get("source_weights", {})
    topic_weights = profile.get("topic_weights", {})

    def score(article: Dict[str, Any]) -> float:
        source = _get_source(article)
        topic = _get_topic(article)

        source_score = float(source_weights.get(source, 0.0))
        topic_score = float(topic_weights.get(topic, 0.0))

        hn_score = float(article.get("score", 0.0) or 0.0)
        popularity_bonus = min(hn_score / 100.0, 2.0)

        return source_score + topic_score + popularity_bonus

    ranked = sorted(articles, key=score, reverse=True)
    return ranked


def record_digest_context(digest_id: str, telegram_id: int, articles: List[Dict[str, Any]]) -> bool:
    """
    Store lightweight digest context for later feedback learning.
    """
    db = get_firestore_client()
    if not db:
        return False

    try:
        context_rows = []
        for article in articles:
            context_rows.append({
                "source": _get_source(article),
                "topic": _get_topic(article),
                "url": article.get("url", ""),
                "title": article.get("title", "")[:160],
            })

        db.collection("digest_context").document(digest_id).set({
            "user_id": telegram_id,
            "items": context_rows,
            "created_at": datetime.utcnow().isoformat(),
        }, merge=True)
        return True
    except Exception as e:
        print(f"Digest context store error: {e}")
        return False


def apply_digest_feedback(telegram_id: int, digest_id: str, rating: str) -> bool:
    """
    Apply thumbs up/down feedback to user preference profile.
    """
    db = get_firestore_client()
    if not db:
        return False

    delta = 1.0 if rating == "up" else -1.0

    try:
        context_doc = db.collection("digest_context").document(digest_id).get()
        if not context_doc.exists:
            return False
        items = (context_doc.to_dict() or {}).get("items", [])
        if not items:
            return False

        profile_ref = db.collection("user_profiles").document(str(telegram_id))
        profile_doc = profile_ref.get()
        profile = profile_doc.to_dict() if profile_doc.exists else {}

        source_weights = profile.get("source_weights", {})
        topic_weights = profile.get("topic_weights", {})
        feedback_count = int(profile.get("feedback_count", 0))

        for item in items:
            source = item.get("source", "Unknown")
            topic = item.get("topic", "general")
            source_weights[source] = round(float(source_weights.get(source, 0.0)) + delta * 0.25, 3)
            topic_weights[topic] = round(float(topic_weights.get(topic, 0.0)) + delta * 0.3, 3)

        # Clamp weights to avoid runaway growth.
        source_weights = {k: max(min(v, 8.0), -8.0) for k, v in source_weights.items()}
        topic_weights = {k: max(min(v, 8.0), -8.0) for k, v in topic_weights.items()}

        profile_ref.set({
            "source_weights": source_weights,
            "topic_weights": topic_weights,
            "feedback_count": feedback_count + 1,
            "updated_at": datetime.utcnow().isoformat(),
        }, merge=True)

        return True
    except Exception as e:
        print(f"Feedback apply error: {e}")
        return False
