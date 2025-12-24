"""
Product Hunt Scraper
Fetches trending products from Product Hunt RSS feed.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime
import xml.etree.ElementTree as ET


# Product Hunt has an RSS feed for their front page
PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"


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
                        import re
                        desc_text = re.sub(r'<[^>]+>', '', description.text)[:200]
                    
                    products.append({
                        'title': title.text or '',
                        'url': link.text or '',
                        'summary': desc_text,
                        'source': 'Product Hunt',
                        'time': pub_date.text if pub_date is not None else datetime.now().isoformat(),
                    })
            
            print(f"Product Hunt: Fetched {len(products)} products")
            return products
            
    except ET.ParseError as e:
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
