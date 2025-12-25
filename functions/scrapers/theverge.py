"""
The Verge RSS Scraper
Fetches latest tech news from The Verge using their RSS feed.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime
import xml.etree.ElementTree as ET

try:
    from ..resilience import retry_with_backoff
except ImportError:
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


VERGE_RSS_URL = "https://www.theverge.com/rss/index.xml"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def fetch_theverge(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch latest articles from The Verge RSS feed.
    
    Args:
        limit: Maximum number of articles to return
        
    Returns:
        List of articles with title, url, summary
    """
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = client.get(VERGE_RSS_URL, headers=headers)
            response.raise_for_status()
            
            # Parse XML/Atom feed
            root = ET.fromstring(response.content)
            
            # The Verge uses Atom format
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            articles = []
            entries = root.findall('.//atom:entry', namespace)
            
            for entry in entries[:limit]:
                title = entry.find('atom:title', namespace)
                link = entry.find('atom:link', namespace)
                published = entry.find('atom:published', namespace)
                summary = entry.find('atom:content', namespace)
                
                if title is not None and link is not None:
                    article = {
                        'title': title.text or '',
                        'url': link.get('href', ''),
                        'source': 'The Verge',
                        'time': published.text if published is not None else datetime.now().isoformat(),
                    }
                    
                    # Add summary if available (clean HTML)
                    if summary is not None and summary.text:
                        # Basic HTML cleaning - just extract first 200 chars of text
                        import re
                        clean_summary = re.sub(r'<[^>]+>', '', summary.text)
                        article['summary'] = clean_summary[:200] + '...' if len(clean_summary) > 200 else clean_summary
                    
                    articles.append(article)
            
            print(f"The Verge: Fetched {len(articles)} articles")
            return articles
            
    except Exception as e:
        print(f"Error fetching The Verge: {e}")
        return []


if __name__ == "__main__":
    # Test the scraper
    articles = fetch_theverge(5)
    print(f"\nFound {len(articles)} articles from The Verge:\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   {article['url']}\n")
