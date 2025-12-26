"""
TechCrunch RSS Feed Parser
Fetches latest articles from TechCrunch using their RSS feed.
"""

import feedparser
import httpx
from typing import List, Dict, Any
from datetime import datetime
import time

try:
    from ..resilience import retry_with_backoff
except ImportError:
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


TECHCRUNCH_RSS = "https://techcrunch.com/feed/"


def parse_date(date_struct) -> str:
    """Convert feedparser date struct to ISO format."""
    if date_struct:
        try:
            return datetime(*date_struct[:6]).isoformat()
        except Exception as e:
            print(f"Error parsing date '{date_struct}': {e}")
            return datetime.now().isoformat() # Ensure a string is returned in case of error
    return datetime.now().isoformat()


@retry_with_backoff(max_retries=2, base_delay=1.0)
def fetch_techcrunch(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch latest articles from TechCrunch RSS feed.
    
    Args:
        limit: Maximum number of articles to return
        
    Returns:
        List of articles with title, url, summary, date
    """
    try:
        # Parse the RSS feed
        feed = feedparser.parse(TECHCRUNCH_RSS)
        
        if feed.bozo and not feed.entries:
            print(f"Error parsing TechCrunch feed: {feed.bozo_exception}")
            return []
        
        articles = []
        for entry in feed.entries[:limit]:
            # Clean up summary (remove HTML tags)
            summary = entry.get('summary', '')
            if summary:
                # Basic HTML tag removal
                import re
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = summary[:300] + '...' if len(summary) > 300 else summary
            
            articles.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'summary': summary,
                'date': parse_date(entry.get('published_parsed')),
                'source': 'TechCrunch',
                'author': entry.get('author', 'TechCrunch')
            })
        
        return articles
        
    except Exception as e:
        print(f"Error fetching TechCrunch: {e}")
        return []


if __name__ == "__main__":
    # Test the scraper
    articles = fetch_techcrunch(5)
    print(f"Found {len(articles)} TechCrunch articles:\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   {article['url']}")
        print(f"   {article['summary'][:100]}...\n")
