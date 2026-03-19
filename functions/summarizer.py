"""
AI Summarization Module
Uses a configurable OpenAI-compatible provider to summarize and format
the tech news digest.
"""

import os
from typing import List, Dict, Any, Optional
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


# OpenAI-compatible API endpoints
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

DEFAULT_AI_PROVIDER = "gemini"
DEFAULT_AI_MODELS = {
    "gemini": "gemini-3-flash-preview",
    "deepseek": "deepseek-chat",
}


def get_ai_provider() -> str:
    """Resolve the active AI provider from env or available credentials."""
    configured = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if configured in DEFAULT_AI_MODELS:
        return configured
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    return DEFAULT_AI_PROVIDER


def get_chat_model() -> str:
    """Resolve the active chat model."""
    configured = (os.environ.get("AI_MODEL") or "").strip()
    if configured:
        return configured
    return DEFAULT_AI_MODELS[get_ai_provider()]


def get_async_client() -> AsyncOpenAI:
    """Get the configured Async API client."""
    provider = get_ai_provider()
    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        return AsyncOpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")
    return AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


async def chat_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 800,
    timeout: float = 45.0,
) -> str:
    """Run a chat completion on the configured provider/model."""
    provider = get_ai_provider()
    client = get_async_client()
    request: Dict[str, Any] = {
        "model": get_chat_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if provider == "gemini":
        request["reasoning_effort"] = os.environ.get("GEMINI_REASONING_EFFORT", "low")

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(**request),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise Exception(f"{provider.title()} API timeout after {int(timeout)} seconds") from exc
    except Exception as exc:
        raise Exception(f"{provider.title()} API error: {exc}") from exc

    content = response.choices[0].message.content
    if not content:
        raise Exception(f"{provider.title()} API returned empty content")
    return content


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
    return f"""You create polished Telegram tech digests. Today is {current_date}.

Respond only in English and use clean Markdown for Telegram.

Required structure:
### Top Stories
### AI & ML
### Tools
### Industry

Required format for every story:
• **Headline** — one short descriptive sentence.
  [Source: Publication Name](url)

Rules:
- Prefer 8-12 strong stories when enough good items exist
- Every item must include both a short description and a source link
- Keep descriptions to one concise sentence
- Skip stale, duplicate, or weak stories
- No intro paragraph and no extra title header
- End with `💡 **Why this matters:**` followed by one brief observation
"""


USER_PROMPT_TEMPLATE = """Here are today's tech news items. Please create a curated digest:

{news_content}

Create an engaging Telegram-friendly digest with the most important stories."""


def build_digest_context(news_items: List[Dict[str, Any]], language: str = 'en', limit: int = 10) -> str:
    """Build compact structured article context for follow-up actions."""
    labels = {
        'en': {
            'title': 'Title',
            'source': 'Source',
            'summary': 'Summary',
            'url': 'URL',
        },
        'ru': {
            'title': 'Заголовок',
            'source': 'Источник',
            'summary': 'Описание',
            'url': 'Ссылка',
        },
    }
    active = labels['ru'] if language == 'ru' else labels['en']
    lines: List[str] = []

    for index, item in enumerate(news_items[:limit], 1):
        title = (item.get('title') or 'Untitled').strip()
        source = (item.get('source') or 'Unknown').strip()
        summary = (item.get('summary') or '').strip()
        url = (item.get('url') or '').strip()

        lines.append(f"{index}. {active['title']}: {title}")
        lines.append(f"   {active['source']}: {source}")
        if summary:
            lines.append(f"   {active['summary']}: {summary[:280]}")
        if url:
            lines.append(f"   {active['url']}: {url}")

    return "\n".join(lines)


async def generate_why_digest(
    digest_content: str,
    articles_meta: Optional[List[Dict[str, Any]]] = None,
    language: str = 'en',
) -> str:
    """Generate a localized follow-up for the Why This Matters button."""
    articles_context = build_digest_context(articles_meta or [], language=language, limit=8)
    digest_excerpt = (digest_content or '')[:2800]

    if language == 'ru':
        system_prompt = """Ты объясняешь, почему новостной дайджест важен для читателя.

Отвечай только на русском и в таком формате:
**Почему это важно:**
• пункт 1
• пункт 2
• пункт 3

**Что сделать дальше:** одно короткое практическое действие.

Опирайся только на факты из дайджеста и списка статей. Не выдумывай детали."""
        user_prompt = (
            "Вот данные дайджеста.\n\n"
            f"Статьи:\n{articles_context or 'Нет структурированных данных.'}\n\n"
            f"Текст дайджеста:\n{digest_excerpt}"
        )
    else:
        system_prompt = """You explain why a tech news digest matters to the reader.

Reply only in English and use this format:
**Why this matters:**
• point 1
• point 2
• point 3

**What to do next:** one short practical action.

Use only details grounded in the digest and article list. Do not invent facts."""
        user_prompt = (
            "Here is the digest data.\n\n"
            f"Articles:\n{articles_context or 'No structured article data available.'}\n\n"
            f"Digest text:\n{digest_excerpt}"
        )

    return await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=320,
        timeout=25.0,
    )


