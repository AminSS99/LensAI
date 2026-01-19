"""
Topic Clustering Module
Automatically groups related news articles by topic.
"""

from typing import Dict, List, Any
from collections import defaultdict
import re


# Topic keywords for classification
TOPIC_KEYWORDS = {
    'ai': [
        'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
        'neural', 'gpt', 'llm', 'openai', 'anthropic', 'deepmind', 'mistral',
        'gemini', 'claude', 'chatgpt', 'transformer', 'diffusion', 'stable diffusion',
        'midjourney', 'copilot', 'llama', 'generative ai', 'foundation model',
        'language model', 'computer vision', 'nlp', 'agi', 'superintelligence'
    ],
    'security': [
        'security', 'hack', 'breach', 'vulnerability', 'cyber', 'malware',
        'ransomware', 'privacy', 'encryption', 'exploit', 'attack', 'phishing',
        'ddos', 'zero-day', 'password', 'authentication', 'firewall', 'vpn'
    ],
    'crypto': [
        'crypto', 'bitcoin', 'ethereum', 'blockchain', 'web3', 'nft', 'defi',
        'token', 'wallet', 'mining', 'solana', 'binance', 'coinbase', 'btc', 'eth'
    ],
    'startups': [
        'startup', 'funding', 'series a', 'series b', 'series c', 'vc', 'venture',
        'unicorn', 'valuation', 'raised', 'investment', 'seed round', 'ipo',
        'acquisition', 'acquired', 'merger', 'y combinator', 'accelerator'
    ],
    'hardware': [
        'hardware', 'chip', 'cpu', 'gpu', 'nvidia', 'amd', 'intel', 'apple silicon',
        'processor', 'semiconductor', 'device', 'quantum', 'robotics', 'drone',
        'm4', 'snapdragon', 'arm', 'risc-v'
    ],
    'software': [
        'software', 'app', 'update', 'release', 'version', 'feature', 'tool',
        'platform', 'saas', 'api', 'sdk', 'framework', 'library', 'open source',
        'github', 'developer', 'programming', 'code'
    ],
    'big_tech': [
        'google', 'apple', 'microsoft', 'amazon', 'meta', 'facebook', 'tesla',
        'netflix', 'twitter', 'x.com', 'tiktok', 'bytedance', 'spotify'
    ],
    'mobile': [
        'iphone', 'android', 'ios', 'samsung', 'pixel', 'mobile', 'smartphone',
        'tablet', 'ipad', 'wearable', 'smartwatch', 'airpods'
    ],
    'gaming': [
        'game', 'gaming', 'playstation', 'xbox', 'nintendo', 'steam', 'esports',
        'vr', 'virtual reality', 'ar', 'augmented reality', 'metaverse'
    ],
    'science': [
        'research', 'study', 'scientist', 'discovery', 'experiment', 'nasa',
        'space', 'rocket', 'satellite', 'mars', 'moon', 'climate', 'energy'
    ]
}

# Topic display info with emojis
TOPIC_DISPLAY = {
    'ai': {'emoji': '🤖', 'en': 'AI & Machine Learning', 'ru': 'ИИ и машинное обучение'},
    'security': {'emoji': '🔒', 'en': 'Security & Privacy', 'ru': 'Безопасность и приватность'},
    'crypto': {'emoji': '💰', 'en': 'Crypto & Blockchain', 'ru': 'Криптовалюты и блокчейн'},
    'startups': {'emoji': '🚀', 'en': 'Startups & Funding', 'ru': 'Стартапы и инвестиции'},
    'hardware': {'emoji': '💻', 'en': 'Hardware & Chips', 'ru': 'Железо и процессоры'},
    'software': {'emoji': '📱', 'en': 'Software & Dev Tools', 'ru': 'Софт и инструменты'},
    'big_tech': {'emoji': '🏢', 'en': 'Big Tech', 'ru': 'Крупные компании'},
    'mobile': {'emoji': '📲', 'en': 'Mobile & Devices', 'ru': 'Мобильные устройства'},
    'gaming': {'emoji': '🎮', 'en': 'Gaming & VR', 'ru': 'Игры и VR'},
    'science': {'emoji': '🔬', 'en': 'Science & Space', 'ru': 'Наука и космос'},
    'general': {'emoji': '📰', 'en': 'General Tech', 'ru': 'Общие новости'}
}


def extract_topic(title: str, url: str = "") -> str:
    """
    Extract the primary topic from an article title and URL.
    
    Args:
        title: Article title
        url: Article URL (optional, used for additional context)
        
    Returns:
        Topic key (e.g., 'ai', 'security', 'crypto')
    """
    text = (title + " " + url).lower()
    
    # Score each topic by keyword matches
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        # Bonus for exact word matches
        words = set(re.findall(r'\b\w+\b', text))
        score += sum(2 for kw in keywords if kw in words and len(kw) > 2)
        if score > 0:
            scores[topic] = score
    
    if scores:
        return max(scores, key=scores.get)
    return 'general'


def cluster_articles(articles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group articles by their primary topic.
    
    Args:
        articles: List of article dicts with 'title' and optionally 'url'
        
    Returns:
        Dict mapping topic to list of articles
    """
    clusters = defaultdict(list)
    
    for article in articles:
        title = article.get('title', '')
        url = article.get('url', '')
        topic = extract_topic(title, url)
        
        # Add topic to article for reference
        article['topic'] = topic
        clusters[topic].append(article)
    
    # Sort clusters by number of articles (descending)
    sorted_clusters = dict(sorted(
        clusters.items(),
        key=lambda x: len(x[1]),
        reverse=True
    ))
    
    return sorted_clusters


def get_topic_label(topic: str, lang: str = 'en') -> str:
    """
    Get display label for a topic with emoji.
    
    Args:
        topic: Topic key
        lang: Language code ('en' or 'ru')
        
    Returns:
        Formatted topic label like "🤖 AI & Machine Learning"
    """
    info = TOPIC_DISPLAY.get(topic, TOPIC_DISPLAY['general'])
    emoji = info['emoji']
    label = info.get(lang, info['en'])
    return f"{emoji} {label}"


def format_clustered_articles(clusters: Dict[str, List[Dict[str, Any]]], lang: str = 'en') -> str:
    """
    Format clustered articles for display.
    
    Args:
        clusters: Dict from cluster_articles()
        lang: Language code
        
    Returns:
        Formatted string with articles grouped by topic
    """
    output = []
    
    for topic, articles in clusters.items():
        label = get_topic_label(topic, lang)
        output.append(f"\n**{label}** ({len(articles)})")
        output.append("-" * 30)
        
        for article in articles[:5]:  # Limit per topic
            title = article.get('title', 'Untitled')[:60]
            source = article.get('source', '')
            output.append(f"• {title}")
            if source:
                output.append(f"  _{source}_")
    
    return "\n".join(output)


def get_topic_counts(articles: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Get count of articles per topic (for trend analysis).
    
    Args:
        articles: List of articles
        
    Returns:
        Dict mapping topic to article count
    """
    clusters = cluster_articles(articles)
    return {topic: len(articles) for topic, articles in clusters.items()}
