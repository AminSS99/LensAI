"""
Hacker News API Scraper
Fetches top stories from Hacker News using the official API.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

try:
    from ..resilience import retry_with_backoff
except ImportError:
    # Fallback for when running standalone
    from functools import wraps
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

# Keywords to filter for tech/AI content
TECH_KEYWORDS = [
    'ai', 'artificial intelligence', 'machine learning', 'ml', 'llm',
    'gpt', 'openai', 'anthropic', 'claude', 'gemini', 'mistral',
    'deepseek', 'neural', 'transformer', 'python', 'javascript',
    'startup', 'google', 'microsoft', 'apple', 'meta', 'amazon',
    'cloud', 'api', 'open source', 'github', 'programming',
    'developer', 'software', 'tech', 'technology', 'coding'
]


async def fetch_story(client: httpx.AsyncClient, story_id: int) -> Dict[str, Any] | None:
    """Fetch a single story by ID."""
    try:
        response = await client.get(f"{HN_API_BASE}/item/{story_id}.json")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching story {story_id}: {e}")
        return None


def is_tech_related(story: Dict[str, Any]) -> bool:
    """Check if story is tech/AI related based on title."""
    if not story or not story.get('title'):
        return False
    
    title_lower = story['title'].lower()
    return any(keyword in title_lower for keyword in TECH_KEYWORDS)


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def fetch_hackernews(limit: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch top tech stories from Hacker News.
    
    Args:
        limit: Maximum number of stories to return
        
    Returns:
        List of stories with title, url, score, comments count
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get top story IDs
        response = await client.get(f"{HN_API_BASE}/topstories.json")
        response.raise_for_status()
        story_ids = response.json()[:100]  # Get top 100 to filter from
        
        # Fetch stories in parallel
        stories = []
        for story_id in story_ids:
            story = await fetch_story(client, story_id)
            if story and is_tech_related(story):
                stories.append({
                    'title': story.get('title', ''),
                    'url': story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                    'score': story.get('score', 0),
                    'comments': story.get('descendants', 0),
                    'source': 'Hacker News',
                    'hn_id': story_id,
                    'time': datetime.fromtimestamp(story.get('time', 0), timezone.utc).isoformat()
                })
                
                if len(stories) >= limit:
                    break
        
        # Sort by score
        stories.sort(key=lambda x: x['score'], reverse=True)
        return stories


def fetch_hackernews_sync(limit: int = 30) -> List[Dict[str, Any]]:
    """
    Synchronous version of fetch_hackernews for simpler usage.
    Handles being called from within an existing event loop.
    """
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # We're inside an async context - use synchronous HTTP calls instead
        return _fetch_hackernews_sync_impl(limit)
    else:
        return asyncio.run(fetch_hackernews(limit))


def _fetch_hackernews_sync_impl(limit: int = 30) -> List[Dict[str, Any]]:
    """Truly synchronous implementation using httpx sync client."""
    with httpx.Client(timeout=30.0) as client:
        # Get top story IDs
        response = client.get(f"{HN_API_BASE}/topstories.json")
        response.raise_for_status()
        story_ids = response.json()[:100]
        
        stories = []
        for story_id in story_ids:
            try:
                resp = client.get(f"{HN_API_BASE}/item/{story_id}.json")
                resp.raise_for_status()
                story = resp.json()
                
                if story and is_tech_related(story):
                    stories.append({
                        'title': story.get('title', ''),
                        'url': story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                        'score': story.get('score', 0),
                        'comments': story.get('descendants', 0),
                        'source': 'Hacker News',
                        'hn_id': story_id,
                    'time': datetime.fromtimestamp(story.get('time', 0), timezone.utc).isoformat()
                    })
                    
                    if len(stories) >= limit:
                        break
            except Exception as e:
                print(f"Error fetching story {story_id}: {e}")
                continue
        
        stories.sort(key=lambda x: x['score'], reverse=True)
        return stories


if __name__ == "__main__":
    # Test the scraper
    import asyncio
    
    async def test():
        stories = await fetch_hackernews(10)
        print(f"Found {len(stories)} tech stories:\n")
        for i, story in enumerate(stories, 1):
            print(f"{i}. [{story['score']} pts] {story['title']}")
            print(f"   {story['url']}\n")
    
    asyncio.run(test())
