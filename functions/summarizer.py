"""
DeepSeek Summarization Module
Uses DeepSeek API to summarize and format tech news digest.
"""

import os
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from openai import AsyncOpenAI
import asyncio
from .resilience import retry_with_backoff
from .fallback_digest import create_simple_digest, create_raw_list

# Baku timezone (UTC+4)
BAKU_TZ = timezone(timedelta(hours=4))

def get_current_date_baku() -> str:
    """Get current date in Baku timezone."""
    return datetime.now(BAKU_TZ).strftime('%Y-%m-%d')


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
    'DeepSeek': '🔍',
    'Qwen': '🔮',
    'Minimax': '🎯',
    'Kimi': '🌙',
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


def get_system_prompt() -> str:
    """Generate system prompt with current date."""
    current_date = get_current_date_baku()
    return f"""You are a professional tech news digest creator. Today is {current_date}.

Create a Telegram digest following this EXACT format:

HEADER:
🔥 Techdigest | {current_date}

CATEGORIES (use ### for headers):
### 🔥 Top Stories
### 🤖 AI News  
### 🛠️ Tools
### 💼 Industry

EACH ITEM FORMAT:
• **Title** — brief 1-sentence summary. (Source) ~X min | [Read](url)

RULES:
- Maximum 8-10 items total
- Keep summaries to ONE sentence
- Use bullet points (•) not asterisks
- Put the link text as just "Read" or "Читать"
- NO intro paragraph, start directly with first category
- End with: 💡 **Insight:** one brief observation

IMPORTANT: Skip old or repeated news. Be concise."""


USER_PROMPT_TEMPLATE = """Here are today's tech news items. Please create a curated digest:

{news_content}

Create an engaging Telegram-friendly digest with the most important stories."""


async def summarize_news(news_items: List[Dict[str, Any]], max_items: int = 30, language: str = 'en') -> str:
    """
    Summarize a list of news items into a formatted digest.
    Uses DeepSeek AI with fallback to simple formatting if AI fails.
    
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
    
    # Shuffle to get variety, then limit
    import random
    shuffled_items = news_items.copy()
    random.shuffle(shuffled_items)
    items_to_summarize = shuffled_items[:max_items]
    
    # Get current date for header
    current_date = datetime.now(BAKU_TZ)
    if language == 'ru':
        date_header = f"🔥 Технодайджест | {current_date.strftime('%d.%m.%Y')}\n\n"
    else:
        date_header = f"🔥 Techdigest | {current_date.strftime('%Y-%m-%d')}\n\n"
    
    # Try AI summarization first
    try:
        digest = await _ai_summarize(items_to_summarize, language)
        # Prepend our own date header (AI might ignore the date instruction)
        if not digest.startswith("🔥"):
            digest = date_header + digest
        return digest
    except Exception as e:
        print(f"AI summarization failed: {e}. Falling back to simple digest.")
        # Fallback to simple digest without AI
        try:
            return date_header + create_simple_digest(items_to_summarize, language)
        except Exception as e2:
            print(f"Simple digest failed: {e2}. Falling back to raw list.")
            # Last resort: raw list
            return date_header + create_raw_list(items_to_summarize, language)


@retry_with_backoff(max_retries=2, base_delay=1.0, max_delay=5.0)
async def _ai_summarize(news_items: List[Dict[str, Any]], language: str) -> str:
    """
    Internal function to call DeepSeek AI with retry logic.
    
    Raises:
        Exception if AI summarization fails after retries
    """
    # Format news for the prompt
    news_content = format_news_for_prompt(news_items)
    
    # Language-specific prompts
    if language == 'ru':
        current_date = get_current_date_baku()
        date_formatted = datetime.now(BAKU_TZ).strftime('%d.%m.%Y')
        system_prompt = f"""Ты создатель профессионального дайджеста новостей. Сегодня {date_formatted}.

Создай дайджест для Telegram СТРОГО по этому формату:

ЗАГОЛОВОК:
🔥 Технодайджест | {date_formatted}

КАТЕГОРИИ (используй ### для заголовков):
### 🔥 Главное
### 🤖 ИИ Новости
### 🛠️ Инструменты
### 💼 Индустрия

ФОРМАТ КАЖДОЙ НОВОСТИ:
• **Заголовок** — краткое описание в 1 предложение. (Источник) ~X мин | [Читать](url)

ПРАВИЛА:
- Максимум 8-10 новостей
- Описание в ОДНО предложение
- Используй буллеты (•) не звёздочки
- Ссылка просто "Читать"
- БЕЗ вступительного абзаца, сразу с первой категории
- В конце: 💡 **Инсайт:** краткое наблюдение

ВАЖНО: Пропускай старые или повторяющиеся новости. Будь кратким."""
        user_prompt = f"""Вот сегодняшние новости. Создай дайджест НА РУССКОМ:

{news_content}"""
    else:
        system_prompt = get_system_prompt()
        user_prompt = USER_PROMPT_TEMPLATE.format(news_content=news_content)
    
    client = get_async_client()
    
    # Add timeout to prevent hanging
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            ),
            timeout=45.0  # 45 second timeout
        )
        
        return response.choices[0].message.content
        
    except asyncio.TimeoutError:
        raise Exception("DeepSeek API timeout after 45 seconds")
    except Exception as e:
        raise Exception(f"DeepSeek API error: {str(e)}")


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

