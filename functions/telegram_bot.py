"""
Telegram Bot Module
Handles all Telegram bot interactions and commands.
"""

import os
import re
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Baku timezone (UTC+4)
BAKU_TZ = timezone(timedelta(hours=4))


def get_bot_token() -> str:
    """Get Telegram bot token from environment."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    return token


def get_admin_ids() -> set:
    """Parse ADMIN_TELEGRAM_IDS env var into a set of ints."""
    raw = os.environ.get("ADMIN_TELEGRAM_IDS", "")
    values = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.add(int(part))
        except ValueError:
            continue
    return values


def get_digest_reply_markup(digest_id: str, user_lang: str) -> InlineKeyboardMarkup:
    """Build shared inline keyboard for digest actions."""
    if user_lang == "ru":
        refresh_label = "Обновить"
        save_label = "Сохранить"
        why_label = "Почему это важно"
    else:
        refresh_label = "Refresh"
        save_label = "Save Digest"
        why_label = "Why It Matters"

    keyboard = [
        [
            InlineKeyboardButton("рџ‘Ќ", callback_data=f"rate_up_{digest_id}"),
            InlineKeyboardButton("рџ‘Ћ", callback_data=f"rate_down_{digest_id}"),
            InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
        ],
        [
            InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
            InlineKeyboardButton(why_label, callback_data=f"why_digest_{digest_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============ KEYBOARD MENUS ============

def get_main_keyboard(lang: str = 'en'):
    """Get the main persistent keyboard with quick action buttons."""
    from telegram import ReplyKeyboardRemove
    
    # Return ReplyKeyboardRemove to hide the big keyboard buttons
    # Users will now use the в‰Ў Menu button (bottom left) for all commands
    return ReplyKeyboardRemove()


# ============ COMMAND HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message."""
    from .user_storage import get_user_language
    from .translations import t
    
    user = update.effective_user
    telegram_id = user.id
    username = user.username or user.first_name
    user_lang = get_user_language(telegram_id)
    
    # Try to register user in database (optional - may not work locally)
    try:
        from .database import create_or_update_user
        create_or_update_user(telegram_id, username)
    except Exception as e:
        print(f"Database not available (running locally?): {e}")
    
    # Escape username for Markdown
    from .security_utils import escape_markdown_v1
    safe_username = escape_markdown_v1(username)
    
    welcome_message = t('welcome', user_lang, username=safe_username)
    await update.message.reply_text(
        welcome_message, 
        parse_mode='Markdown'
        # No reply_markup - using native bot commands instead
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    await update.message.reply_text(t('help_text', user_lang), parse_mode='Markdown')


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - fetch and send digest now."""
    from .cache import get_cached_digest, set_cached_digest, get_digest_timestamp, is_digest_cached, build_digest_cache_key
    from .rate_limiter import check_rate_limit
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)

    # Resolve sources first so cache is language+source scoped.
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github']
    try:
        from .database import get_user
        user = get_user(telegram_id)
        if user and user.get('sources'):
            sources = user.get('sources')
    except Exception:
        pass

    cache_key = build_digest_cache_key(language=user_lang, sources=sources, scope='news')
    
    # Check cache first (no rate limit for cached responses)
    if is_digest_cached(cache_key=cache_key):
        cached_digest = get_cached_digest(cache_key=cache_key)
        timestamp = get_digest_timestamp(cache_key=cache_key)
        
        
        # Format timestamp to Baku time
        timestamp_str = 'recently'
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_baku = dt.astimezone(BAKU_TZ)
                timestamp_str = dt_baku.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                timestamp_str = timestamp[:16]
        
        header = t('cached_news', user_lang, timestamp=timestamp_str)
        
        # Generate digest ID for buttons
        import hashlib
        digest_id = hashlib.md5(cached_digest[:100].encode()).hexdigest()[:8]
        reply_markup = get_digest_reply_markup(digest_id, user_lang)
        
        try:
            await update.message.reply_text(
                header + cached_digest[:3900],
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception:
            # Fallback without markdown if parsing fails
            await update.message.reply_text(
                header + cached_digest[:3900],
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        return
    
    # Check if already generating using distributed lock
    from .distributed_lock import is_locked
    if is_locked('news_generation', telegram_id):
        wait_text = "вЏі Р”Р°Р№РґР¶РµСЃС‚ СѓР¶Рµ РіРµРЅРµСЂРёСЂСѓРµС‚СЃСЏ, РїРѕР¶Р°Р»СѓР№СЃС‚Р° РїРѕРґРѕР¶РґРёС‚Рµ..." if user_lang == 'ru' else "вЏі Digest is already being generated, please wait..."
        await update.message.reply_text(wait_text)
        return
    
    # Rate limit fresh requests
    allowed, message = check_rate_limit(telegram_id, 'news')
    if not allowed:
        await update.message.reply_text(t('rate_limited', user_lang, seconds=message.split()[-2] if 'seconds' in message else '60'))
        return
    
    # Acquire distributed lock
    from .distributed_lock import DistributedLock
    lock = DistributedLock('news_generation', telegram_id, ttl_seconds=300)
    
    if not lock.acquire():
        # Lock already held
        wait_text = "вЏі Р”Р°Р№РґР¶РµСЃС‚ СѓР¶Рµ РіРµРЅРµСЂРёСЂСѓРµС‚СЃСЏ, РїРѕР¶Р°Р»СѓР№СЃС‚Р° РїРѕРґРѕР¶РґРёС‚Рµ..." if user_lang == 'ru' else "вЏі Digest is already being generated, please wait..."
        await update.message.reply_text(wait_text)
        return
    
    # Send "typing" indicator after acquiring lock
    await update.message.reply_text(t('gathering_news', user_lang), parse_mode='Markdown')
    
    try:
        from .scrapers.hackernews import fetch_hackernews
        from .scrapers.techcrunch import fetch_techcrunch
        from .scrapers.ai_blogs import fetch_ai_blogs
        from .scrapers.theverge import fetch_theverge
        from .scrapers.github_trending import fetch_github_trending
        from .summarizer import summarize_news
        
        # Source list already resolved above (used in cache key as well).
        
        # Fetch news concurrently
        tasks = []
        
        if 'hackernews' in sources:
            tasks.append(fetch_hackernews(15)) # Fetch more for variety
        if 'techcrunch' in sources:
            tasks.append(asyncio.to_thread(fetch_techcrunch, 10))
        if 'ai_blogs' in sources:
            tasks.append(fetch_ai_blogs(5))
        if 'theverge' in sources:
            tasks.append(asyncio.to_thread(fetch_theverge, 8))
        if 'github' in sources:
            tasks.append(asyncio.to_thread(fetch_github_trending, 8))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_news = []
        for res in results:
            if isinstance(res, list):
                all_news.extend(res)
            elif isinstance(res, Exception):
                print(f"Error fetching news: {res}")
                
        if not all_news:
            await update.message.reply_text(t('no_news', user_lang))
            return
            
        # Personalized ranking based on previous feedback.
        from .personalization import rank_articles_for_user
        ranked_news = rank_articles_for_user(telegram_id, all_news)
        items_to_summarize = ranked_news[:10]
        
        digest = await summarize_news(items_to_summarize, language=user_lang)
        
        # Initialize refresh session
        try:
            from .user_storage import update_refresh_session, get_article_hash
            seen_hashes = [get_article_hash(item) for item in items_to_summarize]
            update_refresh_session(telegram_id, {
                'attempts': 0,
                'seen_hashes': seen_hashes
            })
        except Exception as e:
            print(f"Error init session: {e}")
        
        # Cache digest variant for 15 minutes.
        set_cached_digest(digest, ttl_minutes=15, cache_key=cache_key)
        
        # Generate unique digest ID for rating tracking
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        
        # Store full digest + metadata for callback actions and personalization.
        try:
            from .user_storage import save_temp_digest
            from .personalization import record_digest_context
            save_temp_digest(digest_id, telegram_id, digest, articles_meta=items_to_summarize, ttl_hours=24)
            record_digest_context(digest_id, telegram_id, items_to_summarize)
        except Exception as e:
            print(f"Error storing digest: {e}")
        
        # Try to save digest to history (optional)
        try:
            from .database import save_digest
            save_digest(telegram_id, digest)
        except Exception:
            pass
        
        # Send digest (split if too long for Telegram)
        reply_markup = get_digest_reply_markup(digest_id, user_lang)
        
        async def send_chunk(chunk, is_last=False):
            try:
                if is_last:
                    # Add action buttons to the last chunk.
                    await update.message.reply_text(
                        chunk, 
                        parse_mode='Markdown', 
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(chunk, parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                # Fallback: send without markdown parsing
                if is_last:
                    await update.message.reply_text(chunk, disable_web_page_preview=True, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(chunk, disable_web_page_preview=True)
        
        # Smart message splitting to avoid breaking UTF-8, URLs, or markdown
        from .message_utils import split_message
        chunks = split_message(digest)
        for i, chunk in enumerate(chunks):
            await send_chunk(chunk, is_last=(i == len(chunks) - 1))
            
    except Exception as e:
        await update.message.reply_text(t('error_fetching', user_lang, error=str(e)[:100]))
    finally:
        lock.release()


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /schedule command - show time picker buttons."""
    from .user_storage import get_user_language
    from .translations import t
    from .database import get_user
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Get current schedule time
    current_time = None
    try:
        user = get_user(telegram_id)
        if user:
            current_time = user.get('schedule_time')
    except Exception:
        pass
    
    # Available times (top of each hour from 09:00 to 22:00)
    times = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', 
             '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00']
    
    # Create button grid (2 columns)
    keyboard = []
    for i in range(0, len(times), 2):
        row = []
        for j in range(2):
            if i + j < len(times):
                time = times[i + j]
                check = "вњ“ " if time == current_time else ""
                row.append(InlineKeyboardButton(f"{check}{time}", callback_data=f"schedule_{time}"))
        keyboard.append(row)
    
    # Add disable option
    disable_text = "вќЊ РћС‚РєР»СЋС‡РёС‚СЊ" if user_lang == 'ru' else "вќЊ Disable"
    keyboard.append([InlineKeyboardButton(disable_text, callback_data="schedule_disable")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    header = "вЏ° *Р’С‹Р±РµСЂРёС‚Рµ РІСЂРµРјСЏ РґР»СЏ РµР¶РµРґРЅРµРІРЅРѕРіРѕ РґР°Р№РґР¶РµСЃС‚Р°:*" if user_lang == 'ru' else "вЏ° *Choose time for daily digest:*"
    if current_time:
        current_text = f"\n\n_РўРµРєСѓС‰РµРµ РІСЂРµРјСЏ: {current_time}_" if user_lang == 'ru' else f"\n\n_Current time: {current_time}_"
        header += current_text
    
    await update.message.reply_text(
        header,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle schedule time selection callback."""
    from .user_storage import get_user_language
    from .database import create_or_update_user
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    data = query.data.replace('schedule_', '')
    
    if data == 'disable':
        # Disable scheduled digest
        try:
            create_or_update_user(telegram_id, schedule_time=None, is_active=False)
        except Exception:
            pass
        
        msg = "вњ… Р•Р¶РµРґРЅРµРІРЅС‹Р№ РґР°Р№РґР¶РµСЃС‚ РѕС‚РєР»СЋС‡РµРЅ." if user_lang == 'ru' else "вњ… Daily digest disabled."
        await query.edit_message_text(msg, parse_mode='Markdown')
        return
    
    # Set the selected time
    selected_time = data  # e.g. "18:00"
    
    try:
        create_or_update_user(telegram_id, schedule_time=selected_time, is_active=True)
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")
        return
    
    if user_lang == 'ru':
        msg = f"вњ… Р•Р¶РµРґРЅРµРІРЅС‹Р№ РґР°Р№РґР¶РµСЃС‚ Р·Р°РїР»Р°РЅРёСЂРѕРІР°РЅ РЅР° *{selected_time}*!\n\nР’С‹ Р±СѓРґРµС‚Рµ РїРѕР»СѓС‡Р°С‚СЊ РїРµСЂСЃРѕРЅР°Р»СЊРЅС‹Рµ РЅРѕРІРѕСЃС‚Рё С‚РµС…РЅРѕР»РѕРіРёР№ РІ СЌС‚Рѕ РІСЂРµРјСЏ РєР°Р¶РґС‹Р№ РґРµРЅСЊ."
    else:
        msg = f"вњ… Daily digest scheduled for *{selected_time}*!\n\nYou will receive personalized tech news at this time every day."
    
    await query.edit_message_text(msg, parse_mode='Markdown')


# Keep settime_command for backward compatibility with /settime command
async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settime command - redirect to schedule picker."""
    await schedule_command(update, context)


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sources command - show source management."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Try to get user preferences from database, use defaults if not available
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github']  # Default all enabled
    try:
        from .database import get_user, create_or_update_user
        user = get_user(telegram_id)
        if not user:
            user = create_or_update_user(telegram_id)
        sources = user.get('sources', sources)
    except Exception:
        pass  # Use defaults
    
    # Create inline keyboard for toggling sources
    keyboard = [
        [InlineKeyboardButton(
            f"{'вњ…' if 'hackernews' in sources else 'вќЊ'} Hacker News",
            callback_data='toggle_hackernews'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'techcrunch' in sources else 'вќЊ'} TechCrunch",
            callback_data='toggle_techcrunch'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'ai_blogs' in sources else 'вќЊ'} AI Blogs",
            callback_data='toggle_ai_blogs'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'theverge' in sources else 'вќЊ'} The Verge",
            callback_data='toggle_theverge'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'github' in sources else 'вќЊ'} GitHub Trending",
            callback_data='toggle_github'
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        t('sources_header', user_lang),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def toggle_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle source toggle button presses."""
    from .database import toggle_user_source
    from .user_storage import get_user_language
    from .translations import t
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    source = query.data.replace('toggle_', '')
    
    # Toggle the source
    new_sources = toggle_user_source(telegram_id, source)
    
    # Update keyboard
    keyboard = [
        [InlineKeyboardButton(
            f"{'вњ…' if 'hackernews' in new_sources else 'вќЊ'} Hacker News",
            callback_data='toggle_hackernews'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'techcrunch' in new_sources else 'вќЊ'} TechCrunch",
            callback_data='toggle_techcrunch'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'ai_blogs' in new_sources else 'вќЊ'} AI Blogs",
            callback_data='toggle_ai_blogs'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'theverge' in new_sources else 'вќЊ'} The Verge",
            callback_data='toggle_theverge'
        )],
        [InlineKeyboardButton(
            f"{'вњ…' if 'github' in new_sources else 'вќЊ'} GitHub Trending",
            callback_data='toggle_github'
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        t('sources_header', user_lang),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current settings."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Try to get user from database
    user = None
    try:
        from .database import get_user
        user = get_user(telegram_id)
    except Exception:
        pass  # Database not available
    
    if not user:
        # Show default settings for local mode
        await update.message.reply_text(t('status_local', user_lang), parse_mode='Markdown')
        return
    
    sources = user.get('sources', [])
    source_names = {
        'hackernews': 'Hacker News',
        'techcrunch': 'TechCrunch',
        'ai_blogs': 'AI Blogs',
        'theverge': 'The Verge',
        'github': 'GitHub Trending',
    }
    
    sources_text = '\n'.join([f"  вЂў {source_names.get(s, s)}" for s in sources])
    if not sources:
        sources_text = '  No sources selected' if user_lang == 'en' else '  РќРµС‚ РІС‹Р±СЂР°РЅРЅС‹С… РёСЃС‚РѕС‡РЅРёРєРѕРІ'

    quiet_hours = user.get('quiet_hours')
    if quiet_hours and quiet_hours.get('start') and quiet_hours.get('end'):
        quiet_text = f"{quiet_hours.get('start')} - {quiet_hours.get('end')}"
    else:
        quiet_text = "Off"
    
    status_message = t(
        'status_cloud',
        user_lang,
        schedule_time=user.get('schedule_time', 'Not set'),
        timezone=user.get('timezone', 'Asia/Baku'),
        sources=sources_text
    )
    status_message += f"\n\nQuiet hours: {quiet_text}"

    await update.message.reply_text(status_message, parse_mode='Markdown')


# ============ SAVED ARTICLES ============

async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /saved command - show saved articles with delete buttons."""
    from .user_storage import get_saved_articles, get_user_language
    from .translations import t
    import hashlib
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    articles = get_saved_articles(telegram_id, limit=10)
    
    if not articles:
        await update.message.reply_text(t('no_saved', user_lang), parse_mode='Markdown')
        return
    
    # Category emoji mapping
    cat_emoji = {
        'ai': 'рџ¤–', 'security': 'рџ”’', 'crypto': 'рџ’°', 'startups': 'рџљЂ',
        'hardware': 'рџ’»', 'software': 'рџ“±', 'tech': 'рџ”§'
    }
    
    message = t('saved_header', user_lang)
    keyboard = []
    
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        source = article.get('source', '')
        category = article.get('category', 'tech')
        saved_at = article.get('saved_at', '')
        
        # Get category emoji
        emoji = cat_emoji.get(category, 'рџ”§')
        
        # Format date
        date_str = saved_at[:10] if saved_at else ''
        
        # Escape title for Markdown security
        from .security_utils import escape_markdown_v1
        safe_title = escape_markdown_v1(title)
        
        # Build message line
        if url.startswith('http'):
            message += f"{i}. {emoji} [{safe_title}]({url})"
        else:
            message += f"{i}. {emoji} {safe_title}"
        
        if date_str:
            message += f" `{date_str}`"
        message += "\n"
        
        # Create delete button - use URL hash for unique ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        delete_label = "рџ—‘пёЏ" if user_lang == 'en' else "рџ—‘пёЏ"
        keyboard.append([InlineKeyboardButton(f"{delete_label} {i}. {title[:25]}...", callback_data=f"del_{url_hash}")])
    
    message += t('saved_footer', user_lang)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try:
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
    except Exception:
        await update.message.reply_text(message, disable_web_page_preview=True, reply_markup=reply_markup)


async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /save command - save an article."""
    from .user_storage import save_article, get_user_language, categorize_article
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    if not context.args:
        await update.message.reply_text(
            t('save_help', user_lang),
            parse_mode='Markdown'
        )
        return
    
    url = context.args[0]
    title = ' '.join(context.args[1:]) if len(context.args) > 1 else url[:50]
    category = categorize_article(title, url)
    
    if save_article(telegram_id, title, url, category=category):
        cat_label = t(f'cat_{category}', user_lang)
        await update.message.reply_text(t('article_saved_single', user_lang, category=cat_label))
    else:
        await update.message.reply_text(t('article_exists', user_lang))


async def clear_saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_saved command."""
    from .user_storage import clear_saved_articles, get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    clear_saved_articles(telegram_id)
    await update.message.reply_text(t('cleared_saved', user_lang))


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /filter command - filter saved articles by category."""
    from .user_storage import get_saved_articles, get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    valid_categories = ['ai', 'security', 'crypto', 'startups', 'hardware', 'software', 'tech']
    
    if not context.args:
        await update.message.reply_text(t('filter_prompt', user_lang), parse_mode='Markdown')
        return
        
    category = context.args[0].lower()
    
    # Validation: Check max length
    if len(category) > 20:
        await update.message.reply_text("вќЊ Category name too long.")
        return
    if category not in valid_categories:
        await update.message.reply_text(t('filter_prompt', user_lang), parse_mode='Markdown')
        return
    
    articles = get_saved_articles(telegram_id, limit=20, category=category)
    
    if not articles:
        cat_label = t(f'cat_{category}', user_lang)
        await update.message.reply_text(t('filter_empty', user_lang, category=cat_label), parse_mode='Markdown')
        return
    
    cat_label = t(f'cat_{category}', user_lang)
    message = t('filter_results', user_lang, category=cat_label, count=len(articles))
    
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        if url.startswith('http'):
            message += f"{i}. [{title}]({url})\n"
        else:
            message += f"{i}. {title}\n"
    
    try:
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(message, disable_web_page_preview=True)


async def recap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recap command - show weekly summary of saved articles."""
    from .user_storage import get_saved_articles, get_user_language
    from .translations import t
    from datetime import datetime, timedelta
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Get all saved articles
    articles = get_saved_articles(telegram_id, limit=50)
    
    # Filter to last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    weekly_articles = []
    
    for article in articles:
        saved_at = article.get('saved_at', '')
        if saved_at:
            try:
                saved_date = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
                if saved_date.replace(tzinfo=None) > week_ago:
                    weekly_articles.append(article)
            except Exception:
                pass
    
    if not weekly_articles:
        await update.message.reply_text(t('recap_empty', user_lang), parse_mode='Markdown')
        return
    
    # Category emoji mapping
    cat_emoji = {
        'ai': 'рџ¤–', 'security': 'рџ”’', 'crypto': 'рџ’°', 'startups': 'рџљЂ',
        'hardware': 'рџ’»', 'software': 'рџ“±', 'tech': 'рџ”§'
    }
    
    message = t('recap_header', user_lang)
    
    # Show top 5 recent articles
    for i, article in enumerate(weekly_articles[:5], 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        category = article.get('category', 'tech')
        emoji = cat_emoji.get(category, 'рџ”§')
        
        if url.startswith('http'):
            message += f"{i}. {emoji} [{title}]({url})\n"
        else:
            message += f"{i}. {emoji} {title}\n"
    
    message += f"\n_Total: {len(weekly_articles)} articles this week_"
    
    try:
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(message, disable_web_page_preview=True)


async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle share button - show bot link to share."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    await update.message.reply_text(t('share_bot', user_lang), parse_mode='Markdown')


async def trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trends command - show weekly topic trends."""
    from .user_storage import get_user_language
    from .trend_analysis import format_trends_message
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Show loading message
    loading_text = "рџ“Љ РђРЅР°Р»РёР·РёСЂСѓСЋ С‚СЂРµРЅРґС‹..." if user_lang == 'ru' else "рџ“Љ Analyzing trends..."
    await update.message.reply_text(loading_text)
    
    try:
        trends_message = format_trends_message(user_lang)
        await update.message.reply_text(
            trends_message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error in trends command: {e}")
        error_text = "вќЊ РћС€РёР±РєР° РїСЂРё Р°РЅР°Р»РёР·Рµ С‚СЂРµРЅРґРѕРІ." if user_lang == 'ru' else "вќЊ Error analyzing trends."
        await update.message.reply_text(error_text)


async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user timezone for scheduled digests."""
    telegram_id = update.effective_user.id
    from .database import set_user_timezone, get_user

    if not context.args:
        user = get_user(telegram_id) or {}
        current_tz = user.get("timezone", "Asia/Baku")
        await update.message.reply_text(
            f"Current timezone: {current_tz}\nUse: /timezone Region/City\nExample: /timezone Europe/Berlin"
        )
        return

    timezone_name = context.args[0].strip()
    try:
        ZoneInfo(timezone_name)
    except Exception:
        await update.message.reply_text("Invalid timezone. Use IANA format like Europe/Berlin or Asia/Baku.")
        return

    set_user_timezone(telegram_id, timezone_name)
    await update.message.reply_text(f"Timezone updated to {timezone_name}.")


async def quiet_hours_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set or clear quiet hours for scheduled digests."""
    telegram_id = update.effective_user.id
    from .database import set_user_quiet_hours, get_user

    if not context.args:
        user = get_user(telegram_id) or {}
        qh = user.get("quiet_hours")
        if qh and qh.get("start") and qh.get("end"):
            await update.message.reply_text(
                f"Current quiet hours: {qh.get('start')} - {qh.get('end')}\nUse: /quiet_hours HH:MM-HH:MM or /quiet_hours off"
            )
        else:
            await update.message.reply_text("Quiet hours are disabled.\nUse: /quiet_hours 23:00-07:00")
        return

    value = context.args[0].strip().lower()
    if value == "off":
        set_user_quiet_hours(telegram_id, None)
        await update.message.reply_text("Quiet hours disabled.")
        return

    match = re.match(r"^([0-2]\d:[0-5]\d)-([0-2]\d:[0-5]\d)$", value)
    if not match:
        await update.message.reply_text("Invalid format. Use /quiet_hours HH:MM-HH:MM (example: /quiet_hours 23:00-07:00)")
        return

    start, end = match.group(1), match.group(2)
    set_user_quiet_hours(telegram_id, {"start": start, "end": end})
    await update.message.reply_text(f"Quiet hours set: {start} - {end}")


async def trendalerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure weekly trend alerts."""
    from .user_storage import set_user_preference, get_user_preferences
    telegram_id = update.effective_user.id

    prefs = get_user_preferences(telegram_id) or {}
    current_enabled = bool(prefs.get("trend_alerts_enabled", False))
    current_threshold = int(prefs.get("trend_alert_threshold", 30))

    if not context.args:
        await update.message.reply_text(
            f"Trend alerts: {'ON' if current_enabled else 'OFF'}\n"
            f"Threshold: {current_threshold}%\n\n"
            "Usage:\n"
            "/trendalerts on 30\n"
            "/trendalerts off"
        )
        return

    mode = context.args[0].lower().strip()
    if mode == "off":
        set_user_preference(telegram_id, "trend_alerts_enabled", False)
        await update.message.reply_text("Weekly trend alerts disabled.")
        return

    if mode != "on":
        await update.message.reply_text("Usage: /trendalerts on [threshold] or /trendalerts off")
        return

    threshold = current_threshold
    if len(context.args) > 1:
        try:
            threshold = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Threshold must be an integer percent (e.g., 25).")
            return

    threshold = max(5, min(100, threshold))
    set_user_preference(telegram_id, "trend_alerts_enabled", True)
    set_user_preference(telegram_id, "trend_alert_threshold", threshold)
    await update.message.reply_text(f"Weekly trend alerts enabled at {threshold}% threshold.")


async def semantic_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search saved articles using lightweight semantic scoring."""
    from .user_storage import get_saved_articles
    from .semantic_search import semantic_search_articles
    from .security_utils import escape_markdown_v1

    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /semsearch your query")
        return

    query = " ".join(context.args).strip()
    saved = get_saved_articles(telegram_id, limit=200)
    if not saved:
        await update.message.reply_text("No saved articles found. Save some first with /save or Save Digest.")
        return

    results = semantic_search_articles(query, saved, limit=10)
    if not results:
        await update.message.reply_text("No relevant saved articles found.")
        return

    safe_query = escape_markdown_v1(query)
    lines = [f"*Semantic results for:* `{safe_query}`\n"]
    for idx, article in enumerate(results, 1):
        title = escape_markdown_v1((article.get("title") or "Untitled")[:70])
        url = article.get("url", "")
        score = article.get("_semantic_score", 0)
        if url.startswith("http"):
            lines.append(f"{idx}. [{title}]({url}) `score={score}`")
        else:
            lines.append(f"{idx}. {title} `score={score}`")

    message = "\n".join(lines)
    try:
        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(message, disable_web_page_preview=True)


async def admin_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show operational status to admins only."""
    telegram_id = update.effective_user.id
    if telegram_id not in get_admin_ids():
        await update.message.reply_text("Unauthorized.")
        return

    from time import perf_counter
    from .observability import build_health_snapshot
    from .scrapers.hackernews import fetch_hackernews
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs

    snapshot = build_health_snapshot()

    # Lightweight live probes.
    probe_results = []
    try:
        t0 = perf_counter()
        hn = await fetch_hackernews(2)
        probe_results.append(f"HN: {len(hn)} items in {perf_counter() - t0:.2f}s")
    except Exception as e:
        probe_results.append(f"HN: error {str(e)[:40]}")

    try:
        t0 = perf_counter()
        tc = await asyncio.to_thread(fetch_techcrunch, 2)
        probe_results.append(f"TechCrunch: {len(tc)} items in {perf_counter() - t0:.2f}s")
    except Exception as e:
        probe_results.append(f"TechCrunch: error {str(e)[:40]}")

    try:
        t0 = perf_counter()
        ai = await fetch_ai_blogs(1)
        probe_results.append(f"AI Blogs: {len(ai)} items in {perf_counter() - t0:.2f}s")
    except Exception as e:
        probe_results.append(f"AI Blogs: error {str(e)[:40]}")

    lines = [
        "*Admin Status*",
        f"timestamp_utc: `{snapshot.get('timestamp_utc', 'n/a')}`",
        f"users_total: `{snapshot.get('users_total', 0)}`",
        f"users_active: `{snapshot.get('users_active', 0)}`",
        f"cache_entries: `{snapshot.get('cache_entries', 0)}`",
        f"active_locks: `{snapshot.get('active_locks', 0)}`",
        f"latest_trend_date: `{snapshot.get('latest_trend_date', 'n/a')}`",
        "",
        "*Live Probes*",
        *[f"- {row}" for row in probe_results],
    ]
    message = "\n".join(lines)
    try:
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(message)


async def delete_article_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle delete article button press."""
    from .user_storage import get_user_language, get_saved_articles, delete_saved_article
    from .translations import t
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Get the URL hash from callback data
    data = query.data  # e.g., "del_abc12345"
    url_hash = data.replace('del_', '')
    
    # Find the article with matching hash
    import hashlib
    articles = get_saved_articles(telegram_id, limit=50)
    
    for article in articles:
        article_hash = hashlib.md5(article.get('url', '').encode()).hexdigest()[:8]
        if article_hash == url_hash:
            delete_saved_article(telegram_id, article.get('url', ''))
            await query.edit_message_text(
                t('article_deleted', user_lang) + f"\n\n_{article.get('title', '')[:40]}_",
                parse_mode='Markdown'
            )
            return
    
    await query.edit_message_text(t('article_deleted', user_lang), parse_mode='Markdown')


# ============ SEARCH ============

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command - search news by topic."""
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .user_storage import add_search_history, get_user_language
    from .rate_limiter import check_rate_limit
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Rate limit check
    allowed, message = check_rate_limit(telegram_id, 'search')
    if not allowed:
        await update.message.reply_text(t('rate_limited', user_lang, seconds='60'))
        return
    
    if not context.args:
        await update.message.reply_text(
            t('search_prompt', user_lang),
            parse_mode='Markdown'
        )
        return
    
    query = ' '.join(context.args).strip()
    query_lower = query.lower()
    
    # Validation
    if len(query) > 100:
        await update.message.reply_text("вќЊ Search query too long (max 100 chars).")
        return
        
    if len(query) < 2:
        await update.message.reply_text("вќЊ Search query too short.")
        return
    
    add_search_history(telegram_id, query)
    
    # Escape query for display
    from .security_utils import escape_markdown_v1
    safe_query = escape_markdown_v1(query)
    
    await update.message.reply_text(t('searching', user_lang, query=safe_query), parse_mode='Markdown')
    
    try:
        # Fetch news without blocking the event loop.
        hn_task = asyncio.to_thread(fetch_hackernews_sync, 30)
        tc_task = asyncio.to_thread(fetch_techcrunch, 20)
        hn_results, tc_results = await asyncio.gather(hn_task, tc_task, return_exceptions=True)

        all_news = []
        if isinstance(hn_results, list):
            all_news.extend(hn_results)
        if isinstance(tc_results, list):
            all_news.extend(tc_results)
        
        # Filter by query
        results = []
        for article in all_news:
            title = article.get('title', '').lower()
            if query_lower in title or any(word in title for word in query_lower.split()):
                results.append(article)
        
        if not results:
            await update.message.reply_text(
                t('no_results', user_lang, query=query),
                parse_mode='Markdown'
            )
            return
        
        # Format results
        message = t('search_results', user_lang, query=safe_query, count=len(results))
        for i, article in enumerate(results[:10], 1):
            title = article.get('title', '')[:60]
            # Escape title for security
            safe_title = escape_markdown_v1(title)
            
            url = article.get('url', '')
            source = article.get('source', '')
            # Escape source for security
            safe_source = escape_markdown_v1(source)
            
            message += f"{i}. [{safe_title}]({url}) _{safe_source}_\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await update.message.reply_text(t('error_fetching', user_lang, error=str(e)[:100]))


# ============ LANGUAGE ============

LANGUAGES = {
    'en': 'рџ‡¬рџ‡§ English',
    'ru': 'рџ‡·рџ‡є Р СѓСЃСЃРєРёР№'
}

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command - change language."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    current_lang = get_user_language(telegram_id)
    
    keyboard = []
    for code, name in LANGUAGES.items():
        check = "вњ“ " if code == current_lang else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"lang_{code}")])
    
    # Azerbaijani - coming soon
    keyboard.append([InlineKeyboardButton("рџ‡¦рџ‡ї AzЙ™rbaycan (TezliklЙ™)", callback_data="lang_coming_soon")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        t('select_language', current_lang),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback."""
    from .user_storage import set_user_language, get_user_language
    from .translations import t
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang_code = query.data.replace('lang_', '')
    
    # Handle coming soon
    if lang_code == 'coming_soon':
        current_lang = get_user_language(telegram_id)
        await query.edit_message_text(
            t('az_coming_soon', current_lang),
            parse_mode='Markdown'
        )
        return
    
    # Validate language code
    if lang_code not in LANGUAGES:
        return
    
    # Set the new language
    set_user_language(telegram_id, lang_code)
    
    # Rebuild the keyboard with updated checkmark
    keyboard = []
    for code, name in LANGUAGES.items():
        check = "вњ“ " if code == lang_code else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"lang_{code}")])
    
    # Azerbaijani - coming soon
    keyboard.append([InlineKeyboardButton("рџ‡¦рџ‡ї AzЙ™rbaycan (TezliklЙ™)", callback_data="lang_coming_soon")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update the message with the new keyboard showing the checkmark on selected language
    await query.edit_message_text(
        t('select_language', lang_code) + f"\n\nвњ… {LANGUAGES[lang_code]}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Send a new message with the refreshed keyboard in the new language
    await query.message.reply_text(
        t('language_set', lang_code, language_name=LANGUAGES[lang_code]),
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(lang_code)
    )


# ============ RATING CALLBACK ============

async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle digest rating button presses."""
    from .user_storage import get_user_language, rate_article
    from .personalization import apply_digest_feedback
    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    data = query.data  # e.g., "rate_up_abc123" or "rate_down_abc123"
    parts = data.split('_')
    if len(parts) >= 3:
        rating_type = parts[1]  # 'up' or 'down'
        digest_id = parts[2]  # unique digest ID
        # Store rating and update preference profile.
        rate_article(telegram_id, f"digest_{digest_id}", rating_type)
        apply_digest_feedback(telegram_id, digest_id, rating_type)
        if rating_type == 'up':
            emoji = "+"
            text = "Thanks for your feedback! Glad you liked it."
        else:
            emoji = "-"
            text = "Thanks for your feedback! We'll take note."
        await query.answer(text, show_alert=False)
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"OK {emoji} Rated", callback_data="rated")]
            ])
        )
    else:
        await query.answer("Invalid rating payload", show_alert=True)

