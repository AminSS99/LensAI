"""Quick test script for scrapers."""
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


print("=" * 50)
print("  Testing Scrapers")
print("=" * 50)

# Test Hacker News
print("\n1. Testing Hacker News API...")
try:
    from functions.scrapers.hackernews import fetch_hackernews_sync

    stories = fetch_hackernews_sync(5)
    print(f"   OK Found {len(stories)} stories")
    for story in stories[:3]:
        print(f"      - {story['title'][:55]}...")
except Exception as exc:
    print(f"   ERR Error: {exc}")

# Test TechCrunch
print("\n2. Testing TechCrunch RSS...")
try:
    from functions.scrapers.techcrunch import fetch_techcrunch

    articles = fetch_techcrunch(5)
    print(f"   OK Found {len(articles)} articles")
    for article in articles[:3]:
        print(f"      - {article['title'][:55]}...")
except Exception as exc:
    print(f"   ERR Error: {exc}")

# Test AI Blogs
print("\n3. Testing AI Blogs...")
try:
    from functions.scrapers.ai_blogs import fetch_ai_blogs_sync

    posts = fetch_ai_blogs_sync(2)
    print(f"   OK Found {len(posts)} posts")
    for post in posts[:5]:
        print(f"      - [{post['source']}] {post['title'][:45]}...")
except Exception as exc:
    print(f"   ERR Error: {exc}")

print("\n" + "=" * 50)
print("  Scraper tests complete!")
print("=" * 50)
