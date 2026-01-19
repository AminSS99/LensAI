"""
Smart Deduplication Module
Detects and merges duplicate news stories from different sources.
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import re
from collections import defaultdict


@dataclass
class MergedArticle:
    """Represents merged duplicate articles."""
    primary: Dict[str, Any]  # Main article to display
    duplicates: List[Dict[str, Any]]  # Other sources covering same story
    source_count: int  # Total number of sources
    
    def get_sources_label(self) -> str:
        """Get label like '[+2 sources]' if duplicates exist."""
        if self.source_count > 1:
            return f"[+{self.source_count - 1} sources]"
        return ""


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    
    - Lowercase
    - Remove special characters
    - Remove common words
    """
    text = text.lower()
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove special characters
    text = re.sub(r'[^\w\s]', ' ', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def extract_keywords(text: str) -> set:
    """
    Extract meaningful keywords from text.
    Removes stopwords and short words.
    """
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'it', 'its', 'how', 'why', 'what', 'when', 'where', 'who',
        'new', 'just', 'now', 'says', 'said', 'get', 'got', 'goes', 'going',
        'more', 'most', 'first', 'last', 'over', 'into', 'about', 'your'
    }
    
    normalized = normalize_text(text)
    words = set(normalized.split())
    
    # Remove stopwords and short words
    keywords = {w for w in words if w not in stopwords and len(w) > 2}
    return keywords


def calculate_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity score between two article titles.
    Uses Jaccard similarity of keywords.
    
    Args:
        title1: First article title
        title2: Second article title
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    keywords1 = extract_keywords(title1)
    keywords2 = extract_keywords(title2)
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2
    
    # Jaccard similarity
    jaccard = len(intersection) / len(union) if union else 0.0
    
    # Boost score if significant keywords match
    significant_keywords = {
        'openai', 'google', 'apple', 'microsoft', 'meta', 'amazon', 'nvidia',
        'tesla', 'chatgpt', 'gpt', 'claude', 'gemini', 'bitcoin', 'ethereum'
    }
    
    sig_matches = intersection & significant_keywords
    if sig_matches:
        jaccard = min(1.0, jaccard + 0.2 * len(sig_matches))
    
    return jaccard


def find_duplicates(articles: List[Dict[str, Any]], 
                    threshold: float = 0.45) -> List[List[int]]:
    """
    Find groups of duplicate articles.
    
    Args:
        articles: List of article dicts
        threshold: Minimum similarity to consider duplicate (0.0-1.0)
        
    Returns:
        List of duplicate groups (each group is list of article indices)
    """
    n = len(articles)
    if n == 0:
        return []
    
    # Track which articles are already grouped
    grouped = set()
    groups = []
    
    for i in range(n):
        if i in grouped:
            continue
            
        title_i = articles[i].get('title', '')
        if not title_i:
            continue
            
        # Find all articles similar to this one
        group = [i]
        
        for j in range(i + 1, n):
            if j in grouped:
                continue
                
            title_j = articles[j].get('title', '')
            if not title_j:
                continue
            
            similarity = calculate_similarity(title_i, title_j)
            
            if similarity >= threshold:
                group.append(j)
                grouped.add(j)
        
        if len(group) > 1:
            grouped.add(i)
            groups.append(group)
    
    return groups


def merge_duplicates(articles: List[Dict[str, Any]], 
                     threshold: float = 0.45) -> List[MergedArticle]:
    """
    Merge duplicate articles from different sources.
    
    Prioritizes articles from more authoritative sources.
    
    Args:
        articles: List of article dicts
        threshold: Similarity threshold for duplicates
        
    Returns:
        List of MergedArticle objects
    """
    # Source priority (higher = more authoritative)
    source_priority = {
        'TechCrunch': 10,
        'The Verge': 9,
        'Hacker News': 8,
        'AI Blogs': 7,
        'GitHub': 6,
    }
    
    duplicate_groups = find_duplicates(articles, threshold)
    
    # Track which articles are duplicates
    duplicate_indices = set()
    for group in duplicate_groups:
        duplicate_indices.update(group)
    
    merged_results = []
    
    # Process duplicate groups
    for group in duplicate_groups:
        group_articles = [articles[i] for i in group]
        
        # Sort by source priority (descending)
        group_articles.sort(
            key=lambda a: source_priority.get(a.get('source', ''), 0),
            reverse=True
        )
        
        primary = group_articles[0]
        duplicates = group_articles[1:]
        
        merged = MergedArticle(
            primary=primary,
            duplicates=duplicates,
            source_count=len(group_articles)
        )
        merged_results.append(merged)
    
    # Add non-duplicate articles
    for i, article in enumerate(articles):
        if i not in duplicate_indices:
            merged = MergedArticle(
                primary=article,
                duplicates=[],
                source_count=1
            )
            merged_results.append(merged)
    
    return merged_results


def deduplicate_articles(articles: List[Dict[str, Any]], 
                         threshold: float = 0.45) -> List[Dict[str, Any]]:
    """
    Deduplicate articles and add source count info.
    
    Returns articles with added '_source_count' and '_sources_label' fields.
    
    Args:
        articles: List of article dicts
        threshold: Similarity threshold
        
    Returns:
        Deduplicated list with source info added
    """
    merged = merge_duplicates(articles, threshold)
    
    result = []
    for m in merged:
        article = m.primary.copy()
        article['_source_count'] = m.source_count
        article['_sources_label'] = m.get_sources_label()
        
        # Add list of all source names
        all_sources = [m.primary.get('source', '')]
        all_sources.extend([d.get('source', '') for d in m.duplicates])
        article['_all_sources'] = [s for s in all_sources if s]
        
        result.append(article)
    
    return result


def format_deduped_for_display(article: Dict[str, Any]) -> str:
    """
    Format a deduplicated article for display.
    
    Example: "OpenAI announces GPT-5 [+2 sources]"
    """
    title = article.get('title', 'Untitled')
    sources_label = article.get('_sources_label', '')
    
    if sources_label:
        return f"{title} {sources_label}"
    return title
