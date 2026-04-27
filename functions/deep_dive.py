"""
Deep Dive Async Agent
When a user saves an article, this module queues background research
and sends a follow-up message with related context, GitHub info, HN discussion, and counter-arguments.
"""

import os
import re
import time
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

import httpx

try:
    from google.cloud import firestore
except Exception:
    firestore = None

from .user_storage import get_firestore_client
from .security_utils import is_safe_url, sanitize_markdown_url
from .summarizer import chat_completion


DEEP_DIVE_DELAY_MINUTES = 3  # Minimum delay before processing


def _get_db():
    return get_firestore_client()


def queue_deep_dive(user_id: int, article: Dict[str, Any]) -> bool:
    """
    Queue an article for deep-dive background research.
    Called immediately when a user saves an article.
    """
    db = _get_db()
    if not db:
        return False

    try:
        doc_ref = db.collection('deep_dive_queue').document()
        doc_ref.set({
            'user_id': user_id,
            'article_title': article.get('title', 'Untitled'),
            'article_url': article.get('url', ''),
            'article_source': article.get('source', ''),
            'status': 'pending',
            'created_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
            'process_after': datetime.now(timezone.utc) + timedelta(minutes=DEEP_DIVE_DELAY_MINUTES),
        })
        return True
    except Exception as e:
        print(f"Error queueing deep dive: {e}")
        return False


def get_pending_deep_dives(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch pending deep dives that are ready to process."""
    db = _get_db()
    if not db:
        return []

    try:
        now = datetime.now(timezone.utc)
        docs = db.collection('deep_dive_queue')\
            .where('status', '==', 'pending')\
            .where('process_after', '<=', now)\
            .limit(limit)\
            .stream()
        return [{**doc.to_dict(), 'id': doc.id} for doc in docs]
    except Exception as e:
        print(f"Error fetching deep dive queue: {e}")
        return []


def mark_deep_dive_status(doc_id: str, status: str, result: Dict[str, Any] = None):
    """Update deep dive status and store result."""
    db = _get_db()
    if not db:
        return
    try:
        update = {
            'status': status,
            'updated_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
        }
        if result:
            update['result'] = result
        db.collection('deep_dive_queue').document(doc_id).update(update)
    except Exception as e:
        print(f"Error updating deep dive status: {e}")


async def find_hn_discussion(url: str) -> Optional[Dict[str, Any]]:
    """Search Hacker News for discussions about a URL via Algolia API."""
    if not url or not url.startswith('http'):
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            api_url = f"https://hn.algolia.com/api/v1/search?query={url}&tags=story&hitsPerPage=3"
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()
            hits = data.get('hits', [])
            if hits:
                best = hits[0]
                return {
                    'title': best.get('title', ''),
                    'url': f"https://news.ycombinator.com/item?id={best.get('objectID')}",
                    'points': best.get('points', 0),
                    'comments': best.get('num_comments', 0),
                }
    except Exception as e:
        print(f"HN search error: {e}")
    return None


def extract_github_repo(url: str) -> Optional[str]:
    """Extract GitHub repo path from URL if applicable."""
    if not url:
        return None
    match = re.search(r'github\.com/([^/]+/[^/]+)', url)
    if match:
        return match.group(1)
    return None


async def get_github_repo_info(repo: str) -> Optional[Dict[str, Any]]:
    """Fetch GitHub repo stars and description."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            token = os.environ.get('GITHUB_TOKEN')
            if token:
                headers['Authorization'] = f'token {token}'
            response = await client.get(f"https://api.github.com/repos/{repo}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    'stars': data.get('stargazers_count', 0),
                    'description': data.get('description', '')[:120],
                    'language': data.get('language', ''),
                    'updated_at': data.get('updated_at', '')[:10],
                }
    except Exception as e:
        print(f"GitHub API error: {e}")
    return None


async def generate_deep_dive_analysis(title: str, url: str, source: str, lang: str = 'en') -> Dict[str, Any]:
    """
    Perform full deep-dive research on an article.
    Returns a dict with all findings.
    """
    result = {
        'hn_discussion': None,
        'github_info': None,
        'ai_perspective': None,
    }

    # HN discussion
    hn = await find_hn_discussion(url)
    if hn:
        result['hn_discussion'] = hn

    # GitHub info
    repo = extract_github_repo(url)
    if repo:
        gh = await get_github_repo_info(repo)
        if gh:
            result['github_info'] = {**gh, 'repo': repo}

    # AI perspective / counter-arguments via LLM
    try:
        if lang == 'ru':
            system_prompt = (
                "Ты — технический аналитик. На основе заголовка и источника статьи "
                "дай краткий контекст: 1) почему это важно, 2) возможные подводные камни или контраргументы, "
                "3) на что обратить внимание. Максимум 3 предложения. Будь объективным."
            )
            user_prompt = f"Заголовок: {title}\nИсточник: {source}\nURL: {url}"
        else:
            system_prompt = (
                "You are a technical analyst. Based on the article title and source, "
                "provide brief context: 1) why it matters, 2) potential caveats or counter-arguments, "
                "3) what to watch for. Maximum 3 sentences. Be objective."
            )
            user_prompt = f"Title: {title}\nSource: {source}\nURL: {url}"

        perspective = await chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=200,
            timeout=20.0,
        )
        result['ai_perspective'] = perspective.strip()
    except Exception as e:
        print(f"AI perspective generation failed: {e}")

    return result


