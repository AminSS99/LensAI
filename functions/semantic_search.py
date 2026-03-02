"""
Semantic Search (Lightweight)
Provides relevance scoring over saved articles without external embeddings.
"""

from typing import Dict, List, Any
import re
from difflib import SequenceMatcher


SYNONYMS = {
    "ai": {"artificial intelligence", "llm", "gpt", "model", "machine learning"},
    "security": {"cyber", "vulnerability", "exploit", "breach", "privacy"},
    "startup": {"funding", "vc", "investment", "series a", "series b"},
    "crypto": {"bitcoin", "ethereum", "blockchain", "web3", "defi"},
}


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
    return tokens


def _expand_query_terms(query: str) -> set:
    terms = set(_tokenize(query))
    expanded = set(terms)
    for term in terms:
        if term in SYNONYMS:
            expanded.update(SYNONYMS[term])
    return expanded


def _jaccard_score(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def semantic_search_articles(query: str, articles: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Rank article list by lightweight semantic relevance.
    """
    if not query or not articles:
        return []

    query_terms = _expand_query_terms(query)
    query_lower = query.lower().strip()
    results = []

    for article in articles:
        title = article.get("title", "")
        source = article.get("source", "")
        category = article.get("category", "")
        text = f"{title} {source} {category}".lower()
        article_terms = set(_tokenize(text))

        jaccard = _jaccard_score(query_terms, article_terms)
        fuzzy = SequenceMatcher(None, query_lower, text).ratio()
        direct = 0.35 if query_lower in text else 0.0

        score = (0.6 * jaccard) + (0.3 * fuzzy) + direct
        if score > 0.12:
            enriched = article.copy()
            enriched["_semantic_score"] = round(score, 4)
            results.append(enriched)

    results.sort(key=lambda x: x.get("_semantic_score", 0.0), reverse=True)
    return results[:limit]
