"""
Trend Analysis Module
Tracks topic popularity over time and generates trend reports.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict


# Baku timezone
BAKU_TZ = timezone(timedelta(hours=4))


def get_firestore_client():
    """Get Firestore client or None if not available."""
    try:
        from google.cloud import firestore
        return firestore.Client(project='lensai-481910')
    except Exception:
        return None


def record_daily_topics(topic_counts: Dict[str, int], date: Optional[datetime] = None):
    """
    Store daily topic counts in Firestore for trend tracking.
    
    Args:
        topic_counts: Dict mapping topic to article count
        date: Date to record for (defaults to today in Baku time)
    """
    db = get_firestore_client()
    if not db:
        print("Firestore not available for trend recording")
        return
    
    if date is None:
        date = datetime.now(BAKU_TZ)
    
    date_str = date.strftime('%Y-%m-%d')
    
    try:
        db.collection('daily_trends').document(date_str).set({
            'date': date_str,
            'counts': topic_counts,
            'recorded_at': datetime.now(BAKU_TZ).isoformat()
        }, merge=True)
        print(f"Recorded trends for {date_str}")
    except Exception as e:
        print(f"Error recording trends: {e}")


def get_trends_for_period(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get trend data for the past N days.
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of daily trend records
    """
    db = get_firestore_client()
    if not db:
        return []
    
    cutoff = datetime.now(BAKU_TZ) - timedelta(days=days)
    cutoff_str = cutoff.strftime('%Y-%m-%d')
    
    try:
        docs = db.collection('daily_trends')\
            .where('date', '>=', cutoff_str)\
            .order_by('date')\
            .stream()
        
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error fetching trends: {e}")
        return []


def calculate_weekly_trends() -> Dict[str, Dict[str, Any]]:
    """
    Calculate trending topics comparing this week vs last week.
    
    Returns:
        Dict mapping topic to trend info:
        {
            'ai': {
                'this_week': 45,
                'last_week': 32,
                'change': 40.6,  # percentage change
                'trend': 'rising'  # 'rising', 'falling', or 'stable'
            },
            ...
        }
    """
    db = get_firestore_client()
    if not db:
        return {}
    
    now = datetime.now(BAKU_TZ)
    
    # This week: last 7 days
    this_week_start = now - timedelta(days=7)
    # Last week: 7-14 days ago
    last_week_start = now - timedelta(days=14)
    last_week_end = now - timedelta(days=7)
    
    try:
        # Get this week's data
        this_week_docs = db.collection('daily_trends')\
            .where('date', '>=', this_week_start.strftime('%Y-%m-%d'))\
            .stream()
        
        this_week_counts = defaultdict(int)
        for doc in this_week_docs:
            data = doc.to_dict()
            counts = data.get('counts', {})
            for topic, count in counts.items():
                this_week_counts[topic] += count
        
        # Get last week's data
        last_week_docs = db.collection('daily_trends')\
            .where('date', '>=', last_week_start.strftime('%Y-%m-%d'))\
            .where('date', '<', last_week_end.strftime('%Y-%m-%d'))\
            .stream()
        
        last_week_counts = defaultdict(int)
        for doc in last_week_docs:
            data = doc.to_dict()
            counts = data.get('counts', {})
            for topic, count in counts.items():
                last_week_counts[topic] += count
        
        # Calculate trends
        all_topics = set(this_week_counts.keys()) | set(last_week_counts.keys())
        trends = {}
        
        for topic in all_topics:
            this_week = this_week_counts.get(topic, 0)
            last_week = last_week_counts.get(topic, 0)
            
            # Calculate percentage change
            if last_week > 0:
                change = ((this_week - last_week) / last_week) * 100
            elif this_week > 0:
                change = 100.0  # New topic this week
            else:
                change = 0.0
            
            # Determine trend direction
            if change > 15:
                trend = 'rising'
            elif change < -15:
                trend = 'falling'
            else:
                trend = 'stable'
            
            trends[topic] = {
                'this_week': this_week,
                'last_week': last_week,
                'change': round(change, 1),
                'trend': trend
            }
        
        return trends
        
    except Exception as e:
        print(f"Error calculating trends: {e}")
        return {}