def build_digest_prompts(news_content: str, language: str = 'en') -> tuple[str, str]:
    """Build localized digest prompts with a consistent output shape."""
    if language == 'ru':
        date_formatted = datetime.now(BAKU_TZ).strftime('%d.%m.%Y')
        system_prompt = f"""Ты создаёшь аккуратные Telegram-дайджесты о технологиях. Сегодня {date_formatted}.

Отвечай только на русском языке и используй Markdown.

Структура:
### Главное
### AI & ML
### Инструменты
### Индустрия

Формат каждой новости:
• **Заголовок** — одно короткое поясняющее предложение.
  [Источник: Название издания](url)

Правила:
- Предпочитай 8-12 сильных новостей, если хватает хороших материалов
- У каждой новости обязательно должны быть короткое описание и ссылка на источник
- Не добавляй вступление и отдельный заголовок с датой
- Пропускай повторы и слабые новости
- Заверши строкой `💡 **Почему это важно:**` и одним кратким наблюдением
"""
        user_prompt = (
            "Создай дайджест на русском языке по этим новостям:\n\n"
            f"{news_content}\n\n"
            "Предпочитай 8-12 сильных новостей, если хватает хороших материалов."
        )
        return system_prompt, user_prompt

    system_prompt = get_system_prompt()
    user_prompt = (
        USER_PROMPT_TEMPLATE.format(news_content=news_content)
        + "\n\nPrefer 8-12 strong stories if enough quality items exist. Every story must include a short description and a source link."
    )
    return system_prompt, user_prompt


async def summarize_news(news_items: List[Dict[str, Any]], max_items: int = 30, language: str = 'en') -> str:
    """
    Summarize a list of news items into a formatted digest.
    Uses the configured AI provider with fallback to simple formatting if AI fails.
    
    Now includes:
    - Smart deduplication (merges similar stories)
    - Topic clustering (groups by category)
    - Trend recording (tracks topic popularity)
    
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
    
    # Step 1: Deduplicate articles from different sources
    try:
        from .deduplication import deduplicate_articles
        items_to_summarize = deduplicate_articles(news_items, threshold=0.45)
        print(f"Deduplication: {len(news_items)} -> {len(items_to_summarize)} articles")
    except Exception as e:
        print(f"Deduplication failed: {e}")
        items_to_summarize = news_items
    
    # Step 2: Cluster articles by topic
    try:
        from .topic_clustering import cluster_articles, get_topic_counts
        clusters = cluster_articles(items_to_summarize)
        topic_counts = get_topic_counts(items_to_summarize)
        print(f"Clustered into topics: {list(topic_counts.keys())}")
    except Exception as e:
        print(f"Clustering failed: {e}")
        clusters = None
        topic_counts = None
    
    # Step 3: Record trends for future analysis
    try:
        if topic_counts:
            from .trend_analysis import record_daily_topics
            record_daily_topics(topic_counts)
    except Exception as e:
        print(f"Trend recording failed: {e}")

    # The max_items knob now directly controls how much context we feed into
    # the model and how many stories the fallback formatter can use.
    prompt_items = items_to_summarize[:max_items]
    
    # Get current date for header
    current_date = datetime.now(BAKU_TZ)
    if language == 'ru':
        date_header = f"🔥 Новости технологий | {current_date.strftime('%d.%m.%Y')}\n\n"
    else:
        date_header = f"🔥 Tech News | {current_date.strftime('%Y-%m-%d')}\n\n"
    
    # Try AI summarization first
    try:
        digest = await _ai_summarize(prompt_items, language)
        # Always prepend our own date header to ensure accuracy
        return date_header + digest
    except Exception as e:
        print(f"AI summarization failed: {e}. Falling back to simple digest.")
        # Fallback to simple digest without AI
        try:
            return date_header + create_simple_digest(prompt_items, language)
        except Exception as e2:
            print(f"Simple digest failed: {e2}. Falling back to raw list.")
            # Last resort: raw list
            return date_header + create_raw_list(prompt_items, language)


@retry_with_backoff(max_retries=2, base_delay=1.0, max_delay=5.0)
async def _ai_summarize(news_items: List[Dict[str, Any]], language: str) -> str:
    """
    Internal function to call the configured AI provider with retry logic.
    
    Raises:
        Exception if AI summarization fails after retries
    """
    # Format news for the prompt
    news_content = format_news_for_prompt(news_items)

    # Use a single prompt builder so English and Russian stay aligned.
    system_prompt, user_prompt = build_digest_prompts(news_content, language)
    return await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=2200,
        timeout=45.0,
    )
    
    # Language-specific prompts
    if language == 'ru':
        current_date = get_current_date_baku()
        date_formatted = datetime.now(BAKU_TZ).strftime('%d.%m.%Y')
        system_prompt = f"""Ты создатель профессионального дайджеста новостей. Сегодня {date_formatted}.

