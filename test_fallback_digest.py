from datetime import datetime, timedelta
from unittest.mock import patch

from functions.fallback_digest import (
    BAKU_TZ,
    categorize_news,
    create_raw_list,
    create_simple_digest,
    get_current_date_baku,
    get_source_emoji,
)


def test_get_current_date_baku():
    now = get_current_date_baku()

    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.tzinfo.utcoffset(now) == timedelta(hours=4)


def test_get_source_emoji():
    cases = {
        "Hacker News": "📰",
        "HN": "📰",
        "TechCrunch": "💻",
        "The Verge": "📱",
        "GitHub": "🔥",
        "Anthropic": "🤖",
        "Google Blog": "🧠",
        "DeepMind": "🧠",
        "OpenAI": "🤖",
        "Mistral AI": "🌪️",
        "Some Random Blog": "📄",
    }

    for source, expected in cases.items():
        assert get_source_emoji(source) == expected


def test_categorize_news_groups_articles():
    categories = categorize_news(
        [
            {"title": "Important top story", "score": 250},
            {"title": "New OpenAI model released", "score": 50},
            {"title": "Learn Machine Learning basics", "score": 0},
            {"title": "Awesome open source framework version 2.0", "score": 10},
            {"title": "Acquisition of new startup for $1B", "score": 100},
            {"title": "Just some regular interesting article", "score": 10},
            {"title": "Another random news", "score": None},
        ]
    )

    assert len(categories["🔥 Top Stories"]) == 1
    assert len(categories["🤖 AI & ML"]) == 2
    assert len(categories["🛠️ Tools & Products"]) == 1
    assert len(categories["💼 Business & Startups"]) == 1
    assert len(categories["📰 Other News"]) == 2
    assert categories["🔥 Top Stories"][0]["title"] == "Important top story"
    assert categories["🤖 AI & ML"][0]["title"] == "New OpenAI model released"
    assert categories["📰 Other News"][1]["title"] == "Another random news"


def test_categorize_news_empty_input():
    assert categorize_news([]) == {}


def test_categorize_news_handles_missing_fields():
    categories = categorize_news([{}, {"score": 10}, {"title": "AI missing score"}])

    assert len(categories.get("📰 Other News", [])) == 2
    assert len(categories.get("🤖 AI & ML", [])) == 1


def test_categorize_news_is_case_insensitive():
    categories = categorize_news(
        [
            {"title": "MACHINE LEARNING rules", "score": 10},
            {"title": "aWeSoMe LaUnCh", "score": 10},
        ]
    )

    assert len(categories["🤖 AI & ML"]) == 1
    assert len(categories["🛠️ Tools & Products"]) == 1


def test_categorize_news_treats_raise_as_business_keyword():
    categories = categorize_news(
        [
            {"title": "Startup secures $10M Series B funding", "score": 5},
            {"title": "Big acquisition in tech", "score": 100},
            {"title": "Company to raise new funds", "score": 50},
        ]
    )

    assert list(categories.keys()) == ["💼 Business & Startups"]
    assert len(categories["💼 Business & Startups"]) == 3


def test_create_simple_digest_empty():
    assert create_simple_digest([], "en") == "📭 No news found today. Check back later!"
    assert create_simple_digest([], "ru") == "📭 Сегодня новостей нет. Проверьте позже!"


@patch("functions.fallback_digest.get_current_date_baku")
def test_create_simple_digest_populated(mock_get_date):
    mock_get_date.return_value = datetime(2025, 3, 19, tzinfo=BAKU_TZ)
    digest_en = create_simple_digest(
        [
            {"title": "OpenAI drops a new model", "url": "http://openai.com", "source": "OpenAI", "score": 300},
            {"title": "New startup gets funding", "url": "http://techcrunch.com", "source": "TechCrunch", "score": 150},
            {"title": "A random news item", "source": "Some Blog", "score": 10},
        ],
        "en",
    )

    assert "📰 **Tech News**\n_2025-03-19_" in digest_en
    assert "_💡 Automatically curated digest_" in digest_en
    assert "**🔥 Top Stories**" in digest_en
    assert "1. 🤖 [OpenAI drops a new model](http://openai.com) `(300↑)`" in digest_en
    assert "**💼 Business & Startups**" in digest_en
    assert "1. 💻 [New startup gets funding](http://techcrunch.com) `(150↑)`" in digest_en
    assert "**📰 Other News**" in digest_en
    assert "1. 📄 A random news item `(10↑)`" in digest_en

    digest_ru = create_simple_digest(
        [
            {"title": "OpenAI drops a new model", "url": "http://openai.com", "source": "OpenAI", "score": 300},
            {"title": "New startup gets funding", "url": "http://techcrunch.com", "source": "TechCrunch", "score": 150},
            {"title": "A random news item", "source": "Some Blog", "score": 10},
        ],
        "ru",
    )

    assert "📰 **Новости технологий**\n_19.03.2025_" in digest_ru
    assert "_💡 Дайджест создан автоматически_" in digest_ru
    assert "**🔥 Top Stories**" in digest_ru
    assert "1. 🤖 [OpenAI drops a new model](http://openai.com) `(300↑)`" in digest_ru


@patch("functions.fallback_digest.get_current_date_baku")
def test_create_simple_digest_limits(mock_get_date):
    mock_get_date.return_value = datetime(2025, 3, 19, tzinfo=BAKU_TZ)
    digest = create_simple_digest(
        [{"title": f"Other item {i}", "score": 10} for i in range(20)],
        "en",
    )

    for i in range(5):
        assert f"Other item {i}" in digest

    for i in range(5, 20):
        assert f"Other item {i}" not in digest


def test_create_raw_list_empty():
    assert create_raw_list([], "en") == "📭 No news available"
    assert create_raw_list([], "ru") == "📭 Нет новостей"


def test_create_raw_list_populated():
    news_items = [
        {"title": "Story with URL", "url": "http://example.com"},
        {"title": "Story without URL"},
    ]

    digest_en = create_raw_list(news_items, "en")
    assert "📰 **Tech News**\n\n" in digest_en
    assert "1. [Story with URL](http://example.com)" in digest_en
    assert "2. Story without URL" in digest_en

    digest_ru = create_raw_list(news_items, "ru")
    assert "📰 **Новости технологий**\n\n" in digest_ru
    assert "1. [Story with URL](http://example.com)" in digest_ru
    assert "2. Story without URL" in digest_ru


def test_create_raw_list_limits():
    digest = create_raw_list(
        [{"title": f"Item {i}", "url": f"http://example.com/{i}"} for i in range(25)],
        "en",
    )

    assert "20. [Item 19](http://example.com/19)" in digest
    assert "21." not in digest
    assert "Item 20" not in digest
