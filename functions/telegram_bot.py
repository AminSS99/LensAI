"""
Telegram Bot Module
Handles all Telegram bot interactions and commands.
"""

import os
import re
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
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    from .translations import t
    
    keyboard = [
        [KeyboardButton(t('btn_news', lang)), KeyboardButton(t('btn_search', lang))],
        [KeyboardButton(t('btn_saved', lang)), KeyboardButton(t('btn_status', lang))],
        [KeyboardButton(t('btn_language', lang)), KeyboardButton(t('btn_settings', lang))],
        [KeyboardButton(t('btn_schedule', lang)), KeyboardButton(t('btn_help', lang))]
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,  # Make buttons smaller
        is_persistent=True     # Keep keyboard visible
    )


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
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(user_lang)
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
        try:
            await update.message.reply_text(
                header + cached_digest[:3900],
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception:
            # Fallback without markdown if parsing fails
            await update.message.reply_text(
                header + cached_digest[:3900],
                disable_web_page_preview=True
            )
        return
    
    # Rate limit fresh requests
    allowed, message = check_rate_limit(telegram_id, 'news')
    if not allowed:
        await update.message.reply_text(t('rate_limited', user_lang, seconds=message.split()[-2] if 'seconds' in message else '60'))
        return
    
    # No cache - fetch fresh
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs_sync
    from .summarizer import summarize_news
    
    # Send "typing" indicator with realistic time estimate
    await update.message.reply_text(t('gathering_news', user_lang), parse_mode='Markdown')
    
    try:
        # Get user preferences from database (or use defaults)
        sources = ['hackernews', 'techcrunch', 'ai_blogs']  # Default sources
        try:
            from .database import get_user
            user = get_user(telegram_id)
            if user and user.get('sources'):
                sources = user.get('sources')
        except Exception:
            pass  # Use defaults if database not available
        
        # Fetch news from selected sources
        all_news = []
        
        if 'hackernews' in sources:
            hn_news = fetch_hackernews_sync(15)
            all_news.extend(hn_news)
        
        if 'techcrunch' in sources:
            tc_news = fetch_techcrunch(10)
            all_news.extend(tc_news)
        
        if 'ai_blogs' in sources:
            ai_news = fetch_ai_blogs_sync(3)
            all_news.extend(ai_news)
        
        if not all_news:
            await update.message.reply_text(t('no_news', user_lang))
            return
        
        # Summarize with DeepSeek (in user's language)
        digest = summarize_news(all_news, language=user_lang)
        
        # Cache the digest for 15 minutes
        set_cached_digest(digest, ttl_minutes=15)
        
        # Try to save digest to history (optional)
        try:
            from .database import save_digest
            save_digest(telegram_id, digest)
        except Exception:
            pass  # Skip saving if database not available
        
        # Generate unique digest ID for rating tracking
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        
        # Send digest (split if too long for Telegram)
        # Use try/except to handle Markdown parsing errors
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
        
        if len(digest) > 4000:
            chunks = [digest[i:i+4000] for i in range(0, len(digest), 4000)]
            for i, chunk in enumerate(chunks):
                await send_chunk(chunk, is_last=(i == len(chunks) - 1))
        else:
            await send_chunk(digest, is_last=True)
            
    except Exception as e:
        await update.message.reply_text(t('error_fetching', user_lang, error=str(e)[:100]))


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
    sources = ['hackernews', 'techcrunch', 'ai_blogs']  # Default all enabled
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
    """Handle /saved command - show saved articles."""
    from .user_storage import get_saved_articles, get_user_language
    from .translations import t
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    articles = get_saved_articles(telegram_id, limit=10)
    
    if not articles:
        await update.message.reply_text(t('no_saved', user_lang), parse_mode='Markdown')
        return
    
    message = t('saved_header', user_lang)
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        source = article.get('source', '')
        message += f"{i}. [{title}]({url})"
        if source:
            message += f" _{source}_"
        message += "\n"
    
    message += t('saved_footer', user_lang)
    
    try:
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    except Exception:
        await update.message.reply_text(message, disable_web_page_preview=True)


async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /save command - save an article."""
    from .user_storage import save_article, get_user_language
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
    
    if save_article(telegram_id, title, url):
        await update.message.reply_text(t('article_saved', user_lang))
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
    await query.answer("🔄 Fetching fresh news...")
    
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Send a "fetching" message
    loading_text = "⏳ Получаю свежие новости..." if user_lang == 'ru' else "⏳ Fetching fresh news..."
    await query.message.reply_text(loading_text)
    
    # Fetch fresh news using the same logic as news_command
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs_sync
    from .scrapers.theverge import fetch_theverge
    from .scrapers.github_trending import fetch_github_trending
    from .summarizer import summarize_news
    
    try:
        all_news = []
        all_news.extend(fetch_hackernews_sync(12))
        all_news.extend(fetch_techcrunch(8))
        all_news.extend(fetch_ai_blogs_sync(3))
        all_news.extend(fetch_theverge(5))
        all_news.extend(fetch_github_trending(5))
        
        if not all_news:
            error_text = "❌ Не удалось получить новости." if user_lang == 'ru' else "❌ Could not fetch news."
            await query.message.reply_text(error_text)
            return
        
        digest = summarize_news(all_news, language=user_lang)
        
        # Generate unique digest ID
        import hashlib
        digest_id = hashlib.md5(digest[:100].encode()).hexdigest()[:8]
        
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
        
        try:
            await query.message.reply_text(
                digest,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception:
            await query.message.reply_text(
                digest,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            
    except Exception as e:
        error_text = f"❌ Ошибка: {str(e)[:50]}" if user_lang == 'ru' else f"❌ Error: {str(e)[:50]}"
        await query.message.reply_text(error_text)


async def save_digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle save digest button press - bookmark current digest."""
    from .user_storage import get_user_language, save_article
    
    query = update.callback_query
    telegram_id = update.effective_user.id
    user_lang = get_user_language(telegram_id)
    
    # Get the digest content from the message
    digest_content = query.message.text[:500]  # Save first 500 chars as reference
    
    # Get digest ID from callback data
    data = query.data  # e.g., "save_digest_abc123"
    parts = data.split('_')
    digest_id = parts[2] if len(parts) >= 3 else "digest"
    
    # Save the digest
    from datetime import datetime
    title = f"📰 Digest {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    saved = save_article(telegram_id, title, f"digest://{digest_id}")
    
    if saved:
        text = "✅ Дайджест сохранён! Используй /saved для просмотра." if user_lang == 'ru' else "✅ Digest saved! Use /saved to view."
        await query.answer(text, show_alert=True)
    else:
        text = "ℹ️ Дайджест уже сохранён." if user_lang == 'ru' else "ℹ️ Digest already saved."
        await query.answer(text)


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
    
    # Check if it's a URL to save
    if user_message.startswith('http://') or user_message.startswith('https://'):
        from .user_storage import save_article
        if save_article(telegram_id, user_message[:50], user_message):
            await update.message.reply_text(t('link_saved', user_lang))
        else:
            await update.message.reply_text(t('link_exists', user_lang))
        return
    
    # Otherwise, treat as a question for AI
    from .summarizer import get_client
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
        client = get_client()
        
        response = client.chat.completions.create(
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
        
        if len(answer) > 4000:
            chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for chunk in chunks:
                await send_answer(chunk)
        else:
            await send_answer(answer)
            
    except Exception as e:
        await update.message.reply_text(t('ai_error', user_lang, error=str(e)[:100]))


# ============ BOT SETUP ============

def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    token = get_bot_token()
    
    application = Application.builder().token(token).build()
    
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
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("language", language_command))
    
    # Add callback query handlers for inline buttons
    application.add_handler(CallbackQueryHandler(toggle_source_callback, pattern='^toggle_'))
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(schedule_callback, pattern='^schedule_'))
    application.add_handler(CallbackQueryHandler(rating_callback, pattern='^rate_'))
    application.add_handler(CallbackQueryHandler(refresh_callback, pattern='^refresh_'))
    application.add_handler(CallbackQueryHandler(save_digest_callback, pattern='^save_digest_'))
    
    # Add message handler for buttons and Q&A (handles any text that isn't a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application


async def send_digest_to_user(telegram_id: int, digest: str):
    """Send a digest message to a specific user."""
    from telegram import Bot
    
    bot = Bot(token=get_bot_token())
    
    try:
        if len(digest) > 4000:
            chunks = [digest[i:i+4000] for i in range(0, len(digest), 4000)]
            for chunk in chunks:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text=digest,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        return True
    except Exception as e:
        print(f"Error sending to user {telegram_id}: {e}")
        return False