def format_deep_dive_result(result: Dict[str, Any], article_title: str, article_url: str, lang: str = 'en') -> str:
    """Format deep dive findings into a Telegram message."""
    safe_url = sanitize_markdown_url(article_url)

    if lang == 'ru':
        lines = [f"🔍 *Глубокое погружение*", f""]
        if safe_url.startswith('http'):
            lines.append(f"Статья: [{article_title[:60]}]({safe_url})")
        else:
            lines.append(f"Статья: {article_title[:60]}")
    else:
        lines = [f"🔍 *Deep Dive*", f""]
        if safe_url.startswith('http'):
            lines.append(f"Article: [{article_title[:60]}]({safe_url})")
        else:
            lines.append(f"Article: {article_title[:60]}")

    # GitHub info
    gh = result.get('github_info')
    if gh:
        stars = gh.get('stars', 0)
        repo = gh.get('repo', '')
        desc = gh.get('description', '')
        if lang == 'ru':
            lines.append(f"\n⭐ *GitHub:* `{repo}` — {stars} stars")
        else:
            lines.append(f"\n⭐ *GitHub:* `{repo}` — {stars} stars")
        if desc:
            lines.append(f"_{desc}_")

    # HN discussion
    hn = result.get('hn_discussion')
    if hn:
        hn_url = sanitize_markdown_url(hn.get('url', ''))
        points = hn.get('points', 0)
        comments = hn.get('comments', 0)
        hn_title = hn.get('title', '')[:50]
        if lang == 'ru':
            lines.append(f"\n💬 *Обсуждение на HN:* [{hn_title}]({hn_url}) — {points}↑ {comments}💬")
        else:
            lines.append(f"\n💬 *HN Discussion:* [{hn_title}]({hn_url}) — {points}↑ {comments}💬")

    # AI perspective
    perspective = result.get('ai_perspective')
    if perspective:
        if lang == 'ru':
            lines.append(f"\n🧠 *Аналитика:*")
        else:
            lines.append(f"\n🧠 *Analyst Take:*")
        lines.append(perspective)

    return "\n".join(lines)


async def process_deep_dive_queue_batch(batch_size: int = 5) -> Dict[str, Any]:
    """
    Process a batch of pending deep dives.
    Called by the scheduled Cloud Function.
    Returns summary of processed items.
    """
    pending = get_pending_deep_dives(limit=batch_size)
    if not pending:
        return {'processed': 0}

    from telegram import Bot
    from .telegram_bot import get_bot_token

    bot = Bot(token=get_bot_token())
    processed = 0
    errors = []

    for item in pending:
        doc_id = item.get('id')
        user_id = item.get('user_id')
        title = item.get('article_title', 'Untitled')
        url = item.get('article_url', '')
        source = item.get('article_source', '')

        try:
            # Mark as processing to avoid duplicate work
            mark_deep_dive_status(doc_id, 'processing')

            # Get user language
            from .user_storage import get_user_language
            lang = get_user_language(user_id)

            # Perform research
            result = await generate_deep_dive_analysis(title, url, source, lang)

            # Format and send
            message = format_deep_dive_result(result, title, url, lang)
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )

            mark_deep_dive_status(doc_id, 'completed', result)
            processed += 1

        except Exception as e:
            print(f"Deep dive processing error for {doc_id}: {e}")
            mark_deep_dive_status(doc_id, 'failed')
            errors.append(str(e))

    return {'processed': processed, 'errors': errors[:5]}


def cleanup_old_deep_dives(days: int = 7) -> int:
    """Remove completed/failed deep dive records older than specified days."""
    db = _get_db()
    if not db:
        return 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        docs = db.collection('deep_dive_queue')\
            .where('updated_at', '<', cutoff)\
            .stream()
        batch = db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
        if count % 400 != 0:
            batch.commit()
        return count
    except Exception as e:
        print(f"Error cleaning deep dives: {e}")
        return 0
