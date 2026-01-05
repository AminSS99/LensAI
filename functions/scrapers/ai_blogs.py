"""
AI Company Blog Scrapers
Fetches latest news from AI company blogs (OpenAI, Anthropic, Google AI, Mistral, etc.)
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime
import asyncio

try:
    from ..resilience import retry_with_backoff
except ImportError:
    def retry_with_backoff(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# AI Blog URLs and their scraping configurations
AI_BLOGS = {
    # OpenAI blocks automated scraping (403 Forbidden)
    # 'openai': {
    #     'url': 'https://openai.com/news/',
    #     'name': 'OpenAI',
    #     'selector': 'a[href*="/index/"]',
    # },
    'anthropic': {
        'url': 'https://www.anthropic.com/news',
        'name': 'Anthropic',
        'selector': 'a[href*="/news/"]',
    },
    'google_ai': {
        'url': 'https://blog.google/technology/ai/',
        'name': 'Google AI',
        'selector': 'a[href*="/technology/ai/"]',
    },
    'mistral': {
        'url': 'https://mistral.ai/news/',
        'name': 'Mistral AI',
        'selector': 'a[href*="/news/"]',
    },
    'deepmind': {
        'url': 'https://deepmind.google/discover/blog/',
        'name': 'DeepMind',
        'selector': 'a[href*="/blog/"]',
    },
    # New AI sources
    'deepseek': {
        'url': 'https://www.deepseek.com/',
        'name': 'DeepSeek',
        'selector': 'a[href*="/news"], a[href*="/blog"], article a',
    },
    'qwen': {
        'url': 'https://qwenlm.github.io/blog/',
        'name': 'Qwen',
        'selector': 'article a, .post-link, a[href*="/blog/"]',
    },
    # xAI blocks automated scraping (403 Forbidden)
    # 'xai': {
    #     'url': 'https://x.ai/',
    #     'name': 'xAI',
    #     'selector': 'a[href*="/blog"], a[href*="/news"], article a',
    # },
}

# Common headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


async def scrape_blog(client: httpx.AsyncClient, blog_key: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Scrape a single AI blog for recent posts.
    
    Args:
        client: httpx async client
        blog_key: Key from AI_BLOGS dict
        limit: Max posts to return
        
    Returns:
        List of blog posts
    """
    blog = AI_BLOGS.get(blog_key)
    if not blog:
        return []
    
    try:
        response = await client.get(blog['url'], headers=HEADERS, follow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        seen_urls = set()
        
        # Find all links that match the selector
        links = soup.select(blog['selector'])
        
        for link in links:
            href = link.get('href', '')
            
            # Skip if empty or already seen
            if not href or href in seen_urls:
                continue
            
            # Make absolute URL if needed
            if href.startswith('/'):
                base_url = blog['url'].split('/')[0] + '//' + blog['url'].split('/')[2]
                href = base_url + href
            
            # Skip non-http URLs
            if not href.startswith('http'):
                continue
                
            seen_urls.add(href)
            
            # Get title from link text or nearest heading
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                # Try to find a nearby title
                parent = link.parent
                for _ in range(3):
                    if parent:
                        heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                        if heading:
                            title = heading.get_text(strip=True)
                            break
                        parent = parent.parent
            
            if title and len(title) > 5:
                posts.append({
                    'title': title[:200],  # Limit title length
                    'url': href,
                    'source': blog['name'],
                    'date': datetime.now().isoformat(),
                    'summary': ''
                })
                
                if len(posts) >= limit:
                    break
        
        return posts
        
    except Exception as e:
        print(f"Error scraping {blog['name']}: {e}")
        return []


@retry_with_backoff(max_retries=2, base_delay=1.0)
async def fetch_ai_blogs(limit_per_blog: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch latest posts from all AI company blogs.
    
    Args:
        limit_per_blog: Max posts per blog
        
    Returns:
        List of all blog posts from all sources
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Scrape all blogs concurrently
        tasks = [
            scrape_blog(client, blog_key, limit_per_blog)
            for blog_key in AI_BLOGS.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine all results
        all_posts = []
        for result in results:
            if isinstance(result, list):
                all_posts.extend(result)
            elif isinstance(result, Exception):
                print(f"Blog scraping error: {result}")
        
        return all_posts


def fetch_ai_blogs_sync(limit_per_blog: int = 5) -> List[Dict[str, Any]]:
    """Synchronous version for simpler usage."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # We're inside an async context - use synchronous HTTP calls
        return _fetch_ai_blogs_sync_impl(limit_per_blog)
    else:
        return asyncio.run(fetch_ai_blogs(limit_per_blog))


def _fetch_ai_blogs_sync_impl(limit_per_blog: int = 5) -> List[Dict[str, Any]]:
    """Truly synchronous implementation using httpx sync client."""
    all_posts = []
    
    with httpx.Client(timeout=30.0) as client:
        for blog_key, blog in AI_BLOGS.items():
            try:
                response = client.get(blog['url'], headers=HEADERS, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                posts = []
                seen_urls = set()
                
                links = soup.select(blog['selector'])
                
                for link in links:
                    href = link.get('href', '')
                    
                    if not href or href in seen_urls:
                        continue
                    
                    if href.startswith('/'):
                        base_url = blog['url'].split('/')[0] + '//' + blog['url'].split('/')[2]
                        href = base_url + href
                    
                    if not href.startswith('http'):
                        continue
                    
                    seen_urls.add(href)
                    
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        parent = link.parent
                        for _ in range(3):
                            if parent:
                                heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                                if heading:
                                    title = heading.get_text(strip=True)
                                    break
                                parent = parent.parent
                    
                    if title and len(title) > 5:
                        posts.append({
                            'title': title[:200],
                            'url': href,
                            'source': blog['name'],
                            'date': datetime.now().isoformat(),
                            'summary': ''
                        })
                        
                        if len(posts) >= limit_per_blog:
                            break
                
                all_posts.extend(posts)
                
            except Exception as e:
                print(f"Error scraping {blog['name']}: {e}")
                continue
    
    return all_posts


if __name__ == "__main__":
    # Test the scrapers
    async def test():
        posts = await fetch_ai_blogs(3)
        print(f"Found {len(posts)} AI blog posts:\n")
        
        # Group by source
        by_source = {}
        for post in posts:
            source = post['source']
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(post)
        
        for source, source_posts in by_source.items():
            print(f"\n=== {source} ===")
            for post in source_posts:
                print(f"  • {post['title']}")
                print(f"    {post['url']}")
    
    asyncio.run(test())
