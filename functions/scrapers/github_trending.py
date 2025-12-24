"""
GitHub Trending Scraper
Fetches trending repositories from GitHub.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup


GITHUB_TRENDING_URL = "https://github.com/trending"


def fetch_github_trending(limit: int = 10, language: str = None) -> List[Dict[str, Any]]:
    """
    Fetch trending repositories from GitHub.
    
    Args:
        limit: Maximum number of repos to return
        language: Optional language filter (e.g., 'python', 'javascript')
        
    Returns:
        List of repos with name, description, url, stars, language
    """
    try:
        url = GITHUB_TRENDING_URL
        if language:
            url = f"{url}/{language}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            repos = []
            articles = soup.select('article.Box-row')
            
            for article in articles[:limit]:
                # Get repo name and URL
                h2 = article.select_one('h2 a')
                if not h2:
                    continue
                    
                repo_path = h2.get('href', '').strip()
                repo_name = repo_path.lstrip('/')
                repo_url = f"https://github.com{repo_path}"
                
                # Get description
                description_elem = article.select_one('p')
                description = description_elem.get_text(strip=True) if description_elem else ''
                
                # Get language
                lang_elem = article.select_one('[itemprop="programmingLanguage"]')
                repo_lang = lang_elem.get_text(strip=True) if lang_elem else 'Unknown'
                
                # Get stars today
                stars_elem = article.select_one('span.d-inline-block.float-sm-right')
                stars_today = stars_elem.get_text(strip=True) if stars_elem else '0 stars today'
                
                # Get total stars
                total_stars_elem = article.select('a.Link--muted')
                total_stars = '0'
                if total_stars_elem:
                    for link in total_stars_elem:
                        if '/stargazers' in link.get('href', ''):
                            total_stars = link.get_text(strip=True).replace(',', '')
                            break
                
                repos.append({
                    'title': f"🔥 {repo_name}",
                    'url': repo_url,
                    'summary': description[:200] if description else f"Trending {repo_lang} repository",
                    'source': 'GitHub Trending',
                    'language': repo_lang,
                    'stars': total_stars,
                    'stars_today': stars_today,
                    'time': datetime.now().isoformat(),
                })
            
            print(f"GitHub Trending: Fetched {len(repos)} repositories")
            return repos
            
    except Exception as e:
        print(f"Error fetching GitHub Trending: {e}")
        return []


if __name__ == "__main__":
    # Test the scraper
    repos = fetch_github_trending(5)
    print(f"\nFound {len(repos)} trending repos:\n")
    for i, repo in enumerate(repos, 1):
        print(f"{i}. {repo['title']}")
        print(f"   ⭐ {repo['stars']} | {repo['language']}")
        print(f"   {repo['summary'][:80]}...")
        print(f"   {repo['url']}\n")
