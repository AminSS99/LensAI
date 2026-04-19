"""
Product Hunt Scraper
Fetches trending products from Product Hunt RSS feed.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
from bs4 import BeautifulSoup

try:
    from ..security_utils import sanitize_html
except ImportError:
    def sanitize_html(text: str) -> str:
        if not text:
            return ""
        import re
        return " ".join(re.sub(r'<[^>]+>', ' ', text).split())


# Product Hunt has an RSS feed for their front page
PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"
PRODUCTHUNT_WEB_URL = "https://www.producthunt.com/"


def _scrape_producthunt_html(client: httpx.Client, limit: int) -> List[Dict[str, Any]]:
    """Fallback HTML scraper when RSS is empty/unavailable."""
    try:
        response = client.get(PRODUCTHUNT_WEB_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        products = []
        seen_urls = set()

        # Product cards usually contain links under posts.
        for link in soup.select("a[href*='/posts/']"):
            href = link.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://www.producthunt.com{href}"
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue

            products.append({
                "title": title[:200],
                "url": href,
                "summary": "",
                "source": "Product Hunt",
                "time": datetime.now().isoformat(),
            })

            if len(products) >= limit:
                break

        return products
    except Exception as e:
        print(f"Product Hunt HTML fallback error: {e}")
        return []


def fetch_producthunt(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch trending products from Product Hunt RSS feed.
    
    Args:
        limit: Maximum number of products to return
        
    Returns:
        List of products with name, tagline, url
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; LensAI Bot/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*'
        }
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(PRODUCTHUNT_RSS_URL, headers=headers)
            
            if response.status_code != 200:
                print(f"Product Hunt RSS returned {response.status_code}")
                return []
            
            # Parse RSS feed
            root = ET.fromstring(response.content)
            
            products = []
            items = root.findall('.//item')
            
            for item in items[:limit]:
                title = item.find('title')
                link = item.find('link')
                description = item.find('description')
                pub_date = item.find('pubDate')
                
                if title is not None and link is not None:
                    # Clean up description (remove HTML)
                    desc_text = ''
                    if description is not None and description.text:
                        desc_text = sanitize_html(description.text)[:200]
                    
                    products.append({
                        'title': title.text or '',
                        'url': link.text or '',
                        'summary': desc_text,
                        'source': 'Product Hunt',
                        'time': pub_date.text if pub_date is not None else datetime.now().isoformat(),
                    })

            # Product Hunt feed can be Atom instead of RSS.
            if not products:
                atom_ns = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('.//atom:entry', atom_ns)
                for entry in entries[:limit]:
                    title = entry.find('atom:title', atom_ns)
                    link = entry.find('atom:link', atom_ns)
                    summary = entry.find('atom:summary', atom_ns)
                    if summary is None:
                        summary = entry.find('atom:content', atom_ns)

                    published = entry.find('atom:published', atom_ns)
                    if published is None:
                        published = entry.find('atom:updated', atom_ns)

                    if title is None or link is None:
                        continue

                    href = link.get('href', '')
                    desc_text = ''
                    if summary is not None and summary.text:
                        desc_text = sanitize_html(summary.text)[:200]

                    products.append({
                        'title': title.text or '',
                        'url': href,
                        'summary': desc_text,
                        'source': 'Product Hunt',
                        'time': published.text if published is not None else datetime.now().isoformat(),
                    })

            if not products:
                products = _scrape_producthunt_html(client, limit)

            print(f"Product Hunt: Fetched {len(products)} products")
            return products
            
    except (ParseError, DefusedXmlException) as e:
        print(f"Product Hunt XML parse error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching Product Hunt: {e}")
        return []


if __name__ == "__main__":
    # Test the scraper
    products = fetch_producthunt(5)
    print(f"\nFound {len(products)} products from Product Hunt:\n")
    for i, product in enumerate(products, 1):
        print(f"{i}. {product['title']}")
        print(f"   {product.get('summary', '')[:60]}...")
        print(f"   {product['url']}\n")
