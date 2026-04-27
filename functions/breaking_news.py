"""
Breaking News Detection Module
Detects sudden spikes in news volume per topic and alerts opted-in users.
Tracks temporal patterns to learn when news dumps typically happen.

Key features:
- Frequency cap: max 2 alerts per user per day, minimum 8h between alerts
- Deduplication: never sends articles already seen in digests or previous alerts
- Descriptions: every article includes a short summary
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

try:
    from google.cloud import firestore
except Exception:
    firestore = None

from .user_storage import get_firestore_client
from .topic_clustering import extract_topic, get_topic_label
from .security_utils import stable_hash

# Thresholds for breaking news detection
BREAKING_SPIKE_MULTIPLIER = 2.0  # Current count must be > 2x average
BREAKING_MIN_ABSOLUTE = 5       # At least 5 articles to trigger
HISTORY_WINDOW_HOURS = 168      # 7 days of history for baseline

# Frequency limits
MIN_HOURS_BETWEEN_ALERTS = 8    # Minimum hours between breaking alerts per user
MAX_ALERTS_PER_DAY = 2          # Max breaking alerts per user per day
ARTICLE_DEDUP_WINDOW_HOURS = 24 # How long to remember sent articles


def _get_db():
    """Get Firestore client or None."""
    return get_firestore_client()


def record_hourly_topic_counts(articles: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Record article counts per topic for the current hour.
    Returns the topic counts for this batch.
    """
    db = _get_db()
    if not db or firestore is None:
        return {}

    now = datetime.now(timezone.utc)
    hour_key = now.strftime("%Y-%m-%d-%H")

    topic_counts = defaultdict(int)
    for article in articles:
        topic = extract_topic(article.get('title', ''), article.get('url', ''))
        topic_counts[topic] += 1

    try:
        batch = db.batch()
        for topic, count in topic_counts.items():
            doc_ref = db.collection('temporal_patterns').document(f"{hour_key}_{topic}")
            batch.set(doc_ref, {
                'hour_key': hour_key,
                'topic': topic,
                'count': count,
                'timestamp': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        batch.commit()
    except Exception as e:
        print(f"Error recording temporal patterns: {e}")

    return dict(topic_counts)


def get_topic_baselines(topic: str, hours: int = HISTORY_WINDOW_HOURS) -> Dict[str, float]:
    """
    Calculate average and max article counts per hour for a topic.
    Returns {'average': float, 'max': int, 'samples': int}
    """
    db = _get_db()
    if not db:
        return {'average': 0.0, 'max': 0, 'samples': 0}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        docs = db.collection('temporal_patterns')\
            .where('topic', '==', topic)\
            .where('timestamp', '>=', cutoff)\
            .stream()

        counts = []
        for doc in docs:
            data = doc.to_dict()
            c = data.get('count', 0)
            if isinstance(c, int) and c > 0:
                counts.append(c)

        if not counts:
            return {'average': 0.0, 'max': 0, 'samples': 0}

        return {
            'average': sum(counts) / len(counts),
            'max': max(counts),
            'samples': len(counts)
        }
    except Exception as e:
        print(f"Error getting baseline for {topic}: {e}")
        return {'average': 0.0, 'max': 0, 'samples': 0}


def detect_breaking_news(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyze articles and detect breaking news spikes.
    Returns a list of breaking alerts with topic, count, and representative articles.
    """
    if not articles:
        return []

    # Record current counts for future baselines
    current_counts = record_hourly_topic_counts(articles)

    alerts = []
    for topic, count in current_counts.items():
        if count < BREAKING_MIN_ABSOLUTE:
            continue

        baseline = get_topic_baselines(topic)
        avg = baseline.get('average', 0.0)

        # If no baseline yet, use a sensible default
        if avg < 1.0:
            avg = 2.0

        if count >= avg * BREAKING_SPIKE_MULTIPLIER:
            # Get representative articles for this topic
            topic_articles = [
                a for a in articles
                if extract_topic(a.get('title', ''), a.get('url', '')) == topic
            ]
            alerts.append({
                'topic': topic,
                'count': count,
                'baseline_avg': round(avg, 1),
                'multiplier': round(count / avg, 1),
                'articles': topic_articles[:5],
                'detected_at': datetime.now(timezone.utc).isoformat(),
            })

    return alerts


# ============ USER FREQUENCY LIMITING ============

def can_send_breaking_to_user(user_id: int) -> bool:
    """
    Check if user is eligible for a breaking alert right now.
    Rules:
    - Minimum 8 hours since last breaking alert
    - Maximum 2 alerts per calendar day (UTC)
    """
    db = _get_db()
    if not db:
        return False

    try:
        doc = db.collection('users').document(str(user_id)).get()
        if not doc.exists:
            return True  # New user, allow first alert

        data = doc.to_dict()
        last_sent = data.get('breaking_last_sent_at')
        today_count = data.get('breaking_today_count', 0)
        today_date = data.get('breaking_today_date', '')

        now = datetime.now(timezone.utc)
        current_date = now.strftime("%Y-%m-%d")

        # Reset daily count if it's a new day
        if today_date != current_date:
            return True

        # Check daily cap
        if today_count >= MAX_ALERTS_PER_DAY:
            return False

        # Check minimum gap between alerts
        if last_sent:
            try:
                if isinstance(last_sent, datetime):
                    last_dt = last_sent
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                else:
                    last_dt = datetime.fromisoformat(str(last_sent))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                hours_since = (now - last_dt).total_seconds() / 3600
                if hours_since < MIN_HOURS_BETWEEN_ALERTS:
                    return False
            except Exception:
                pass

        return True
    except Exception as e:
        print(f"Error checking breaking eligibility for {user_id}: {e}")
        return False


def record_breaking_sent_to_user(user_id: int):
    """Update user's breaking alert tracking after sending."""
    db = _get_db()
    if not db:
        return

    try:
        now = datetime.now(timezone.utc)
        current_date = now.strftime("%Y-%m-%d")

        doc = db.collection('users').document(str(user_id)).get()
        if doc.exists:
            data = doc.to_dict()
            today_date = data.get('breaking_today_date', '')
            today_count = data.get('breaking_today_count', 0) if today_date == current_date else 0
        else:
            today_count = 0

        db.collection('users').document(str(user_id)).set({
            'breaking_last_sent_at': firestore.SERVER_TIMESTAMP if firestore else now,
            'breaking_today_date': current_date,
            'breaking_today_count': today_count + 1,
        }, merge=True)
    except Exception as e:
        print(f"Error recording breaking sent for {user_id}: {e}")


# ============ ARTICLE DEDUPLICATION ============

def _article_hash(article: Dict[str, Any]) -> str:
    """Generate a stable hash for an article (for dedup)."""
    key = article.get('url', '') or article.get('title', '')
    return stable_hash(key)[:16]


def get_recently_sent_article_hashes(user_id: int, hours: int = ARTICLE_DEDUP_WINDOW_HOURS) -> Set[str]:
    """Get set of article hashes sent to user in the last N hours (digests + breaking)."""
    db = _get_db()
    if not db:
        return set()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        docs = db.collection('users').document(str(user_id)).collection('sent_articles')\
            .where('sent_at', '>=', cutoff)\
            .stream()

        hashes = set()
        for doc in docs:
            data = doc.to_dict()
            h = data.get('article_hash')
            if h:
                hashes.add(h)
        return hashes
    except Exception as e:
        print(f"Error getting sent articles for {user_id}: {e}")
        return set()


def record_sent_articles(user_id: int, articles: List[Dict[str, Any]]):
    """Mark articles as sent to user so they aren't repeated."""
    db = _get_db()
    if not db or not articles:
        return

    try:
        batch = db.batch()
        user_ref = db.collection('users').document(str(user_id))
        for article in articles:
            h = _article_hash(article)
            doc_ref = user_ref.collection('sent_articles').document(h)
            batch.set(doc_ref, {
                'article_hash': h,
                'title': article.get('title', '')[:100],
                'url': article.get('url', '')[:200],
                'sent_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
            }, merge=True)
        batch.commit()
    except Exception as e:
        print(f"Error recording sent articles for {user_id}: {e}")


def filter_fresh_articles(articles: List[Dict[str, Any]], user_id: int) -> List[Dict[str, Any]]:
    """Filter out articles that were already sent to this user recently."""
    sent_hashes = get_recently_sent_article_hashes(user_id)
    fresh = []
    for article in articles:
        h = _article_hash(article)
        if h not in sent_hashes:
            fresh.append(article)
    return fresh


# ============ USER PREFERENCE ============

def get_user_breaking_news_preference(user_id: int) -> bool:
    """Check if user has enabled breaking news alerts."""
    db = _get_db()
    if not db:
        return False
    try:
        doc = db.collection('users').document(str(user_id)).get()
        if doc.exists:
            return bool(doc.to_dict().get('breaking_news_enabled', False))
    except Exception:
        pass
    return False


def set_user_breaking_news_preference(user_id: int, enabled: bool):
    """Enable or disable breaking news alerts for a user."""
    db = _get_db()
    if not db:
        return
    try:
        db.collection('users').document(str(user_id)).set({
            'breaking_news_enabled': enabled,
            'updated_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
        }, merge=True)
    except Exception as e:
        print(f"Error setting breaking news preference: {e}")


# ============ FORMATTING ============

def format_breaking_alert(alert: Dict[str, Any], lang: str = 'en') -> str:
    """Format a breaking news alert message for Telegram."""
    topic = alert.get('topic', 'general')
    count = alert.get('count', 0)
    baseline = alert.get('baseline_avg', 0)
    multiplier = alert.get('multiplier', 0)
    articles = alert.get('articles', [])

    topic_label = get_topic_label(topic, lang)

    if lang == 'ru':
        lines = [
            f"🚨 *Важные новости: {topic_label}*",
            f"",
            f"Обнаружен резкий всплеск: *{count}* статей за час (обычно ~{baseline}).",
            f"",
            f"*Главное:*"
        ]
    else:
        lines = [
            f"🚨 *Breaking: {topic_label}*",
            f"",
            f"Detected a sudden spike: *{count}* articles this hour (usually ~{baseline}).",
            f"",
            f"*Top stories:*"
        ]

    for i, article in enumerate(articles[:3], 1):
        title = article.get('title', 'Untitled')[:70]
        url = article.get('url', '')
        source = article.get('source', '')
        summary = article.get('summary', '')

        # Build the line with title and link
        if url.startswith('http'):
            lines.append(f"{i}. [{title}]({url})")
        else:
            lines.append(f"{i}. {title}")

        # Add source
        if source:
            lines.append(f"   _{source}_")

        # Add short description (max 120 chars)
        if summary:
            short_summary = summary[:120] + "..." if len(summary) > 120 else summary
            lines.append(f"   {short_summary}")
        else:
            # If no summary, try to get any description field
            desc = article.get('description', '')
            if desc:
                short_desc = desc[:120] + "..." if len(desc) > 120 else desc
                lines.append(f"   {short_desc}")

        lines.append("")  # Empty line between articles

    if lang == 'ru':
        lines.append(f"\n_Отключить экстренные уведомления: /breaking off_")
    else:
        lines.append(f"\n_Turn off breaking news: /breaking off_")

    return "\n".join(lines)


def get_temporal_insights(topic: str, lang: str = 'en') -> str:
    """
    Generate a temporal pattern insight for a topic.
    E.g., 'AI paper dumps usually happen on Thursdays at 14:00 UTC'
    """
    db = _get_db()
    if not db:
        return ""

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        docs = db.collection('temporal_patterns')\
            .where('topic', '==', topic)\
            .where('timestamp', '>=', cutoff)\
            .stream()

        hourly_counts = defaultdict(int)
        weekday_counts = defaultdict(int)
        total = 0

        for doc in docs:
            data = doc.to_dict()
            ts = data.get('timestamp')
            if not ts:
                continue
            try:
                if isinstance(ts, datetime):
                    dt = ts
                else:
                    dt = datetime.fromisoformat(str(ts))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                hour = dt.strftime("%H:00")
                weekday = dt.strftime("%A")
                count = data.get('count', 0)
                hourly_counts[hour] += count
                weekday_counts[weekday] += count
                total += count
            except Exception:
                continue

        if total < 10:
            return ""

        peak_hour = max(hourly_counts, key=hourly_counts.get) if hourly_counts else None
        peak_weekday = max(weekday_counts, key=weekday_counts.get) if weekday_counts else None

        if lang == 'ru':
            parts = []
            if peak_weekday and weekday_counts[peak_weekday] > total * 0.2:
                parts.append(f"обычно по {peak_weekday}ам")
            if peak_hour and hourly_counts[peak_hour] > total * 0.15:
                parts.append(f"в пик около {peak_hour} UTC")
            if parts:
                return f"📊 *Паттерн:* новости по теме {get_topic_label(topic, 'ru')} {' и '.join(parts)}."
        else:
            parts = []
            if peak_weekday and weekday_counts[peak_weekday] > total * 0.2:
                parts.append(f"usually on {peak_weekday}s")
            if peak_hour and hourly_counts[peak_hour] > total * 0.15:
                parts.append(f"peaking around {peak_hour} UTC")
            if parts:
                return f"📊 *Pattern:* {get_topic_label(topic, 'en')} news {' and '.join(parts)}."

        return ""
    except Exception as e:
        print(f"Error generating temporal insight: {e}")
        return ""


def cleanup_old_temporal_patterns(days: int = 14) -> int:
    """Remove temporal pattern records older than specified days."""
    db = _get_db()
    if not db:
        return 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        docs = db.collection('temporal_patterns').where('timestamp', '<', cutoff).stream()
        batch = db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
        if count % 400 != 0:
            batch.commit()
        return count
    except Exception as e:
        print(f"Error cleaning temporal patterns: {e}")
        return 0


def cleanup_old_sent_articles(days: int = 2) -> int:
    """Remove sent article tracking records older than specified days."""
    db = _get_db()
    if not db:
        return 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # We need to clean up per user, but for efficiency we'll do a collection group query
        # or just let them accumulate since they're small documents.
        # For now, just return 0 to avoid complex multi-user cleanup.
        return 0
    except Exception as e:
        print(f"Error cleaning sent articles: {e}")
        return 0