Создай дайджест для Telegram СТРОГО по этому формату:

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
- БЕЗ вступительного абзаца, БЕЗ заголовка с датой, сразу с первой категории
- В конце: 💡 **Инсайт:** краткое наблюдение

ВАЖНО: Пропускай старые или повторяющиеся новости. Будь кратким."""
        user_prompt = f"""Вот сегодняшние новости. Создай дайджест НА РУССКОМ:

{news_content}

РџСЂРµРґРїРѕС‡С‚РёС‚РµР»СЊРЅРѕ РІРєР»СЋС‡Рё 12-14 СЃРёР»СЊРЅС‹С… РЅРѕРІРѕСЃС‚РµР№, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ."""
        system_prompt = f"""You create polished Telegram tech digests. Today is {date_formatted}.

Respond entirely in Russian and follow this exact structure:
- Use category headers with `###`
- Categories:
  `### 🔥 Главное`
  `### 🤖 ИИ Новости`
  `### 🛠️ Инструменты`
  `### 💼 Индустрия`
- Each item format:
  `• **Заголовок** — 1-2 кратких предложения. (Источник) ~X мин | [Читать](url)`
- Target 12-14 strong stories when enough good items exist
- Skip stale or repetitive items
- Do not add an intro paragraph or a date header
- End with: `💡 **Инсайт:**` and one brief observation
"""
        user_prompt = (
            "Create the digest in Russian from these stories:\n\n"
            f"{news_content}\n\n"
            "Prefer 12-14 strong stories if available."
        )
    else:
        system_prompt = get_system_prompt()
        user_prompt = USER_PROMPT_TEMPLATE.format(news_content=news_content) + "\n\nPrefer 12-14 strong stories if available."

    return await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=2200,
        timeout=45.0,
    )


def create_fallback_digest(news_items: List[Dict[str, Any]]) -> str:
    """Create a simple digest without AI if API fails."""
    lines = ["📰 *Tech News*\\n"]
    
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
        return await chat_completion(
            messages=[
                {"role": "system", "content": "Summarize the following in one concise sentence."},
                {"role": "user", "content": text[:1000]}  # Limit input
            ],
            temperature=0.5,
            max_tokens=100,
            timeout=20.0,
        )
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
    
    print("Testing summarizer (requires AI provider credentials)...")
    
    async def test():
        try:
            digest = await summarize_news(sample_news)
            print(digest)
        except ValueError as e:
            print(f"Skipping test: {e}")
            print("\\nFallback digest:")
            print(create_fallback_digest(sample_news))
            
    asyncio.run(test())