async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refresh button press - fetch fresh news digest."""
    from .user_storage import get_user_language, get_refresh_session, update_refresh_session, get_article_hash, save_temp_digest
    from .translations import t
    from .cache import clear_cached_digest, build_digest_cache_key, set_cached_digest
    from .personalization import rank_articles_for_user, record_digest_context
    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    # Resolve enabled sources for scoped cache invalidation.
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github']
    try:
        from .database import get_user
        user = get_user(telegram_id)
        if user and user.get('sources'):
            sources = user.get('sources')
    except Exception:
        pass
    cache_key = build_digest_cache_key(language=user_lang, sources=sources, scope='news')
    # Check refresh limits
    session = get_refresh_session(telegram_id)
    attempts = session.get('attempts', 0)
    if attempts >= 2:
        await query.answer()
        await query.message.reply_text(t('refresh_limit', user_lang), parse_mode='Markdown')
        return
    # Clear only this user's digest variant cache.
    clear_cached_digest(cache_key=cache_key)
    # Acquire distributed lock
    from .distributed_lock import DistributedLock
    lock = DistributedLock('news_generation', telegram_id, ttl_seconds=300)
    if not lock.acquire():
        await query.answer("Generating...", show_alert=True)
        return
    await query.answer("Fetching fresh news...")
    loading_text = "Fetching fresh news..."
    await query.message.reply_text(loading_text)
    try:
        from .scrapers.hackernews import fetch_hackernews
        from .scrapers.techcrunch import fetch_techcrunch
        from .scrapers.ai_blogs import fetch_ai_blogs
        from .scrapers.theverge import fetch_theverge
        from .scrapers.github_trending import fetch_github_trending
        from .summarizer import summarize_news
        tasks = []
        if 'hackernews' in sources:
            tasks.append(fetch_hackernews(20))
        if 'techcrunch' in sources:
            tasks.append(asyncio.to_thread(fetch_techcrunch, 15))
        if 'ai_blogs' in sources:
            tasks.append(fetch_ai_blogs(6))
        if 'theverge' in sources:
            tasks.append(asyncio.to_thread(fetch_theverge, 10))
        if 'github' in sources:
            tasks.append(asyncio.to_thread(fetch_github_trending, 10))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_news = []
        for res in results:
            if isinstance(res, list):
                all_news.extend(res)
            elif isinstance(res, Exception):
                print(f"Error fetching news in refresh: {res}")
        if not all_news:
            error_text = "Could not fetch news."
            await query.message.reply_text(error_text)
            return
        # Filter out seen articles.
        seen_hashes = set(session.get('seen_hashes', []))
        fresh_news = [item for item in all_news if get_article_hash(item) not in seen_hashes]
        # Build candidate pool.
        if fresh_news:
            candidate_news = fresh_news
        else:
            candidate_news = all_news
        ranked_news = rank_articles_for_user(telegram_id, candidate_news)
        items_to_summarize = ranked_news[:10]
        if not items_to_summarize:
            error_text = "Could not select stories."
            await query.message.reply_text(error_text)
            return
        new_seen = seen_hashes.union({get_article_hash(i) for i in items_to_summarize})
        update_refresh_session(telegram_id, {
            'attempts': attempts + 1,
            'seen_hashes': list(new_seen)
        })
        digest = await summarize_news(items_to_summarize, language=user_lang)
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        # Persist callback context.
        save_temp_digest(digest_id, telegram_id, digest, articles_meta=items_to_summarize, ttl_hours=24)
        record_digest_context(digest_id, telegram_id, items_to_summarize)
        # Refresh cache with latest digest variant.
        set_cached_digest(digest, ttl_minutes=15, cache_key=cache_key)
        reply_markup = get_digest_reply_markup(digest_id, user_lang)
        from .message_utils import split_message
        chunks = split_message(digest)
        try:
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await query.message.reply_text(
                        chunk,
                        parse_mode='Markdown',
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                else:
                    await query.message.reply_text(
                        chunk,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
        except Exception:
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await query.message.reply_text(
                        chunk,
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                else:
                    await query.message.reply_text(
                        chunk,
                        disable_web_page_preview=True
                    )
    except Exception as e:
        error_text = f"Error: {str(e)[:50]}"
        await query.message.reply_text(error_text)
    finally:
        lock.release()

async def save_digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle save digest button press - extract and save article URLs from digest context."""
    from .user_storage import get_user_language, save_article, get_temp_digest
    import re
    query = update.callback_query
    await query.answer("Saving...")
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    callback_data = query.data
    parts = callback_data.split('_')
    if len(parts) < 3:
        await query.answer("Error: Invalid callback data", show_alert=True)
        return
    digest_id = parts[2]
    digest_data = get_temp_digest(digest_id)
    if not digest_data:
        await query.answer("Digest not found", show_alert=True)
        return
    digest_content = digest_data.get('content', '')
    articles_meta = digest_data.get('articles_meta', [])
    saved_count = 0
    # Preferred path: use exact article metadata.
    for item in articles_meta:
        title = (item.get('title') or item.get('url') or 'Untitled')[:100]
        url = item.get('url', '')
        source = item.get('source', '')
        if url and save_article(telegram_id, title, url, source):
            saved_count += 1
    # Fallback parsing from markdown in case metadata is missing.
    if not articles_meta and digest_content:
        url_pattern = r'\[([^\]]+)\]\((https?://[^)]+)\)'
        matches = re.findall(url_pattern, digest_content)
        plain_url_pattern = r'(?<!\()https?://[^\s\)\]]+'
        plain_urls = re.findall(plain_url_pattern, digest_content)
        for title, url in matches:
            clean_title = title.strip()[:100]
            if save_article(telegram_id, clean_title, url, ''):
                saved_count += 1
        for url in plain_urls:
            if any(url in m[1] for m in matches):
                continue
            title = f"Article {datetime.now().strftime('%Y-%m-%d')}"
            if save_article(telegram_id, title, url, ''):
                saved_count += 1
    if saved_count > 0:
        text = f"Saved {saved_count} articles! Use /saved to view."
        await query.answer(text, show_alert=True)
    else:
        text = "All articles already saved or no links to save."
        await query.answer(text, show_alert=True)


