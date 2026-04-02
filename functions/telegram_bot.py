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
PERSONALIZED_DIGEST_ITEM_LIMIT = 14


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
            InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
            InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
            InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
        ],
        [
            InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
            InlineKeyboardButton(why_label, callback_data=f"why_digest_{digest_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def _digest_action_texts(lang: str) -> dict:
    """Localized callback copy for digest action buttons."""
    if lang == 'ru':
        return {
            'saving': 'Сохраняю...',
            'saved': 'Сохранено статей: {count}. Откройте /saved.',
            'save_empty': 'Все статьи уже сохранены или ссылки не найдены.',
            'invalid': 'Некорректный запрос.',
            'not_found': 'Контекст дайджеста истёк.',
            'analyzing': 'Анализирую...',
            'digest_missing': 'Не удалось найти данные дайджеста.',
            'analysis_error': 'Не удалось подготовить объяснение: {error}',
        }

    return {
        'saving': 'Saving...',
        'saved': 'Saved {count} articles. Open /saved to view them.',
        'save_empty': 'All articles are already saved or no links were found.',
        'invalid': 'Invalid request.',
        'not_found': 'Digest context expired.',
        'analyzing': 'Analyzing...',
        'digest_missing': 'Could not find digest data.',
        'analysis_error': 'Could not prepare the explanation: {error}',
    }


# ============ KEYBOARD MENUS ============

def get_main_keyboard(lang: str = 'en'):
    """Get the main persistent keyboard with quick action buttons."""
    from telegram import ReplyKeyboardRemove
    
    # Return ReplyKeyboardRemove to hide the big keyboard buttons
    # Users now use the Telegram Menu button for all commands
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
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github', 'producthunt']
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
        from .security_utils import stable_hash
        digest_id = stable_hash(cached_digest[:100])[:8]
        reply_markup = get_digest_reply_markup(digest_id, user_lang)
        
        from .message_utils import split_message
        chunks = split_message(header + cached_digest)

        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            try:
                await update.message.reply_text(
                    chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True,
                    reply_markup=reply_markup if is_last else None
                )
            except Exception:
                await update.message.reply_text(
                    chunk,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup if is_last else None
                )
        return
    
    # Check if already generating using distributed lock
    from .distributed_lock import is_locked
    if is_locked('news_generation', telegram_id):
        wait_text = "⏳ Дайджест уже генерируется, пожалуйста подождите..." if user_lang == 'ru' else "⏳ Digest is already being generated, please wait..."
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
        wait_text = "⏳ Дайджест уже генерируется, пожалуйста подождите..." if user_lang == 'ru' else "⏳ Digest is already being generated, please wait..."
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
        from .scrapers.producthunt import fetch_producthunt
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
        if 'producthunt' in sources:
            tasks.append(asyncio.to_thread(fetch_producthunt, 8))
            
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
        items_to_summarize = ranked_news[:PERSONALIZED_DIGEST_ITEM_LIMIT]
        
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
        from .security_utils import stable_hash
        digest_id = stable_hash(digest[:100])[:8]
        
        # Store full digest + metadata for callback actions and personalization.
        try:
            from .user_storage import save_temp_digest
            from .personalization import record_digest_context
            save_temp_digest(
                digest_id,
                telegram_id,
                digest,
                articles_meta=items_to_summarize,
                language=user_lang,
                ttl_hours=24,
            )
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
                check = "✓ " if time == current_time else ""
                row.append(InlineKeyboardButton(f"{check}{time}", callback_data=f"schedule_{time}"))
        keyboard.append(row)
    
    # Add disable option
    disable_text = "🚫 Отключить" if user_lang == 'ru' else "🚫 Disable"
    keyboard.append([InlineKeyboardButton(disable_text, callback_data="schedule_disable")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    header = "⏰ *Выберите время для ежедневного дайджеста:*" if user_lang == 'ru' else "⏰ *Choose time for daily digest:*"
    if current_time:
        current_text = f"\n\n_Текущее время: {current_time}_" if user_lang == 'ru' else f"\n\n_Current time: {current_time}_"
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
        
        msg = "✅ Ежедневный дайджест отключен." if user_lang == 'ru' else "✅ Daily digest disabled."
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
        msg = f"✅ Ежедневный дайджест запланирован на *{selected_time}*!\n\nВы будете получать персональные новости технологий в это время каждый день."
    else:
        msg = f"✅ Daily digest scheduled for *{selected_time}*!\n\nYou will receive personalized tech news at this time every day."
    
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
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github', 'producthunt']  # Default all enabled
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
            f"{'✅' if 'hackernews' in sources else '❌'} Hacker News",
            callback_data='toggle_hackernews'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'techcrunch' in sources else '❌'} TechCrunch",
            callback_data='toggle_techcrunch'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'ai_blogs' in sources else '❌'} AI Blogs",
            callback_data='toggle_ai_blogs'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'theverge' in sources else '❌'} The Verge",
            callback_data='toggle_theverge'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'github' in sources else '❌'} GitHub Trending",
            callback_data='toggle_github'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'producthunt' in sources else '❌'} Product Hunt",
            callback_data='toggle_producthunt'
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
            f"{'✅' if 'hackernews' in new_sources else '❌'} Hacker News",
            callback_data='toggle_hackernews'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'techcrunch' in new_sources else '❌'} TechCrunch",
            callback_data='toggle_techcrunch'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'ai_blogs' in new_sources else '❌'} AI Blogs",
            callback_data='toggle_ai_blogs'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'theverge' in new_sources else '❌'} The Verge",
            callback_data='toggle_theverge'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'github' in new_sources else '❌'} GitHub Trending",
            callback_data='toggle_github'
        )],
        [InlineKeyboardButton(
            f"{'✅' if 'producthunt' in new_sources else '❌'} Product Hunt",
            callback_data='toggle_producthunt'
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
        'producthunt': 'Product Hunt',
    }
    
    sources_text = '\n'.join([f"  вЂў {source_names.get(s, s)}" for s in sources])
    if not sources:
        sources_text = '  No sources selected' if user_lang == 'en' else '  Нет выбранных источников'

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

async def _render_saved_page(update_or_query, telegram_id: int, user_lang: str, page: int, is_callback: bool = False):
    from .user_storage import get_saved_articles
    from .translations import t
    
    limit = 10
    offset = page * limit
    # Fetch limit + 1 to check if there is a next page
    articles = get_saved_articles(telegram_id, limit=limit + 1, offset=offset)
    
    has_next = len(articles) > limit
    articles = articles[:limit]
    
    if not articles and page == 0:
        msg = t('no_saved', user_lang)
        if is_callback:
            await update_or_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update_or_query.message.reply_text(msg, parse_mode='Markdown')
        return
    elif not articles and page > 0:
        # Should rarely happen unless items were deleted from under the user
        await update_or_query.answer("No more articles.", show_alert=True)
        return

    cat_emoji = {
        'ai': '🤖', 'security': '🔒', 'crypto': '💰', 'startups': '🚀',
        'hardware': '💻', 'software': '📱', 'tech': '🔧'
    }
    
    message = t('saved_header', user_lang)
    if page > 0:
        # Append page info safely preserving any whitespace
        message = message.rstrip() + f" (Page {page + 1})\n\n"

    keyboard = []
    
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        category = article.get('category', 'tech')
        saved_at = article.get('saved_at', '')
        
        emoji = cat_emoji.get(category, '🔧')
        date_str = saved_at[:10] if saved_at else ''
        
        from .security_utils import escape_markdown_v1
        safe_title = escape_markdown_v1(title)
        
        item_num = offset + i

        if url.startswith('http'):
            message += f"{item_num}. {emoji} [{safe_title}]({url})"
        else:
            message += f"{item_num}. {emoji} {safe_title}"
        
        if date_str:
            message += f" `{date_str}`"
        message += "\n"
        
        # Create delete button - use URL hash for unique ID
        from .security_utils import stable_hash
        url_hash = stable_hash(url)[:8]
        delete_label = "🗑️"
        # encode page in callback data so delete button can refresh the correct page
        keyboard.append([InlineKeyboardButton(f"{delete_label} {item_num}. {title[:25]}...", callback_data=f"del_{url_hash}_{page}")])
    
    message += t('saved_footer', user_lang)

    # Add pagination buttons
    nav_buttons = []
    if page > 0:
        prev_text = "⬅️ Назад" if user_lang == 'ru' else "⬅️ Previous"
        nav_buttons.append(InlineKeyboardButton(prev_text, callback_data=f"saved_page_{page-1}"))
    if has_next:
        next_text = "Вперед ➡️" if user_lang == 'ru' else "Next ➡️"
        nav_buttons.append(InlineKeyboardButton(next_text, callback_data=f"saved_page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Add Clear All button
    clear_all_text = t('clear_all_btn', user_lang)
    keyboard.append([InlineKeyboardButton(clear_all_text, callback_data=f"clear_all_prompt_{page}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try:
        if is_callback:
            await update_or_query.edit_message_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        else:
            await update_or_query.message.reply_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
    except Exception:
        if is_callback:
            await update_or_query.edit_message_text(message, disable_web_page_preview=True, reply_markup=reply_markup)
        else:
            await update_or_query.message.reply_text(message, disable_web_page_preview=True, reply_markup=reply_markup)


async def saved_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle saved articles pagination."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    from .user_storage import get_user_language
    user_lang = get_user_language(telegram_id)

    data = query.data
    page = int(data.replace('saved_page_', ''))

    await _render_saved_page(query, telegram_id, user_lang, page, is_callback=True)


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /saved command - show saved articles with delete buttons."""
    from .user_storage import get_user_language

    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)

    await _render_saved_page(update, telegram_id, user_lang, 0, is_callback=False)


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


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /export command - export saved articles as a Markdown file."""
    from .translations import t
    from .user_storage import get_all_saved_articles, get_user_language
    import io

    def _clean_export_value(value) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        return str(value).replace("\r", " ").replace("\n", " ").strip()

    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    articles = get_all_saved_articles(telegram_id)

    if not articles:
        await update.message.reply_text(t('export_empty', user_lang), parse_mode='Markdown')
        return

    lines = [
        "# LensAI Saved Articles",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Total articles: {len(articles)}",
        "",
    ]

    for index, article in enumerate(articles, 1):
        title = _clean_export_value(article.get('title')) or "Untitled"
        url = _clean_export_value(article.get('url'))
        source = _clean_export_value(article.get('source'))
        category = article.get('category', 'tech') or 'tech'
        category_label = _clean_export_value(t(f'cat_{category}', user_lang))
        saved_at = _clean_export_value(article.get('saved_at'))

        lines.append(f"## {index}. {title}")
        lines.append(f"- Category: {category_label}")
        if source:
            lines.append(f"- Source: {source}")
        if saved_at:
            lines.append(f"- Saved: {saved_at}")
        if url:
            lines.append(f"- URL: <{url}>")
        lines.append("")

    document = io.BytesIO("\n".join(lines).encode('utf-8'))
    document.name = f"lensai_saved_articles_{datetime.now().strftime('%Y%m%d')}.md"

    await update.message.reply_document(
        document=document,
        caption=t('export_caption', user_lang, count=len(articles)),
        parse_mode='Markdown'
    )


async def clear_all_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clear all prompt button press."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    from .user_storage import get_user_language
    from .translations import t
    user_lang = get_user_language(telegram_id)

    data = query.data
    page = data.replace('clear_all_prompt_', '')

    message = t('clear_all_prompt', user_lang)
    keyboard = [
        [InlineKeyboardButton(t('clear_all_confirm_btn', user_lang), callback_data=f"clear_all_confirm_{page}")],
        [InlineKeyboardButton(t('clear_all_cancel_btn', user_lang), callback_data=f"clear_all_cancel_{page}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def clear_all_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clear all confirm button press."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    from .user_storage import clear_saved_articles, get_user_language
    from .translations import t

    user_lang = get_user_language(telegram_id)
    clear_saved_articles(telegram_id)

    await query.edit_message_text(
        t('cleared_saved', user_lang),
        parse_mode='Markdown'
    )

async def clear_all_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clear all cancel button press."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    from .user_storage import get_user_language

    user_lang = get_user_language(telegram_id)
    data = query.data
    try:
        page = int(data.replace('clear_all_cancel_', ''))
    except (TypeError, ValueError):
        page = 0

    await _render_saved_page(query, telegram_id, user_lang, page, is_callback=True)

async def search_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle search history button press."""
    query = update.callback_query
    await query.answer()

    # Extract the query safely
    search_query = query.data[15:] if query.data.startswith('search_history_') else query.data

    # Set context.args
    context.args = search_query.split()

    # Call search_command
    await search_command(update, context)

async def clear_search_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clear search history button press."""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    from .user_storage import clear_search_history, get_user_language

    clear_search_history(telegram_id)
    user_lang = get_user_language(telegram_id)

    msg = "✅ История поиска очищена." if user_lang == 'ru' else "✅ Search history cleared."
    await query.edit_message_text(msg, parse_mode='Markdown')

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
        await update.message.reply_text("❌ Category name too long.")
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
        'ai': '🤖', 'security': '🔒', 'crypto': '💰', 'startups': '🚀',
        'hardware': '💻', 'software': '📱', 'tech': '🔧'
    }
    
    message = t('recap_header', user_lang)
    
    # Show top 5 recent articles
    for i, article in enumerate(weekly_articles[:5], 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        category = article.get('category', 'tech')
        emoji = cat_emoji.get(category, '🔧')
        
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
    loading_text = "📊 Анализирую тренды..." if user_lang == 'ru' else "📊 Analyzing trends..."
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
        error_text = "❌ Ошибка при анализе трендов." if user_lang == 'ru' else "❌ Error analyzing trends."
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
    from .user_storage import get_user_language, get_all_saved_articles, delete_saved_article
    from .translations import t
    
    query = update.callback_query
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Get the URL hash and page from callback data
    data = query.data  # e.g., "del_abc12345_0"
    parts = data.split('_')
    if len(parts) >= 2:
        url_hash = parts[1]
    else:
        url_hash = data.replace('del_', '')

    page = int(parts[2]) if len(parts) > 2 else 0
    
    # Find the article with matching hash
    from .security_utils import stable_hash
    articles = get_all_saved_articles(telegram_id)
    article_title = ""
    
    for article in articles:
        article_hash = stable_hash(article.get('url', ''))[:8]
        if article_hash == url_hash:
            article_title = article.get('title', '')[:40]
            delete_saved_article(telegram_id, article.get('url', ''))
            break

    if article_title:
        await query.answer(f"Deleted: {article_title}", show_alert=False)
    else:
        await query.answer("Article deleted!", show_alert=False)

    # Refresh the current page
    await _render_saved_page(query, telegram_id, user_lang, page, is_callback=True)


# ============ SEARCH ============

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command - search news by topic."""
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .security_utils import escape_markdown_v1
    from .user_storage import add_search_history, get_user_language, get_search_history
    from .rate_limiter import check_rate_limit
    from .translations import t
    
    reply_msg = update.message if update.message else update.callback_query.message
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Rate limit check
    allowed, message = check_rate_limit(telegram_id, 'search')
    if not allowed:
        await reply_msg.reply_text(t('rate_limited', user_lang, seconds='60'))
        return
    
    if not context.args:
        prompt = t('search_prompt', user_lang)

        # Fetch and append recent search history
        recent_searches = get_search_history(telegram_id, limit=5)
        reply_markup = None
        if recent_searches:
            unique_searches = list(dict.fromkeys(recent_searches))
            header = t('search_history_header', user_lang)
            prompt += f"\n\n{header}"

            keyboard = []
            for query in unique_searches:
                keyboard.append([InlineKeyboardButton(f"🔍 {query}", callback_data=f"search_history_{query[:45]}")])
            keyboard.append([InlineKeyboardButton("🗑️ Clear History" if user_lang == 'en' else "🗑️ Очистить историю", callback_data="clear_search_history")])
            reply_markup = InlineKeyboardMarkup(keyboard)

        await reply_msg.reply_text(
            prompt,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    query = ' '.join(context.args).strip()
    query_lower = query.lower()
    
    # Validation
    if len(query) > 100:
        await reply_msg.reply_text("❌ Search query too long (max 100 chars).")
        return
        
    if len(query) < 2:
        await reply_msg.reply_text("❌ Search query too short.")
        return
    
    add_search_history(telegram_id, query)
    
    # Escape query for display
    from .security_utils import escape_markdown_v1
    safe_query = escape_markdown_v1(query)
    
    await reply_msg.reply_text(t('searching', user_lang, query=safe_query), parse_mode='Markdown')
    
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
            await reply_msg.reply_text(
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
        
        await reply_msg.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await reply_msg.reply_text(t('error_fetching', user_lang, error=str(e)[:100]))


# ============ LANGUAGE ============

LANGUAGES = {
    'en': '🇬🇧 English',
    'ru': '🇷🇺 Русский'
}

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command - change language."""
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    current_lang = get_user_language(telegram_id)
    
    keyboard = []
    for code, name in LANGUAGES.items():
        check = "✓ " if code == current_lang else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"lang_{code}")])
    
    # Azerbaijani - coming soon
    keyboard.append([InlineKeyboardButton("🇦🇿 Azərbaycan (Tezliklə)", callback_data="lang_coming_soon")])
    
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
        check = "✓ " if code == lang_code else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"lang_{code}")])
    
    # Azerbaijani - coming soon
    keyboard.append([InlineKeyboardButton("🇦🇿 Azərbaycan (Tezliklə)", callback_data="lang_coming_soon")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update the message with the new keyboard showing the checkmark on selected language
    await query.edit_message_text(
        t('select_language', lang_code) + f"\n\n✅ {LANGUAGES[lang_code]}",
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
    sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github', 'producthunt']
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
        from .scrapers.producthunt import fetch_producthunt
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
        if 'producthunt' in sources:
            tasks.append(asyncio.to_thread(fetch_producthunt, 10))
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
        items_to_summarize = ranked_news[:PERSONALIZED_DIGEST_ITEM_LIMIT]
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
        from .security_utils import stable_hash
        digest_id = stable_hash(digest[:100])[:8]
        # Persist callback context.
        save_temp_digest(
            digest_id,
            telegram_id,
            digest,
            articles_meta=items_to_summarize,
            language=user_lang,
            ttl_hours=24,
        )
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
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    texts = _digest_action_texts(user_lang)
    await query.answer(texts['saving'])
    callback_data = query.data
    parts = callback_data.split('_')
    if len(parts) < 3:
        await query.answer(texts['invalid'], show_alert=True)
        return
    digest_id = parts[2]
    digest_data = get_temp_digest(digest_id)
    if not digest_data:
        await query.answer(texts['not_found'], show_alert=True)
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
        text = texts['saved'].format(count=saved_count)
        await query.answer(text, show_alert=True)
    else:
        await query.answer(texts['save_empty'], show_alert=True)


async def why_digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a quick \"why it matters\" explanation for a digest."""
    from .user_storage import get_user_language, get_temp_digest, normalize_language_code
    from .summarizer import generate_why_digest
    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    texts = _digest_action_texts(user_lang)
    parts = query.data.split('_')
    if len(parts) < 3:
        await query.answer(texts['invalid'], show_alert=True)
        return
    digest_id = parts[2]
    digest_data = get_temp_digest(digest_id)
    if not digest_data:
        await query.answer(texts['not_found'], show_alert=True)
        return
    reply_lang = normalize_language_code(digest_data.get('language') or user_lang)
    texts = _digest_action_texts(reply_lang)
    await query.answer(texts['analyzing'])
    digest_content = (digest_data.get('content') or '')[:3500]
    articles_meta = digest_data.get('articles_meta') or []
    if not digest_content:
        await query.message.reply_text(texts['digest_missing'])
        return
    try:
        answer = await generate_why_digest(
            digest_content=digest_content,
            articles_meta=articles_meta,
            language=reply_lang,
        )
        try:
            await query.message.reply_text(answer, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(answer, disable_web_page_preview=True)
    except Exception as e:
        err = texts['analysis_error'].format(error=str(e)[:80])
        await query.message.reply_text(err)

async def summarize_url_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Summarize a saved URL."""
    from .user_storage import get_user_language, get_temp_url
    from .translations import t
    from .summarizer import chat_completion
    import httpx
    from bs4 import BeautifulSoup

    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)

    parts = query.data.split('_')
    if len(parts) < 3:
        await query.answer("Invalid request", show_alert=True)
        return

    url_hash = parts[2]
    url = get_temp_url(url_hash, telegram_id)

    if not url:
        await query.answer("Link expired. Please send the link again.", show_alert=True)
        return

    await query.answer(t('summarizing_link', user_lang))

    try:
        # Fetch content
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        # Parse content safely
        soup = await asyncio.to_thread(BeautifulSoup, response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text_content = "\n\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])

        if not text_content:
            text_content = soup.get_text(strip=True)

        # Limit content size to avoid token limit
        text_content = text_content[:5000]

        if len(text_content) < 100:
            await query.message.reply_text("Could not extract enough text to summarize.")
            return

        # Prepare prompt
        if user_lang == 'ru':
            system_prompt = "Сделай краткое содержание этой статьи в 3 пунктах и добавь 1 главный вывод. Отвечай на русском языке."
        else:
            system_prompt = "Summarize this article in 3 bullet points and 1 actionable takeaway. Respond in English."

        user_prompt = f"Article:\n\n{text_content}"

        # Call AI
        answer = await chat_completion(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            timeout=25.0,
        )

        # Send back summary
        try:
            await query.message.reply_text(answer, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(answer, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:80]
        await query.message.reply_text(t('summary_error', user_lang, error=error_msg))


# ============ Q&A HANDLER ============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message - button presses or questions for the active AI model."""
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
        await update.message.reply_text("❌ Message too long (max 1000 chars).")
        return
    
    # Handle button presses - REMOVED (now using command menu only)
    # The big persistent keyboard has been disabled, so these checks are no longer needed.
    # Users should use the /slash commands from the menu.
    
    # Check if it's a URL to save
    if user_message.startswith('http://') or user_message.startswith('https://'):
        from .user_storage import save_article, save_temp_url
        from .security_utils import stable_hash

        is_saved = save_article(telegram_id, user_message[:50], user_message)

        url_hash = stable_hash(user_message)[:8]
        save_temp_url(url_hash, telegram_id, user_message)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t('btn_summarize', user_lang), callback_data=f"summarize_url_{url_hash}")]
        ])

        if is_saved:
            await update.message.reply_text(t('link_saved', user_lang), reply_markup=reply_markup)
        else:
            await update.message.reply_text(t('link_exists', user_lang), reply_markup=reply_markup)
        return
    
    # Otherwise, treat as a question for AI
    from .summarizer import chat_completion
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
        answer = await chat_completion(
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
            max_tokens=800,
            timeout=30.0,
        )

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
        BotCommand("export", "Export saved articles"),
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
        BotCommand("start", "Запустить бота"),
        BotCommand("news", "Получить дайджест новостей"),
        BotCommand("saved", "Сохранённые статьи"),
        BotCommand("export", "Экспорт статей"),
        BotCommand("search", "Поиск статей"),
        BotCommand("semsearch", "Умный поиск"),
        BotCommand("filter", "Фильтр по категориям"),
        BotCommand("recap", "Еженедельная сводка"),
        BotCommand("status", "Настройки"),
        BotCommand("language", "Язык"),
        BotCommand("sources", "Источники новостей"),
        BotCommand("schedule", "Расписание"),
        BotCommand("timezone", "Часовой пояс"),
        BotCommand("quiet_hours", "Тихие часы"),
        BotCommand("trendalerts", "Тренд-уведомления"),
        BotCommand("admin_status", "Статус системы"),
        BotCommand("share", "Поделиться ботом"),
        BotCommand("trends", "Тренды недели"),
        BotCommand("help", "Помощь"),
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
    application.add_handler(CommandHandler("export", export_command))
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
    application.add_handler(CallbackQueryHandler(saved_page_callback, pattern='^saved_page_'))
    application.add_handler(CallbackQueryHandler(summarize_url_callback, pattern='^summarize_url_'))
    application.add_handler(CallbackQueryHandler(clear_all_prompt_callback, pattern='^clear_all_prompt_'))
    application.add_handler(CallbackQueryHandler(clear_all_confirm_callback, pattern='^clear_all_confirm_'))
    application.add_handler(CallbackQueryHandler(clear_all_cancel_callback, pattern='^clear_all_cancel_'))
    application.add_handler(CallbackQueryHandler(search_history_callback, pattern='^search_history_'))
    application.add_handler(CallbackQueryHandler(clear_search_history_callback, pattern='^clear_search_history$'))
    
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
    from .security_utils import stable_hash
    
    bot = Bot(token=get_bot_token())
    user_lang = get_user_language(telegram_id)
    
    # Generate digest ID for buttons
    digest_id = stable_hash(digest[:100])[:8]
    
    # Persist temp digest context so callbacks work for scheduled sends too.
    try:
        save_temp_digest(
            digest_id,
            telegram_id,
            digest,
            articles_meta=articles_meta or [],
            language=user_lang,
            ttl_hours=24,
        )
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



