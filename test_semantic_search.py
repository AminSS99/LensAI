import pytest
from functions.semantic_search import semantic_search_articles, _tokenize, _expand_query_terms, _jaccard_score

def test_empty_inputs():
    assert semantic_search_articles("", [{"title": "test"}]) == []
    assert semantic_search_articles("test", []) == []
    assert semantic_search_articles("", []) == []

def test_semantic_ranking_order():
    articles = [
        {"id": 1, "title": "A random article about cooking", "source": "Blog", "category": "Food"},
        {"id": 2, "title": "The future of AI and machine learning", "source": "TechCrunch", "category": "Technology"},
        {"id": 3, "title": "Crypto startup raises series A", "source": "CoinDesk", "category": "Business"}
    ]
    # Exact match "AI and machine learning"
    res = semantic_search_articles("ai and machine learning", articles)
    assert len(res) >= 1
    assert res[0]["id"] == 2

    res = semantic_search_articles("crypto startup", articles)
    assert len(res) >= 1
    assert res[0]["id"] == 3

def test_synonym_expansion():
    articles = [
        {"id": 1, "title": "New LLM model released", "source": "AI News", "category": "Tech"}
    ]
    res = semantic_search_articles("ai", articles)
    assert len(res) == 1
    assert res[0]["id"] == 1

def test_limit_results():
    articles = [{"id": i, "title": "AI startup news"} for i in range(15)]
    res = semantic_search_articles("ai startup", articles, limit=5)
    assert len(res) == 5

def test_score_threshold():
    articles = [
        {"id": 1, "title": "Completely irrelevant cooking recipe"}
    ]
    res = semantic_search_articles("crypto startup funding", articles)
    assert len(res) == 0

def test_tokenize():
    assert _tokenize("Hello, World! 123") == ["hello", "world", "123"]

def test_expand_query_terms():
    terms = _expand_query_terms("ai security")
    assert "llm" in terms
    assert "cyber" in terms

def test_jaccard_score():
    assert _jaccard_score({"a", "b"}, {"b", "c"}) == 1/3
    assert _jaccard_score(set(), {"a"}) == 0.0
    assert _jaccard_score({"a"}, set()) == 0.0

if __name__ == "__main__":
    pytest.main(["-v", "test_semantic_search.py"])
