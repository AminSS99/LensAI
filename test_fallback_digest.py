import pytest
from functions.fallback_digest import categorize_news

def test_categorize_empty():
    assert categorize_news([]) == {}

def test_categorize_top_stories():
    articles = [
        {"title": "Some random title", "score": 250},
        {"title": "AI is taking over", "score": 300} # AI title but score overrides it
    ]
    result = categorize_news(articles)
    assert len(result) == 1
    assert len(result["🔥 Top Stories"]) == 2

def test_categorize_ai_keywords():
    articles = [
        {"title": "New machine learning model released", "score": 50},
        {"title": "Anthropic drops a new LLM", "score": 100}
    ]
    result = categorize_news(articles)
    assert len(result) == 1
    assert len(result["🤖 AI & ML"]) == 2

def test_categorize_tools_keywords():
    articles = [
        {"title": "React version 19 launch", "score": 10},
        {"title": "Awesome new framework for testing", "score": 150}
    ]
    result = categorize_news(articles)
    assert len(result) == 1
    assert len(result["🛠️ Tools & Products"]) == 2

def test_categorize_business_keywords():
    articles = [
        {"title": "Startup secures $10M Series B funding", "score": 5},
        {"title": "Big acquisition in tech", "score": 100}
    ]
    result = categorize_news(articles)
    assert len(result) == 1
    assert len(result["💼 Business & Startups"]) == 2

def test_categorize_other_news():
    articles = [
        {"title": "How I built a cabin in the woods", "score": 15},
        {"title": "A review of some movie", "score": 50}
    ]
    result = categorize_news(articles)
    assert len(result) == 1
    assert len(result["📰 Other News"]) == 2

def test_categorize_case_insensitivity():
    articles = [
        {"title": "MACHINE LEARNING rules", "score": 10},
        {"title": "aWeSoMe LaUnCh", "score": 10}
    ]
    result = categorize_news(articles)
    assert "🤖 AI & ML" in result
    assert "🛠️ Tools & Products" in result
    assert len(result["🤖 AI & ML"]) == 1
    assert len(result["🛠️ Tools & Products"]) == 1

def test_categorize_missing_keys():
    articles = [
        {}, # Missing title and score
        {"score": 10}, # Missing title
        {"title": "AI missing score"} # Missing score
    ]
    result = categorize_news(articles)
    assert len(result["📰 Other News"]) == 2
    assert len(result["🤖 AI & ML"]) == 1