async def why_digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a quick \"why it matters\" explanation for a digest."""
    from .user_storage import get_user_language, get_temp_digest
    from .summarizer import get_async_client
    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    parts = query.data.split('_')
    if len(parts) < 3:
        await query.answer("Invalid request", show_alert=True)
        return
    digest_id = parts[2]
    digest_data = get_temp_digest(digest_id)
    if not digest_data:
        await query.answer("Digest context expired", show_alert=True)
        return
    await query.answer("Analyzing...")
    digest_content = (digest_data.get('content') or '')[:3500]
    if not digest_content:
        await query.message.reply_text("Digest data not found.")
        return
    if user_lang == 'ru':
        system_prompt = "Summarize why this digest matters in Russian with 3 bullet points and 1 actionable takeaway."
        user_prompt = f"Digest:\n\n{digest_content}"
    else:
        system_prompt = "You are a tech analyst. Explain why this digest matters: 3 bullets + 1 actionable takeaway."
        user_prompt = f"Digest:\n\n{digest_content}"
    try:
        client = get_async_client()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model='deepseek-chat',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.4,
                max_tokens=350,
            ),
            timeout=25.0,
        )
        answer = response.choices[0].message.content
        try:
            await query.message.reply_text(answer, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(answer, disable_web_page_preview=True)
    except Exception as e:
        err = f"Could not generate analysis: {str(e)[:80]}"
        await query.message.reply_text(err)

# ============ Q&A HANDLER ============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message - button presses or questions for DeepSeek."""
    from .user_storage import get_user_language
    from .translations import t
    
    user_message = update.message.text
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Skip if message is too short
    if not user_message or len(user_message) < 2:
        return
        
    # Validation: Message length for AI
    if len(user_message) > 1000:
        await update.message.reply_text("вќЊ Message too long (max 1000 chars).")
        return
    
    # Handle button presses - REMOVED (now using command menu only)
    # The big persistent keyboard has been disabled, so these checks are no longer needed.
    # Users should use the /slash commands from the menu.
    
    # Check if it's a URL to save
    if user_message.startswith('http://') or user_message.startswith('https://'):
        from .user_storage import save_article
        if save_article(telegram_id, user_message[:50], user_message):
            await update.message.reply_text(t('link_saved', user_lang))
        else:
            await update.message.reply_text(t('link_exists', user_lang))
        return
    
    # Otherwise, treat as a question for AI
    from .summarizer import get_async_client
    from .rate_limiter import check_rate_limit
    
    # Rate limit AI chat
    allowed, message = check_rate_limit(telegram_id, 'ai_chat')
    if not allowed:
        await update.message.reply_text(t('rate_limited', user_lang, seconds='60'))
        return
    
    await update.message.reply_text(t('thinking', user_lang), parse_mode='Markdown')
    
    lang_instruction = ""
    if user_lang == 'ru':
        lang_instruction = " Respond in Russian."
    elif user_lang == 'az':
        lang_instruction = " Respond in Azerbaijani."
    
    try:
        client = get_async_client()
        
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system", 
                    "content": f"""You are a helpful tech news assistant. 
Current Date: {datetime.now(BAKU_TZ).strftime('%Y-%m-%d')}
Users may ask you:
- Questions about tech news, AI developments, or industry trends
- To explain what a news item means
- For more details about a technology or company
- General tech questions

Be concise, informative, and friendly. Use emojis sparingly. 
If the question is about a specific news item, provide context and explain its significance.
Keep responses under 300 words unless more detail is needed.{lang_instruction}"""
                },
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        answer = response.choices[0].message.content
        
        # Send answer (split if too long) with markdown error handling
        async def send_answer(text):
            try:
                await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)
            except Exception:
                await update.message.reply_text(text, disable_web_page_preview=True)
        
        # Smart message splitting to avoid breaking UTF-8, URLs, or markdown
        from .message_utils import split_message
        chunks = split_message(answer)
        for chunk in chunks:
            await send_answer(chunk)
            
    except Exception as e:
        await update.message.reply_text(t('ai_error', user_lang, error=str(e)[:100]))


