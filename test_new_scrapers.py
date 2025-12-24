"""Test new scrapers"""
import sys
sys.path.insert(0, 'functions')

from scrapers.theverge import fetch_theverge
from scrapers.github_trending import fetch_github_trending
from scrapers.producthunt import fetch_producthunt

print("Testing The Verge...")
verge = fetch_theverge(3)
print(f"The Verge: {len(verge)} articles")
for a in verge:
    print(f"  - {a['title'][:60]}")

print("\nTesting GitHub Trending...")
github = fetch_github_trending(3)
print(f"GitHub: {len(github)} repos")
for r in github:
    print(f"  - {r['title'][:60]}")

print("\nTesting Product Hunt...")
ph = fetch_producthunt(3)
print(f"Product Hunt: {len(ph)} products")
for p in ph:
    print(f"  - {p['title'][:60]}")

print("\nAll scrapers tested!")
