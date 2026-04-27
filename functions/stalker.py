"""
Stalker Module — Competitor / Repo Tracking
Users can stalk companies (to get news only from them) or GitHub repos (for releases).
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

import httpx

try:
    from google.cloud import firestore
except Exception:
    firestore = None

from .user_storage import get_firestore_client
from .security_utils import sanitize_markdown_url


def _get_db():
    return get_firestore_client()


# ==================== USER-FACING CRUD ====================

def add_stalk_target(user_id: int, target_type: str, name: str) -> bool:
    """
    Add a stalk target for a user.
    target_type: 'company' or 'repo'
    name: company name or repo path (owner/repo)
    """
    db = _get_db()
    if not db:
        return False

    # Normalize repo format
    if target_type == 'repo':
        name = name.strip().lower()
        if not re.match(r'^[\w\-]+/[\w\-.]+$', name):
            return False
    else:
        name = name.strip().lower()

    try:
        stalk_id = f"{target_type}_{name.replace('/', '_')}"
        db.collection('users').document(str(user_id)).collection('stalks').document(stalk_id).set({
            'target_type': target_type,
            'name': name,
            'added_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
            'last_alert_at': None,
            'last_check_data': {},
        }, merge=True)
        return True
    except Exception as e:
        print(f"Error adding stalk target: {e}")
        return False


def remove_stalk_target(user_id: int, name: str) -> bool:
    """Remove a stalk target by name."""
    db = _get_db()
    if not db:
        return False

    name = name.strip().lower()
    try:
        # Try to find and delete by name field
        docs = db.collection('users').document(str(user_id)).collection('stalks').stream()
        deleted = False
        for doc in docs:
            data = doc.to_dict() or {}
            if data.get('name', '').lower() == name:
                doc.reference.delete()
                deleted = True
        return deleted
    except Exception as e:
        print(f"Error removing stalk target: {e}")
        return False


def list_stalk_targets(user_id: int) -> List[Dict[str, Any]]:
    """List all stalk targets for a user."""
    db = _get_db()
    if not db:
        return []

    try:
        docs = db.collection('users').document(str(user_id)).collection('stalks').stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error listing stalk targets: {e}")
        return []


# ==================== CHECKING LOGIC ====================

async def check_repo_release(repo: str) -> Optional[Dict[str, Any]]:
    """Check latest GitHub release for a repo."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            token = os.environ.get('GITHUB_TOKEN')
            if token:
                headers['Authorization'] = f'token {token}'

            # Get latest release
            resp = await client.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'tag': data.get('tag_name', ''),
                    'name': data.get('name', '')[:80],
                    'url': data.get('html_url', ''),
                    'published_at': data.get('published_at', ''),
                    'body': data.get('body', '')[:200],
                }

            # If no releases, check recent commits
            resp = await client.get(f"https://api.github.com/repos/{repo}/commits?per_page=1", headers=headers)
            if resp.status_code == 200:
                commits = resp.json()
                if commits:
                    c = commits[0]
                    return {
                        'tag': 'latest commit',
                        'name': c.get('commit', {}).get('message', '')[:80],
                        'url': c.get('html_url', ''),
                        'published_at': c.get('commit', {}).get('committer', {}).get('date', ''),
                        'body': '',
                    }
    except Exception as e:
        print(f"GitHub check error for {repo}: {e}")
    return None


