"""
Observability Helpers
Builds a simple runtime health snapshot for admin usage.
"""

from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from collections import Counter


def get_firestore_client():
    """Get Firestore client or None."""
    try:
        from google.cloud import firestore
        import os
        project_id = os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return firestore.Client(project=project_id)
        return firestore.Client()
    except Exception:
        return None


def build_health_snapshot() -> Dict[str, Any]:
    """
    Build operational snapshot from Firestore state.
    """
    snapshot = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "users_total": 0,
        "users_active": 0,
        "languages": {},
        "timezones": {},
        "latest_trend_date": None,
        "cache_entries": 0,
        "active_locks": 0,
    }

    db = get_firestore_client()
    if not db:
        snapshot["warning"] = "Firestore unavailable"
        return snapshot

    try:
        users = list(db.collection("users").stream())
        snapshot["users_total"] = len(users)
        lang_counts = Counter()
        tz_counts = Counter()
        active = 0
        for doc in users:
            data = doc.to_dict() or {}
            if data.get("is_active", False):
                active += 1
            lang_counts[data.get("language", "unknown")] += 1
            tz_counts[data.get("timezone", "unknown")] += 1
        snapshot["users_active"] = active
        snapshot["languages"] = dict(lang_counts)
        snapshot["timezones"] = dict(tz_counts)
    except Exception as e:
        snapshot["users_error"] = str(e)

    try:
        from google.cloud import firestore as firestore_module
        latest = (
            db.collection("daily_trends")
            .order_by("date", direction=firestore_module.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        latest_list = list(latest)
        if latest_list:
            snapshot["latest_trend_date"] = (latest_list[0].to_dict() or {}).get("date")
    except Exception as e:
        snapshot["trends_error"] = str(e)

    try:
        now_ts = datetime.now(timezone.utc).timestamp()
        cache_docs = list(db.collection("cache").stream())
        valid = 0
        for doc in cache_docs:
            data = doc.to_dict() or {}
            expires_at = data.get("expires_at", 0)
            if isinstance(expires_at, (int, float)) and expires_at > now_ts:
                valid += 1
        snapshot["cache_entries"] = valid
    except Exception as e:
        snapshot["cache_error"] = str(e)

    try:
        now = datetime.now(timezone.utc)
        lock_docs = list(db.collection("locks").stream())
        active_locks = 0
        for doc in lock_docs:
            data = doc.to_dict() or {}
            expires_at = data.get("expires_at")
            try:
                if expires_at:
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at > now:
                        active_locks += 1
            except Exception:
                continue
        snapshot["active_locks"] = active_locks
    except Exception as e:
        snapshot["locks_error"] = str(e)

    return snapshot
