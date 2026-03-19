import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from functions.fallback_digest import (
    get_source_emoji,
    get_current_date_baku,
    BAKU_TZ,
    categorize_news,
    create_simple_digest,
    create_raw_list
)

def test_get_current_date_baku():
    """Test get_current_date_baku returns timezone-aware datetime."""
    now = get_current_date_baku()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    # Verify offset is UTC+4
    assert now.tzinfo.utcoffset(now) == timedelta(hours=4)

def test_get_source_emoji():
    """Test get_source_emoji correctly maps sources to emojis."""
    assert get_source_emoji("Hacker News") == '📰'
    assert get_source_emoji("HN") == '📰'
    assert get_source_emoji("TechCrunch") == '💻'
    assert get_source_emoji("The Verge") == '📱'
    assert get_source_emoji("GitHub") == '🔥'
    assert get_source_emoji("Anthropic") == '🤖'
    assert get_source_emoji("Google Blog") == '🧠'
    assert get_source_emoji("DeepMind") == '🧠'
    assert get_source_emoji("OpenAI") == '🤖'
    assert get_source_emoji("Mistral AI") == '🌪️'

    # Unknown source
    assert get_source_emoji("Some Random Blog") == '📄'

def test_categorize_news():
    """Test categorize_news correctly groups articles and removes empty categories."""

    news_items = [
        # Top Story (score > 200)
        {"title": "Important top story", "score": 250},
        # AI & ML
        {"title": "New OpenAI model released", "score": 50},
        {"title": "Learn Machine Learning basics", "score": 0},
        # Tools & Products
        {"title": "Awesome open source framework version 2.0", "score": 10},
        # Business & Startups
        {"title": "Acquisition of new startup for $1B", "score": 100},
        # Other News (fallback)
        {"title": "Just some regular interesting article", "score": 10},
        {"title": "Another random news", "score": None} # Testing score as None
    ]

    categories = categorize_news(news_items)

    # Check that expected categories are present
    assert '🔥 Top Stories' in categories
    assert '🤖 AI & ML' in categories
    assert '🛠️ Tools & Products' in categories
    assert '💼 Business & Startups' in categories
    assert '📰 Other News' in categories

    # Verify counts
    assert len(categories['🔥 Top Stories']) == 1
    assert len(categories['🤖 AI & ML']) == 2
    assert len(categories['🛠️ Tools & Products']) == 1
    assert len(categories['💼 Business & Startups']) == 1
    assert len(categories['📰 Other News']) == 2

    # Verify content
    assert categories['🔥 Top Stories'][0]['title'] == "Important top story"
    assert categories['🤖 AI & ML'][0]['title'] == "New OpenAI model released"
    assert categories['📰 Other News'][1]['title'] == "Another random news"


def test_categorize_news_empty_categories_removed():
    """Test categorize_news removes empty categories from the dictionary."""

    # Only sending AI items
    news_items = [
        {"title": "New deep learning technique", "score": 10}
    ]

    categories = categorize_news(news_items)

    # Should only have AI category
    assert len(categories) == 1
    assert '🤖 AI & ML' in categories
    assert '🔥 Top Stories' not in categories

def test_categorize_news_empty_input():
    """Test categorize_news with empty input list."""
    assert categorize_news([]) == {}


def test_create_simple_digest_empty():
    """Test create_simple_digest handles empty inputs gracefully for both languages."""
    # Test 'en' language
    assert create_simple_digest([], 'en') == "📭 No news found today. Check back later!"

    # Test 'ru' language
    assert create_simple_digest([], 'ru') == "📭 Сегодня новостей нет. Проверьте позже!"


@patch('functions.fallback_digest.get_current_date_baku')
def test_create_simple_digest_populated(mock_get_date):
    """Test create_simple_digest formats a list correctly."""

    # Set mock date
    mock_date = datetime(2025, 3, 19, tzinfo=BAKU_TZ)
    mock_get_date.return_value = mock_date

    news_items = [
        {"title": "OpenAI drops a new model", "url": "http://openai.com", "source": "OpenAI", "score": 300},
        # Use explicit business keyword 'startup'
        {"title": "New startup gets funding", "url": "http://techcrunch.com", "source": "TechCrunch", "score": 150},
        {"title": "A random news item", "source": "Some Blog", "score": 10} # Missing URL
    ]

    # Test English
    digest_en = create_simple_digest(news_items, 'en')

    # Assert header and footer
    assert "📰 **Tech News**\n_2025-03-19_" in digest_en
    assert "_💡 Automatically curated digest_" in digest_en

    # Assert top story presence
    assert "**🔥 Top Stories**" in digest_en
    assert "🤖 [OpenAI drops a new model](http://openai.com) `(300↑)`" in digest_en

    # Business presence
    assert "**💼 Business & Startups**" in digest_en
    assert "💻 [New startup gets funding](http://techcrunch.com) `(150↑)`" in digest_en

    # Assert other story presence
    assert "**📰 Other News**" in digest_en
    assert "📄 A random news item `(10↑)`" in digest_en


    # Test Russian
    digest_ru = create_simple_digest(news_items, 'ru')

    # Assert header and footer
    assert "📰 **Новости технологий**\n_19.03.2025_" in digest_ru
    assert "_💡 Дайджест создан автоматически_" in digest_ru

    # Ensure story content is still present in Russian digest
    assert "**🔥 Top Stories**" in digest_ru
    assert "🤖 [OpenAI drops a new model](http://openai.com) `(300↑)`" in digest_ru


@patch('functions.fallback_digest.get_current_date_baku')
def test_create_simple_digest_limits(mock_get_date):
    """Test create_simple_digest limits items appropriately."""
    mock_get_date.return_value = datetime(2025, 3, 19, tzinfo=BAKU_TZ)

    # Create 20 "Other News" items
    news_items = [{"title": f"Other item {i}", "score": 10} for i in range(20)]

    digest_en = create_simple_digest(news_items, 'en')

    # First, only top 15 items should be considered, all falling into "Other News"
    # Second, within "Other News", only max 5 items should be shown

    # Check that up to item 4 (5th item) are present
    for i in range(5):
        assert f"Other item {i}" in digest_en

    # Check that item 5 (6th item) and onwards are NOT present
    for i in range(5, 20):
        assert f"Other item {i}" not in digest_en


def test_create_raw_list_empty():
    """Test create_raw_list handles empty lists correctly."""
    assert create_raw_list([], 'en') == "📭 No news available"
    assert create_raw_list([], 'ru') == "📭 Нет новостей"

def test_create_raw_list_populated():
    """Test create_raw_list correctly formats items with and without URLs."""
    news_items = [
        {"title": "Story with URL", "url": "http://example.com"},
        {"title": "Story without URL"}
    ]

    # Test English
    digest_en = create_raw_list(news_items, 'en')
    assert "📰 **Tech News**\n\n" in digest_en
    assert "1. [Story with URL](http://example.com)" in digest_en
    assert "2. Story without URL" in digest_en

    # Test Russian
    digest_ru = create_raw_list(news_items, 'ru')
    assert "📰 **Новости технологий**\n\n" in digest_ru
    assert "1. [Story with URL](http://example.com)" in digest_ru
    assert "2. Story without URL" in digest_ru

def test_create_raw_list_limits():
    """Test create_raw_list enforces the 20-item limit."""
    news_items = [{"title": f"Item {i}", "url": f"http://example.com/{i}"} for i in range(25)]

    digest = create_raw_list(news_items)

    # First 20 should be present
    assert "20. [Item 19](http://example.com/19)" in digest

    # 21st shouldn't be present
    assert "21." not in digest
    assert "Item 20" not in digest
