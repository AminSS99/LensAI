"""
DeepSeek Summarization Module
Uses DeepSeek API to summarize and format tech news digest.
"""

import os
from typing import List, Dict, Any
from openai import OpenAI


# DeepSeek uses OpenAI-compatible API
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_client() -> OpenAI:
    """Get DeepSeek API client."""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")
    
    return OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL
    )


def format_news_for_prompt(news_items: List[Dict[str, Any]]) -> str:
    """Format news items for the summarization prompt."""
    formatted = []
    
    for i, item in enumerate(news_items, 1):
        source = item.get('source', 'Unknown')
        title = item.get('title', 'No title')
        url = item.get('url', '')
        summary = item.get('summary', '')
        score = item.get('score', '')
        
        entry = f"{i}. [{source}] {title}"
        if score:
            entry += f" (Score: {score})"
        if summary:
            entry += f"\n   Summary: {summary}"
        if url:
            entry += f"\n   URL: {url}"
        
        formatted.append(entry)
    
    return "\n\n".join(formatted)


SYSTEM_PROMPT = """You are a tech news curator and summarizer. Your job is to:
1. Analyze the provided tech news items
2. Identify the most important and impactful stories
3. Create a concise, well-organized digest

Format your response as a Telegram message using these guidelines:
- Use emojis to make it visually appealing
- Group news by category (🔥 Top Stories, 🤖 AI News, 🛠️ New Tools, 💼 Industry News)
- Keep each summary to 1-2 sentences
- Include the source and make URLs clickable
- Be conversational and engaging
- Maximum 10 items in total, prioritize quality over quantity
- End with a brief one-liner insight or observation

Target length: 500-800 words"""


USER_PROMPT_TEMPLATE = """Here are today's tech news items. Please create a curated digest:

{news_content}

Create an engaging Telegram-friendly digest with the most important stories."""


def summarize_news(news_items: List[Dict[str, Any]], max_items: int = 30) -> str:
    """
    Summarize a list of news items into a formatted digest.
    
    Args:
        news_items: List of news items from scrapers
        max_items: Maximum items to send to API (to control token usage)
        
    Returns:
        Formatted markdown digest for Telegram
    """
    if not news_items:
        return "📭 No tech news found today. Check back later!"
    
    # Limit items to control API costs
    items_to_summarize = news_items[:max_items]
    
    # Format news for the prompt
    news_content = format_news_for_prompt(items_to_summarize)
    
    try:
        client = get_client()
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(news_content=news_content)}
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
    lines = ["📰 *Tech News Digest*\n"]
    
    for item in news_items:
        source = item.get('source', 'News')
        title = item.get('title', '')
        url = item.get('url', '')
        
        lines.append(f"• [{source}] {title}")
        if url:
            lines.append(f"  {url}")
        lines.append("")
    
    lines.append("\n_Generated without AI summarization (API unavailable)_")
    return "\n".join(lines)


def quick_summary(text: str, max_length: int = 100) -> str:
    """
    Generate a quick one-liner summary of text.
    Useful for individual article summaries.
    """
    try:
        client = get_client()
        
        response = client.chat.completions.create(
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
    try:
        digest = summarize_news(sample_news)
        print(digest)
    except ValueError as e:
        print(f"Skipping test: {e}")
        print("\nFallback digest:")
        print(create_fallback_digest(sample_news))
