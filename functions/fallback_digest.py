"""
Fallback Digest Generator
Creates simple, formatted digests without AI when DeepSeek API fails.
"""

from typing import List, Dict, Any
from datetime import datetime


def get_source_emoji(source: str) -> str:
    """Get emoji for a news source."""
    source_lower = source.lower()
    
    if 'hacker' in source_lower or 'hn' in source_lower:
        return '📰'
    elif 'techcrunch' in source_lower:
        return '💻'
    elif 'verge' in source_lower:
        return '📱'
    elif 'github' in source_lower:
        return '🔥'
    elif 'anthropic' in source_lower:
        return '🤖'
    elif 'google' in source_lower or 'deepmind' in source_lower:
        return '🧠'
    elif 'openai' in source_lower:
        return '🤖'
    elif 'mistral' in source_lower:
        return '🌪️'
    else:
        return '📄'


def categorize_news(news_items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize news items by topic.
    
    Returns:
        Dictionary mapping category names to lists of articles
    """
    categories = {
        '🔥 Top Stories': [],
        '🤖 AI & ML': [],
        '🛠️ Tools & Products': [],
        '💼 Business & Startups': [],
        '📰 Other News': []
    }
    
    ai_keywords = ['ai', 'ml', 'machine learning', 'artificial intelligence', 'gpt', 'llm', 'neural', 'deep learning', 'openai', 'anthropic', 'deepmind', 'mistral', 'claude', 'gemini']
    tools_keywords = ['release', 'launch', 'tool', 'framework', 'library', 'app', 'update', 'version', 'open source']
    business_keywords = ['funding', 'startup', 'vc', 'acquisition', 'valuation', 'raise', 'investment', 'series']
    
    for item in news_items:
        title_lower = item.get('title', '').lower()
        score = item.get('score', 0)
        
        # Top stories (high score or from specific sources)
        if score and score > 200:
            categories['🔥 Top Stories'].append(item)
        # AI category
        elif any(kw in title_lower for kw in ai_keywords):
            categories['🤖 AI & ML'].append(item)
        # Tools category
        elif any(kw in title_lower for kw in tools_keywords):
            categories['🛠️ Tools & Products'].append(item)
        # Business category
        elif any(kw in title_lower for kw in business_keywords):
            categories['💼 Business & Startups'].append(item)
        # Default to other
        else:
            categories['📰 Other News'].append(item)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


def create_simple_digest(news_items: List[Dict[str, Any]], language: str = 'en') -> str:
    """
    Create a simple, formatted digest without AI.
    Falls back to this when DeepSeek API fails.
    
    Args:
        news_items: List of news articles
        language: Language code ('en' or 'ru')
        
    Returns:
        Formatted digest string
    """
    if not news_items:
        if language == 'ru':
            return "📭 Сегодня новостей нет. Проверьте позже!"
        return "📭 No news found today. Check back later!"
    
    # Limit to top 15 items
    items_to_show = news_items[:15]
    
    # Categorize news
    categorized = categorize_news(items_to_show)
    
    # Build digest
    if language == 'ru':
        header = f"📰 **Дайджест технологических новостей**\n_{datetime.now().strftime('%d.%m.%Y')}_\n\n"
        footer = "\n\n_💡 Дайджест создан автоматически_"
    else:
        header = f"📰 **Tech News Digest**\n_{datetime.now().strftime('%Y-%m-%d')}_\n\n"
        footer = "\n\n_💡 Automatically curated digest_"
    
    digest_parts = [header]
    
    # Add each category
    for category, articles in categorized.items():
        digest_parts.append(f"**{category}**\n")
        
        for i, article in enumerate(articles[:5], 1):  # Max 5 per category
            title = article.get('title', 'Untitled')
            url = article.get('url', '')
            source = article.get('source', 'Unknown')
            score = article.get('score', '')
            
            emoji = get_source_emoji(source)
            
            # Format article entry
            if url:
                entry = f"{i}. {emoji} [{title}]({url})"
            else:
                entry = f"{i}. {emoji} {title}"
            
            if score:
                entry += f" `({score}↑)`"
            
            digest_parts.append(entry)
        
        digest_parts.append("")  # Empty line between categories
    
    digest_parts.append(footer)
    
    return "\n".join(digest_parts)


def create_raw_list(news_items: List[Dict[str, Any]], language: str = 'en') -> str:
    """
    Create a simple bullet-point list of articles.
    Last resort fallback when everything else fails.
    
    Args:
        news_items: List of news articles
        language: Language code
        
    Returns:
        Simple list of articles
    """
    if not news_items:
        if language == 'ru':
            return "📭 Нет новостей"
        return "📭 No news available"
    
    if language == 'ru':
        header = "📰 **Новости технологий**\n\n"
    else:
        header = "📰 **Tech News**\n\n"
    
    lines = [header]
    
    for i, article in enumerate(news_items[:20], 1):
        title = article.get('title', 'Untitled')
        url = article.get('url', '')
        
        if url:
            lines.append(f"{i}. [{title}]({url})")
        else:
            lines.append(f"{i}. {title}")
    
    return "\n".join(lines)
