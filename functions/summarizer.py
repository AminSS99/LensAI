"""
DeepSeek Summarization Module
Uses DeepSeek API to summarize and format tech news digest.
"""

import os
from typing import List, Dict, Any
from openai import AsyncOpenAI
import asyncio


# DeepSeek uses OpenAI-compatible API
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_async_client() -> AsyncOpenAI:
    """Get DeepSeek Async API client."""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")
    
    return AsyncOpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL
    )


# Source emoji mapping
SOURCE_EMOJIS = {
    'Hacker News': '📰',
    'TechCrunch': '💻',
    'The Verge': '📱',
    'GitHub Trending': '🔥',
    'Anthropic': '🤖',
    'Google AI': '🧠',
    'Mistral AI': '🌪️',
    'DeepMind': '🔬',
    'Product Hunt': '🚀',
    'OpenAI': '🤖',
}


def get_source_emoji(source: str) -> str:
    """Get emoji for a news source."""
    for key, emoji in SOURCE_EMOJIS.items():
        if key.lower() in source.lower():
            return emoji
    return '📄'  # Default emoji


def format_news_for_prompt(news_items: List[Dict[str, Any]]) -> str:
    """Format news items for the summarization prompt with source emojis."""
    formatted = []
    
    for i, item in enumerate(news_items, 1):
        source = item.get('source', 'Unknown')
        emoji = get_source_emoji(source)
        title = item.get('title', 'No title')
        url = item.get('url', '')
        summary = item.get('summary', '')
        score = item.get('score', '')
        read_time = estimate_read_time(title, summary)
        
        entry = f"{i}. {emoji} [{source}] {title} (~{read_time} min)"
        if score:
            entry += f" (Score: {score})"
        if summary:
            entry += f"\n   Summary: {summary}"
        if url:
            entry += f"\n   URL: {url}"
        
        formatted.append(entry)
    
    return "\n\n".join(formatted)


def estimate_read_time(title: str, summary: str = "") -> int:
    """
    Estimate read time for an article in minutes.
    Based on average reading speed of 200 words per minute.
    """
    # Typical article length estimation based on title/summary
    title_words = len(title.split())
    summary_words = len(summary.split()) if summary else 0
    
    # Estimate full article length (title usually ~10% of article)
    estimated_words = max(title_words * 10, summary_words * 3, 200)
    
    # Calculate read time (minimum 1 minute)
    read_time = max(1, round(estimated_words / 200))
    
    # Cap at 15 minutes for very long articles
    return min(read_time, 15)


SYSTEM_PROMPT = """You are a tech news curator and summarizer. Your job is to:
1. Analyze the provided tech news items
2. Identify the most important and impactful stories
3. Create a concise, well-organized digest

Format your response as a Telegram message using these guidelines:
- Use emojis to make it visually appealing
- Group news by category (🔥 Top Stories, 🤖 AI News, 🛠️ New Tools, 💼 Industry News)
- Keep each summary to 1-2 sentences
- Include the source, read time (e.g. "~3 min"), and make URLs clickable
- Be conversational and engaging
- Maximum 10 items in total, prioritize quality over quantity
- End with a brief one-liner insight or observation

Target length: 500-800 words"""


USER_PROMPT_TEMPLATE = """Here are today's tech news items. Please create a curated digest:

{news_content}

Create an engaging Telegram-friendly digest with the most important stories."""


async def summarize_news(news_items: List[Dict[str, Any]], max_items: int = 30, language: str = 'en') -> str:
    """
    Summarize a list of news items into a formatted digest.
    
    Args:
        news_items: List of news items from scrapers
        max_items: Maximum items to send to API (to control token usage)
        language: Language code ('en', 'ru')
        
    Returns:
        Formatted markdown digest for Telegram
    """
    if not news_items:
        if language == 'ru':
            return "📭 Сегодня новостей нет. Проверьте позже!"
        return "📭 No tech news found today. Check back later!"
    
    # Limit items to control API costs
    items_to_summarize = news_items[:max_items]
    
    # Format news for the prompt
    news_content = format_news_for_prompt(items_to_summarize)
    
    # Language-specific prompts
    if language == 'ru':
        system_prompt = """Ты куратор и редактор технических новостей. Твоя задача:
1. Проанализировать предоставленные технические новости
2. Выбрать самые важные и значимые истории
3. Создать краткий, хорошо организованный дайджест НА РУССКОМ ЯЗЫКЕ

Формат ответа для Telegram:
- Используй эмодзи для визуальной привлекательности
- Группируй новости по категориям (🔥 Главное, 🤖 ИИ Новости, 🛠️ Инструменты, 💼 Индустрия)
- Краткое описание каждой новости в 1-2 предложениях
- Указывай источник, время чтения (например "~3 мин") и делай ссылки кликабельными
- Максимум 10 новостей, приоритет качеству
- В конце добавь краткий инсайт или наблюдение

ВАЖНО: Весь текст должен быть НА РУССКОМ ЯЗЫКЕ!"""
        user_prompt = f"""Вот сегодняшние технические новости. Создай дайджест НА РУССКОМ ЯЗЫКЕ:

{news_content}

Создай увлекательный дайджест для Telegram НА РУССКОМ ЯЗЫКЕ."""
    else:
        system_prompt = SYSTEM_PROMPT
        user_prompt = USER_PROMPT_TEMPLATE.format(news_content=news_content)
    
    try:
        client = get_async_client()
        
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error summarizing news: {e}")
        # Fallback to basic formatting
        return create_fallback_digest(items_to_summarize[:10])


def create_fallback_digest(news_items: List[Dict[str, Any]]) -> str:
    """Create a simple digest without AI if API fails."""
    lines = ["📰 *Tech News Digest*\\n"]
    
    for item in news_items:
        source = item.get('source', 'News')
        title = item.get('title', '')
        url = item.get('url', '')
        
        lines.append(f"• [{source}] {title}")
        if url:
            lines.append(f"  {url}")
        lines.append("")
    
    lines.append("\\n_Generated without AI summarization (API unavailable)_")
    return "\\n".join(lines)


async def quick_summary(text: str, max_length: int = 100) -> str:
    """
    Generate a quick one-liner summary of text.
    Useful for individual article summaries.
    """
    try:
        client = get_async_client()
        
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Summarize the following in one concise sentence."},
                {"role": "user", "content": text[:1000]}  # Limit input
            ],
            temperature=0.5,
            max_tokens=100
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error in quick_summary: {e}")
        return text[:max_length] + "..." if len(text) > max_length else text


if __name__ == "__main__":
    # Test with sample data
    sample_news = [
        {
            'title': 'OpenAI Releases GPT-5',
            'source': 'TechCrunch',
            'url': 'https://example.com/gpt5',
            'summary': 'The new model shows significant improvements in reasoning.'
        },
        {
            'title': 'Google Announces Gemini 2.0',
            'source': 'Google AI',
            'url': 'https://example.com/gemini2',
            'summary': 'Multimodal capabilities expanded with new features.'
        }
    ]
    
    print("Testing summarizer (requires DEEPSEEK_API_KEY)...")
    
    async def test():
        try:
            digest = await summarize_news(sample_news)
            print(digest)
        except ValueError as e:
            print(f"Skipping test: {e}")
            print("\\nFallback digest:")
            print(create_fallback_digest(sample_news))
            
    asyncio.run(test())