def format_trends_message(lang: str = 'en') -> str:
    """
    Format trend data as a user-friendly message.
    
    Args:
        lang: Language code ('en' or 'ru')
        
    Returns:
        Formatted trend message
    """
    from .topic_clustering import TOPIC_DISPLAY
    
    trends = calculate_weekly_trends()
    
    if not trends:
        if lang == 'ru':
            return "📊 **Анализ трендов**\n\n_Недостаточно данных. Тренды появятся через несколько дней использования._"
        return "📊 **Trend Analysis**\n\n_Not enough data yet. Trends will appear after a few days of usage._"
    
    # Sort topics by change (descending for rising, ascending for falling)
    rising = [(t, d) for t, d in trends.items() if d['trend'] == 'rising']
    falling = [(t, d) for t, d in trends.items() if d['trend'] == 'falling']
    stable = [(t, d) for t, d in trends.items() if d['trend'] == 'stable']
    
    rising.sort(key=lambda x: x[1]['change'], reverse=True)
    falling.sort(key=lambda x: x[1]['change'])
    
    lines = []
    
    if lang == 'ru':
        lines.append("📊 **Анализ трендов этой недели**\n")
    else:
        lines.append("📊 **This Week's Trend Analysis**\n")
    
    # Rising topics
    if rising:
        if lang == 'ru':
            lines.append("📈 **Растущие темы:**")
        else:
            lines.append("📈 **Rising Topics:**")
        
        for topic, data in rising[:5]:
            info = TOPIC_DISPLAY.get(topic, {'emoji': '📰', 'en': topic, 'ru': topic})
            label = info.get(lang, info['en'])
            emoji = info['emoji']
            change = data['change']
            count = data['this_week']
            lines.append(f"  {emoji} {label}: +{change:.0f}% ({count} articles)")
        lines.append("")
    
    # Falling topics
    if falling:
        if lang == 'ru':
            lines.append("📉 **Снижающиеся темы:**")
        else:
            lines.append("📉 **Declining Topics:**")
        
        for topic, data in falling[:5]:
            info = TOPIC_DISPLAY.get(topic, {'emoji': '📰', 'en': topic, 'ru': topic})
            label = info.get(lang, info['en'])
            emoji = info['emoji']
            change = data['change']
            count = data['this_week']
            lines.append(f"  {emoji} {label}: {change:.0f}% ({count} articles)")
        lines.append("")
    
    # Stable topics
    if stable and len(rising) + len(falling) < 5:
        if lang == 'ru':
            lines.append("➡️ **Стабильные темы:**")
        else:
            lines.append("➡️ **Stable Topics:**")
        
        for topic, data in stable[:3]:
            info = TOPIC_DISPLAY.get(topic, {'emoji': '📰', 'en': topic, 'ru': topic})
            label = info.get(lang, info['en'])
            emoji = info['emoji']
            count = data['this_week']
            lines.append(f"  {emoji} {label} ({count} articles)")
    
    # Add footer
    if lang == 'ru':
        lines.append("\n_Сравнение с прошлой неделей_")
    else:
        lines.append("\n_Compared to last week_")
    
    return "\n".join(lines)


def get_top_topics_this_week(limit: int = 5) -> List[tuple]:
    """
    Get the most discussed topics this week.
    
    Args:
        limit: Max topics to return
        
    Returns:
        List of (topic, count) tuples
    """
    trends = calculate_weekly_trends()
    
    if not trends:
        return []
    
    # Sort by this week's count
    sorted_topics = sorted(
        [(t, d['this_week']) for t, d in trends.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    return sorted_topics[:limit]