def filter_company_news(company: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter articles to only those directly from the specified company/source."""
    company_lower = company.lower()
    matches = []
    for article in articles:
        source = (article.get('source') or '').lower()
        title = (article.get('title') or '').lower()
        url = (article.get('url') or '').lower()

        # Direct source match
        if company_lower in source:
            matches.append(article)
            continue

        # URL domain match (e.g., anthropic.com)
        if company_lower.replace(' ', '') in url.replace('-', '').replace('_', ''):
            matches.append(article)
            continue

        # Title starts with company name (often indicates original announcement)
        if title.startswith(company_lower):
            matches.append(article)

    return matches


# ==================== ALERTING ====================

async def process_stalker_alerts(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check all user stalk targets against fetched articles.
    Send alerts for new company news or repo releases.
    Called by a scheduled function.
    """
    db = _get_db()
    if not db:
        return {'sent': 0}

    from telegram import Bot
    from .telegram_bot import get_bot_token
    from .user_storage import get_user_language

    bot = Bot(token=get_bot_token())
    sent = 0
    errors = []

    try:
        # Get all users with stalks
        users = db.collection('users').stream()
        for user_doc in users:
            user_id = int(user_doc.id)
            stalks = list_stalk_targets(user_id)
            if not stalks:
                continue

            lang = get_user_language(user_id)

            for stalk in stalks:
                target_type = stalk.get('target_type')
                name = stalk.get('name', '')
                last_alert = stalk.get('last_alert_at')
                last_data = stalk.get('last_check_data', {})

                try:
                    if target_type == 'company':
                        news = filter_company_news(name, articles)
                        if not news:
                            continue

                        # Deduplicate against last alerted article
                        new_articles = []
                        for article in news:
                            url = article.get('url', '')
                            if url and url != last_data.get('last_url'):
                                new_articles.append(article)

                        if not new_articles:
                            continue

                        # Send alert
                        article = new_articles[0]
                        title = article.get('title', 'Untitled')[:70]
                        url = sanitize_markdown_url(article.get('url', ''))
                        source = article.get('source', '')

                        if lang == 'ru':
                            msg = f"📡 *Новость от {name.title()}*\n\n[{title}]({url})\n_{source}_"
                        else:
                            msg = f"📡 *News from {name.title()}*\n\n[{title}]({url})\n_{source}_"

                        await bot.send_message(
                            chat_id=user_id,
                            text=msg,
                            parse_mode='Markdown',
                            disable_web_page_preview=True,
                        )

                        # Update last alert
                        stalk_ref = db.collection('users').document(str(user_id)).collection('stalks').document(f"company_{name}")
                        stalk_ref.update({
                            'last_alert_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
                            'last_check_data': {'last_url': article.get('url', '')},
                        })
                        sent += 1

                    elif target_type == 'repo':
                        release = await check_repo_release(name)
                        if not release:
                            continue

                        tag = release.get('tag', '')
                        last_tag = last_data.get('last_tag', '')
                        if tag == last_tag:
                            continue

                        rel_url = sanitize_markdown_url(release.get('url', ''))
                        rel_name = release.get('name', tag)
                        published = release.get('published_at', '')[:10]

                        if lang == 'ru':
                            msg = f"🚀 *Новый релиз* `{name}`\n\n*{rel_name}*\n_{published}_"
                        else:
                            msg = f"🚀 *New Release* `{name}`\n\n*{rel_name}*\n_{published}_"

                        if rel_url.startswith('http'):
                            if lang == 'ru':
                                msg += f"\n\n[Смотреть релиз]({rel_url})"
                            else:
                                msg += f"\n\n[View release]({rel_url})"

                        await bot.send_message(
                            chat_id=user_id,
                            text=msg,
                            parse_mode='Markdown',
                            disable_web_page_preview=True,
                        )

                        stalk_ref = db.collection('users').document(str(user_id)).collection('stalks').document(f"repo_{name.replace('/', '_')}")
                        stalk_ref.update({
                            'last_alert_at': firestore.SERVER_TIMESTAMP if firestore else datetime.now(timezone.utc),
                            'last_check_data': {'last_tag': tag},
                        })
                        sent += 1

                except Exception as e:
                    print(f"Stalker alert error for user {user_id}, target {name}: {e}")
                    errors.append(str(e))

    except Exception as e:
        print(f"Stalker processing error: {e}")
        errors.append(str(e))

    return {'sent': sent, 'errors': errors[:5]}