# ============ BOT SETUP ============

async def setup_bot_commands(application: Application):
    """Set up bot commands for the native Telegram command menu."""
    from telegram import BotCommand, MenuButtonCommands
    
    # English commands
    commands_en = [
        BotCommand("start", "Start the bot"),
        BotCommand("news", "Get AI news digest"),
        BotCommand("saved", "View saved articles"),
        BotCommand("search", "Search articles"),
        BotCommand("semsearch", "Semantic search saved"),
        BotCommand("filter", "Filter saved by category"),
        BotCommand("recap", "Weekly saved articles recap"),
        BotCommand("status", "View your settings"),
        BotCommand("language", "Change language"),
        BotCommand("sources", "Toggle news sources"),
        BotCommand("schedule", "Set digest schedule"),
        BotCommand("timezone", "Set timezone"),
        BotCommand("quiet_hours", "Set quiet hours"),
        BotCommand("trendalerts", "Weekly trend alerts"),
        BotCommand("admin_status", "Admin observability"),
        BotCommand("share", "Share bot with friends"),
        BotCommand("trends", "Weekly topic trends"),
        BotCommand("help", "Show help"),
    ]
    
    # Russian commands
    commands_ru = [
        BotCommand("start", "Р—Р°РїСѓСЃС‚РёС‚СЊ Р±РѕС‚Р°"),
        BotCommand("news", "РџРѕР»СѓС‡РёС‚СЊ РґР°Р№РґР¶РµСЃС‚ РЅРѕРІРѕСЃС‚РµР№"),
        BotCommand("saved", "РЎРѕС…СЂР°РЅС‘РЅРЅС‹Рµ СЃС‚Р°С‚СЊРё"),
        BotCommand("search", "РџРѕРёСЃРє СЃС‚Р°С‚РµР№"),
        BotCommand("semsearch", "Умный поиск"),
        BotCommand("filter", "Р¤РёР»СЊС‚СЂ РїРѕ РєР°С‚РµРіРѕСЂРёСЏРј"),
        BotCommand("recap", "Р•Р¶РµРЅРµРґРµР»СЊРЅР°СЏ СЃРІРѕРґРєР°"),
        BotCommand("status", "РќР°СЃС‚СЂРѕР№РєРё"),
        BotCommand("language", "РЇР·С‹Рє"),
        BotCommand("sources", "РСЃС‚РѕС‡РЅРёРєРё РЅРѕРІРѕСЃС‚РµР№"),
        BotCommand("schedule", "Р Р°СЃРїРёСЃР°РЅРёРµ"),
        BotCommand("timezone", "Часовой пояс"),
        BotCommand("quiet_hours", "Тихие часы"),
        BotCommand("trendalerts", "Тренд-уведомления"),
        BotCommand("admin_status", "Статус системы"),
        BotCommand("share", "РџРѕРґРµР»РёС‚СЊСЃСЏ Р±РѕС‚РѕРј"),
        BotCommand("trends", "РўСЂРµРЅРґС‹ РЅРµРґРµР»Рё"),
        BotCommand("help", "РџРѕРјРѕС‰СЊ"),
    ]
    
    # Set commands for different languages
    await application.bot.set_my_commands(commands_en, language_code="en")
    await application.bot.set_my_commands(commands_ru, language_code="ru")
    
    # Set menu button to show commands (creates the blue "Menu" button at bottom-left)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    
    print("Bot commands and menu button registered successfully")

