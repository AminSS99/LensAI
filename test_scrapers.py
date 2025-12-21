"""Quick test script for scrapers."""
import sys
sys.path.insert(0, '.')

print("=" * 50)
print("  Testing Scrapers")
print("=" * 50)

# Test Hacker News
print("\n1. Testing Hacker News API...")
try:
    from functions.scrapers.hackernews import fetch_hackernews_sync
    stories = fetch_hackernews_sync(5)
    print(f"   ✅ Found {len(stories)} stories")
    for s in stories[:3]:
        print(f"      - {s['title'][:55]}...")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test TechCrunch
print("\n2. Testing TechCrunch RSS...")
try:
    from functions.scrapers.techcrunch import fetch_techcrunch
    articles = fetch_techcrunch(5)
    print(f"   ✅ Found {len(articles)} articles")
    for a in articles[:3]:
        print(f"      - {a['title'][:55]}...")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test AI Blogs
print("\n3. Testing AI Blogs...")
try:
    from functions.scrapers.ai_blogs import fetch_ai_blogs_sync
    posts = fetch_ai_blogs_sync(2)
    print(f"   ✅ Found {len(posts)} posts")
    for p in posts[:5]:
        print(f"      - [{p['source']}] {p['title'][:45]}...")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 50)
print("  Scraper tests complete!")
print("=" * 50)
