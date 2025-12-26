"""
Telegram Bot Module
Handles all Telegram bot interactions and commands.
"""

import os
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)


def get_bot_token() -> str:
    """Get Telegram bot token from environment."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    return token


# ============ KEYBOARD MENUS ============

def get_main_keyboard(lang: str = 'en'):
    """Get the main persistent keyboard with quick action buttons."""
    from telegram import ReplyKeyboardRemove
    
    # Return ReplyKeyboardRemove to hide the big keyboard buttons
    # Users will now use the ≡ Menu button (bottom left) for all commands
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
    
    welcome_message = t('welcome', user_lang, username=username)
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
    from .cache import get_cached_digest, set_cached_digest, get_digest_timestamp, is_digest_cached
    from .rate_limiter import check_rate_limit
    from .user_storage import get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Check cache first (no rate limit for cached responses)
    if is_digest_cached():
        cached_digest = get_cached_digest()
        timestamp = get_digest_timestamp()
        
        header = t('cached_news', user_lang, timestamp=timestamp[:16] if timestamp else 'recently')
        
        # Generate digest ID for buttons
        import hashlib
        digest_id = hashlib.md5(cached_digest[:100].encode()).hexdigest()[:8]
        
        # Define button labels based on language
        refresh_label = "🔄 Обновить" if user_lang == 'ru' else "🔄 Refresh"
        save_label = "🔖 Сохранить" if user_lang == 'ru' else "🔖 Save Digest"
        
        keyboard = [
            [
                InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
                InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
                InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
            ],
            [
                InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
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
        from .summarizer import summarize_news
        
        # Get user preferences from database (or use defaults)
        sources = ['hackernews', 'techcrunch', 'ai_blogs', 'theverge', 'github']  # Default all sources
        try:
            from .database import get_user
            user = get_user(telegram_id)
            if user and user.get('sources'):
                sources = user.get('sources')
        except Exception:
            pass  # Use defaults if database not available
        
        # Fetch news concurrently
        tasks = []
        
        if 'hackernews' in sources:
            tasks.append(fetch_hackernews(15))
        
        if 'techcrunch' in sources:
            # wrap sync function
            tasks.append(asyncio.to_thread(fetch_techcrunch, 10))
        
        if 'ai_blogs' in sources:
            tasks.append(fetch_ai_blogs(3))
        
        if 'theverge' in sources:
            tasks.append(asyncio.to_thread(fetch_theverge, 8))
        
        if 'github' in sources:
            tasks.append(asyncio.to_thread(fetch_github_trending, 5))
            
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
        
        # Summarize with DeepSeek (in user's language)
        digest = await summarize_news(all_news, language=user_lang)
        
        # Cache the digest for 15 minutes
        set_cached_digest(digest, ttl_minutes=15)
        
        # Generate unique digest ID for rating tracking
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        
        # Store full digest in Firestore for save button access
        try:
            from .user_storage import get_firestore_client
            db = get_firestore_client()
            if db:
                from google.cloud import firestore
                db.collection('digests_temp').document(digest_id).set({
                    'content': digest,
                    'user_id': telegram_id,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'expires_at': datetime.now() + timedelta(hours=24)
                })
        except Exception as e:
            print(f"Error storing digest: {e}")
        
        # Try to save digest to history (optional)
        try:
            from .database import save_digest
            save_digest(telegram_id, digest)
        except Exception:
            pass
        
        # Send digest (split if too long for Telegram)
        # Define button labels based on language
        refresh_label = "🔄 Обновить" if user_lang == 'ru' else "🔄 Refresh"
        save_label = "🔖 Сохранить" if user_lang == 'ru' else "🔖 Save Digest"
        
        async def send_chunk(chunk, is_last=False):
            try:
                if is_last:
                    # Add rating, refresh and save buttons to the last chunk
                    keyboard = [
                        [
                            InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
                            InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
                            InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
                        ],
                        [
                            InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
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
                    keyboard = [
                        [
                            InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
                            InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
                            InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
                        ],
                        [
                            InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
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
    disable_text = "❌ Отключить" if user_lang == 'ru' else "❌ Disable"
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
            create_or_update_user(telegram_id, schedule_time=None)
        except Exception:
            pass
        
        msg = "✅ Ежедневный дайджест отключен." if user_lang == 'ru' else "✅ Daily digest disabled."
        await query.edit_message_text(msg, parse_mode='Markdown')
        return
    
    # Set the selected time
    selected_time = data  # e.g. "18:00"
    
    try:
        create_or_update_user(telegram_id, schedule_time=selected_time)
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
        'ai_blogs': 'AI Blogs'
    }
    
    sources_text = '\n'.join([f"  • {source_names.get(s, s)}" for s in sources])
    if not sources:
        sources_text = '  No sources selected' if user_lang == 'en' else '  Нет выбранных источников'
    
    await update.message.reply_text(
        t('status_cloud', user_lang, 
          schedule_time=user.get('schedule_time', 'Not set'),
          timezone=user.get('timezone', 'Asia/Baku'),
          sources=sources_text),
        parse_mode='Markdown'
    )


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
        'ai': '🤖', 'security': '🔒', 'crypto': '💰', 'startups': '🚀',
        'hardware': '💻', 'software': '📱', 'tech': '🔧'
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
        emoji = cat_emoji.get(category, '🔧')
        
        # Format date
        date_str = saved_at[:10] if saved_at else ''
        
        # Build message line
        if url.startswith('http'):
            message += f"{i}. {emoji} [{title}]({url})"
        else:
            message += f"{i}. {emoji} {title}"
        
        if date_str:
            message += f" `{date_str}`"
        message += "\n"
        
        # Create delete button - use URL hash for unique ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        delete_label = "🗑️" if user_lang == 'en' else "🗑️"
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
            except:
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
    
    query = ' '.join(context.args).lower()
    add_search_history(telegram_id, query)
    
    await update.message.reply_text(t('searching', user_lang, query=query), parse_mode='Markdown')
    
    try:
        # Fetch news
        all_news = []
        all_news.extend(fetch_hackernews_sync(30))
        all_news.extend(fetch_techcrunch(20))
        
        # Filter by query
        results = []
        for article in all_news:
            title = article.get('title', '').lower()
            if query in title or any(word in title for word in query.split()):
                results.append(article)
        
        if not results:
            await update.message.reply_text(
                t('no_results', user_lang, query=query),
                parse_mode='Markdown'
            )
            return
        
        # Format results
        message = t('search_results', user_lang, query=query, count=len(results))
        for i, article in enumerate(results[:10], 1):
            title = article.get('title', '')[:60]
            url = article.get('url', '')
            source = article.get('source', '')
            message += f"{i}. [{title}]({url}) _{source}_\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await update.message.reply_text(t('error_fetching', user_lang, error=str(e)[:100]))


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
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    data = query.data  # e.g., "rate_up_abc123" or "rate_down_abc123"
    parts = data.split('_')
    
    if len(parts) >= 3:
        rating_type = parts[1]  # 'up' or 'down'
        digest_id = parts[2]  # unique digest ID
        
        # Store the rating
        rate_article(telegram_id, f"digest_{digest_id}", rating_type)
        
        # Show confirmation
        if rating_type == 'up':
            emoji = "👍"
            text = "Спасибо за отзыв! Рады, что понравилось!" if user_lang == 'ru' else "Thanks for your feedback! Glad you liked it!"
        else:
            emoji = "👎"
            text = "Спасибо за отзыв! Мы учтём это." if user_lang == 'ru' else "Thanks for your feedback! We'll take note."
        
        # Update the message to show the selected rating
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ {emoji} Оценено" if user_lang == 'ru' else f"✅ {emoji} Rated", callback_data="rated")]
            ])
        )


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refresh button press - fetch fresh news digest."""
    from .user_storage import get_user_language
    from .translations import t
    
    query = update.callback_query
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Acquire distributed lock
    from .distributed_lock import DistributedLock
    lock = DistributedLock('news_generation', telegram_id, ttl_seconds=300)
    
    if not lock.acquire():
        await query.answer("⏳ Генерирую..." if user_lang == 'ru' else "⏳ Generating...", show_alert=True)
        return
        
    await query.answer("🔄 Обновляю новости..." if user_lang == 'ru' else "🔄 Fetching fresh news...")
    
    # Send a "fetching" message
    loading_text = "⏳ Получаю свежие новости..." if user_lang == 'ru' else "⏳ Fetching fresh news..."
    await query.message.reply_text(loading_text)
    
    try:
        from .scrapers.hackernews import fetch_hackernews
        from .scrapers.techcrunch import fetch_techcrunch
        from .scrapers.ai_blogs import fetch_ai_blogs
        from .scrapers.theverge import fetch_theverge
        from .scrapers.github_trending import fetch_github_trending
        from .summarizer import summarize_news
        
        # Fetch fresh news concurrently
        tasks = []
        tasks.append(fetch_hackernews(12))
        tasks.append(asyncio.to_thread(fetch_techcrunch, 8))
        tasks.append(fetch_ai_blogs(3))
        tasks.append(asyncio.to_thread(fetch_theverge, 5))
        tasks.append(asyncio.to_thread(fetch_github_trending, 5))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_news = []
        for res in results:
            if isinstance(res, list):
                all_news.extend(res)
            elif isinstance(res, Exception):
                print(f"Error fetching news in refresh: {res}")
        
        if not all_news:
            error_text = "❌ Не удалось получить новости." if user_lang == 'ru' else "❌ Could not fetch news."
            await query.message.reply_text(error_text)
            return
        
        digest = await summarize_news(all_news, language=user_lang)
        
        # Generate unique digest ID
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        
        # Store full digest in Firestore for save button access
        try:
            from .user_storage import get_firestore_client
            db = get_firestore_client()
            if db:
                from google.cloud import firestore
                db.collection('digests_temp').document(digest_id).set({
                    'content': digest,
                    'user_id': telegram_id,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'expires_at': datetime.now() + timedelta(hours=24)
                })
        except Exception as e:
            print(f"Error storing digest in refresh: {e}")
        
        # Define button labels based on language
        refresh_label = "🔄 Обновить" if user_lang == 'ru' else "🔄 Refresh"
        save_label = "🔖 Сохранить" if user_lang == 'ru' else "🔖 Save Digest"
        
        # Send the digest with buttons
        keyboard = [
            [
                InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
                InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
                InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
            ],
            [
                InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the digest with buttons (split if needed)
        from .message_utils import split_message
        chunks = split_message(digest)
        
        try:
            for i, chunk in enumerate(chunks):
                # Add buttons only to the last chunk
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
            # Fallback without markdown if parsing fails
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
        error_text = f"❌ Ошибка: {str(e)[:50]}" if user_lang == 'ru' else f"❌ Error: {str(e)[:50]}"
        await query.message.reply_text(error_text)
    finally:
        lock.release()


async def save_digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle save digest button press - extract and save all article URLs from the digest."""
    from .user_storage import get_user_language, save_article, get_firestore_client
    import re
    
    query = update.callback_query
    await query.answer("💾 Сохраняю..." if get_user_language(update.effective_user.id) == 'ru' else "💾 Saving...")
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Extract digest_id from callback_data
    callback_data = query.data
    parts = callback_data.split('_')
    if len(parts) < 3:
        await query.answer("❌ Error: Invalid callback data", show_alert=True)
        return
    
    digest_id = parts[2]
    
    # Fetch full digest from Firestore
    db = get_firestore_client()
    if not db:
        await query.answer("❌ Database unavailable", show_alert=True)
        return
    
    try:
        digest_doc = db.collection('digests_temp').document(digest_id).get()
        if not digest_doc.exists:
            await query.answer("❌ Digest not found" if user_lang != 'ru' else "❌ Дайджест не найден", show_alert=True)
            return
        
        digest_content = digest_doc.to_dict().get('content', '')
        
        # Extract all URLs from the full digest using regex
        url_pattern = r'\[([^\]]+)\]\((https?://[^)]+)\)'
        matches = re.findall(url_pattern, digest_content)
        
        # Also find plain URLs
        plain_url_pattern = r'(?<!\()https?://[^\s\)\]]+'
        plain_urls = re.findall(plain_url_pattern, digest_content)
        
        saved_count = 0
        
        # Save each article found
        for title, url in matches:
            clean_title = title.strip()[:100]
            # Detect source from URL
            source = ''
            if 'techcrunch' in url.lower():
                source = 'TechCrunch'
            elif 'news.ycombinator' in url.lower():
                source = 'Hacker News'
            elif 'theverge' in url.lower():
                source = 'The Verge'
            elif 'github' in url.lower():
                source = 'GitHub'
            elif 'anthropic' in url.lower():
                source = 'Anthropic'
            elif 'deepmind' in url.lower():
                source = 'DeepMind'
            elif 'openai' in url.lower():
                source = 'OpenAI'
            elif 'mistral' in url.lower():
                source = 'Mistral'
            
            if save_article(telegram_id, clean_title, url, source):
                saved_count += 1
        
        # Save plain URLs without titles
        for url in plain_urls:
            if any(url in m[1] for m in matches):
                continue
            title = f"Article {datetime.now().strftime('%Y-%m-%d')}"
            if save_article(telegram_id, title, url, ''):
                saved_count += 1
        
        if saved_count > 0:
            text = f"✅ Сохранено {saved_count} статей! Используй /saved для просмотра." if user_lang == 'ru' else f"✅ Saved {saved_count} articles! Use /saved to view."
            await query.answer(text, show_alert=True)
        else:
            text = "ℹ️ Все статьи уже сохранены или нет ссылок для сохранения." if user_lang == 'ru' else "ℹ️ All articles already saved or no links to save."
            await query.answer(text, show_alert=True)
            
    except Exception as e:
        print(f"Error in save_digest_callback: {e}")
        await query.answer("❌ Ошибка сохранения" if user_lang == 'ru' else "❌ Save error", show_alert=True)


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
    
    # Handle button presses - check for both English and Russian labels
    # News button
    if user_message in ["📰 Get News", "📰 Новости", t('btn_news', 'en'), t('btn_news', 'ru')]:
        await news_command(update, context)
        return
    # Search button
    elif user_message in ["🔍 Search", "🔍 Поиск", t('btn_search', 'en'), t('btn_search', 'ru')]:
        await update.message.reply_text(
            t('search_prompt', user_lang),
            parse_mode='Markdown'
        )
        return
    # Saved button
    elif user_message in ["🔖 Saved", "🔖 Сохранённые", t('btn_saved', 'en'), t('btn_saved', 'ru')]:
        await saved_command(update, context)
        return
    # Status button
    elif user_message in ["📊 Status", "📊 Статус", t('btn_status', 'en'), t('btn_status', 'ru')]:
        await status_command(update, context)
        return
    # Settings button
    elif user_message in ["⚙️ Settings", "⚙️ Настройки", t('btn_settings', 'en'), t('btn_settings', 'ru')]:
        await sources_command(update, context)
        return
    # Language button
    elif user_message in ["🌐 Language", "🌐 Язык", t('btn_language', 'en'), t('btn_language', 'ru')]:
        await language_command(update, context)
        return
    # Schedule button
    elif user_message in ["⏰ Schedule", "⏰ Расписание", t('btn_schedule', 'en'), t('btn_schedule', 'ru')]:
        await schedule_command(update, context)
        return
    # Help button
    elif user_message in ["❓ Help", "❓ Помощь", t('btn_help', 'en'), t('btn_help', 'ru')]:
        await help_command(update, context)
        return
    # Share button
    elif user_message in ["📤 Share", "📤 Поделиться", t('btn_share', 'en'), t('btn_share', 'ru')]:
        await share_command(update, context)
        return
    
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
                    "content": f"""You are a helpful tech news assistant. Users may ask you:
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
        BotCommand("filter", "Filter saved by category"),
        BotCommand("recap", "Weekly saved articles recap"),
        BotCommand("status", "View your settings"),
        BotCommand("language", "Change language"),
        BotCommand("sources", "Toggle news sources"),
        BotCommand("schedule", "Set digest schedule"),
        BotCommand("share", "Share bot with friends"),
        BotCommand("help", "Show help"),
    ]
    
    # Russian commands
    commands_ru = [
        BotCommand("start", "Запустить бота"),
        BotCommand("news", "Получить дайджест новостей"),
        BotCommand("saved", "Сохранённые статьи"),
        BotCommand("search", "Поиск статей"),
        BotCommand("filter", "Фильтр по категориям"),
        BotCommand("recap", "Еженедельная сводка"),
        BotCommand("status", "Настройки"),
        BotCommand("language", "Язык"),
        BotCommand("sources", "Источники новостей"),
        BotCommand("schedule", "Расписание"),
        BotCommand("share", "Поделиться ботом"),
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
    application = (
        Application.builder()
        .token(token)
        .request(request)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("news", news_command))
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
    
    # Add callback query handlers for inline buttons
    application.add_handler(CallbackQueryHandler(toggle_source_callback, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(schedule_callback, pattern='^schedule_'))
    application.add_handler(CallbackQueryHandler(rating_callback, pattern='^rate_'))
    application.add_handler(CallbackQueryHandler(refresh_callback, pattern='^refresh_'))
    application.add_handler(CallbackQueryHandler(save_digest_callback, pattern='^save_digest_'))
    application.add_handler(CallbackQueryHandler(delete_article_callback, pattern='^del_'))
    
    # Add message handler for buttons and Q&A (handles any text that isn't a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Set up bot commands for native Telegram menu (will be called after initialization)
    application.post_init = setup_bot_commands
    
    return application


async def send_digest_to_user(telegram_id: int, digest: str):
    """Send a digest message to a specific user."""
    from telegram import Bot
    from .user_storage import get_user_language
    import hashlib
    
    bot = Bot(token=get_bot_token())
    user_lang = get_user_language(telegram_id)
    
    # Generate digest ID for buttons
    digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
    
    # Define button labels based on language
    refresh_label = "🔄 Обновить" if user_lang == 'ru' else "🔄 Refresh"
    save_label = "🔖 Сохранить" if user_lang == 'ru' else "🔖 Save Digest"
    
    keyboard = [
        [
            InlineKeyboardButton("👍", callback_data=f"rate_up_{digest_id}"),
            InlineKeyboardButton("👎", callback_data=f"rate_down_{digest_id}"),
            InlineKeyboardButton(refresh_label, callback_data="refresh_news"),
        ],
        [
            InlineKeyboardButton(save_label, callback_data=f"save_digest_{digest_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