def create_bot_application() -> Application:
    """Create and configure the Telegram bot application with HTTP timeouts."""
    from telegram.request import HTTPXRequest
    
    token = get_bot_token()
    
    # Configure HTTP request with aggressive timeouts directly
    # HTTPXRequest takes timeout parameters directly in this version
    request = HTTPXRequest(
        connect_timeout=5.0,    # 5s to establish connection
        read_timeout=20.0,      # 20s to read response
        write_timeout=10.0,     # 10s to send request
        pool_timeout=5.0,       # 5s to get connection from pool
        connection_pool_size=100
    )
    
    # Build application with custom HTTP request configuration
    # Note: Cannot set http_version when using custom request
    # PTB 20.8 + Python 3.13 can fail while constructing Updater internals.
    # This project runs in webhook mode, so we explicitly disable Updater.
    application = (
        Application.builder()
        .token(token)
        .request(request)
        .updater(None)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("settime", settime_command))
    application.add_handler(CommandHandler("sources", sources_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # New feature commands
    application.add_handler(CommandHandler("saved", saved_command))
    application.add_handler(CommandHandler("save", save_command))
    application.add_handler(CommandHandler("clear_saved", clear_saved_command))
    application.add_handler(CommandHandler("clear", clear_saved_command))  # Alias for /clear_saved
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("filter", filter_command))
    application.add_handler(CommandHandler("recap", recap_command))
    application.add_handler(CommandHandler("share", share_command))
    application.add_handler(CommandHandler("trends", trends_command))
    application.add_handler(CommandHandler("timezone", timezone_command))
    application.add_handler(CommandHandler("quiet_hours", quiet_hours_command))
    application.add_handler(CommandHandler("trendalerts", trendalerts_command))
    application.add_handler(CommandHandler("semsearch", semantic_search_command))
    application.add_handler(CommandHandler("admin_status", admin_status_command))
    
    # Add callback query handlers for inline buttons
    application.add_handler(CallbackQueryHandler(toggle_source_callback, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(schedule_callback, pattern='^schedule_'))
    application.add_handler(CallbackQueryHandler(rating_callback, pattern='^rate_'))
    application.add_handler(CallbackQueryHandler(refresh_callback, pattern='^refresh_'))
    application.add_handler(CallbackQueryHandler(save_digest_callback, pattern='^save_digest_'))
    application.add_handler(CallbackQueryHandler(why_digest_callback, pattern='^why_digest_'))
    application.add_handler(CallbackQueryHandler(delete_article_callback, pattern='^del_'))
    
    # Add message handler for buttons and Q&A (handles any text that isn't a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Set up bot commands for native Telegram menu (will be called after initialization)
    application.post_init = setup_bot_commands
    
    return application


async def send_digest_to_user(telegram_id: int, digest: str, articles_meta: list = None):
    """Send a digest message to a specific user."""
    from telegram import Bot
    from .user_storage import get_user_language, save_temp_digest
    from .personalization import record_digest_context
    import hashlib
    
    bot = Bot(token=get_bot_token())
    user_lang = get_user_language(telegram_id)
    
    # Generate digest ID for buttons
    digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
    
    # Persist temp digest context so callbacks work for scheduled sends too.
    try:
        save_temp_digest(digest_id, telegram_id, digest, articles_meta=articles_meta or [], ttl_hours=24)
        if articles_meta:
            record_digest_context(digest_id, telegram_id, articles_meta)
    except Exception as e:
        print(f"Error storing scheduled digest context: {e}")

    reply_markup = get_digest_reply_markup(digest_id, user_lang)
    
    try:
        # Smart message splitting to avoid breaking UTF-8, URLs, or markdown
        from .message_utils import split_message
        chunks = split_message(digest)
        
        for i, chunk in enumerate(chunks):
            # Add buttons only to the last chunk
            if i == len(chunks) - 1:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
            else:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        return True
    except Exception as e:
        print(f"Error sending to user {telegram_id}: {e}")
        return False



