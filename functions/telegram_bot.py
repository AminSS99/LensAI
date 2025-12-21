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

def get_main_keyboard():
    """Get the main persistent keyboard with quick action buttons."""
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    
    keyboard = [
        [KeyboardButton("📰 Get News"), KeyboardButton("🔍 Search")],
        [KeyboardButton("🔖 Saved"), KeyboardButton("⚙️ Settings")],
        [KeyboardButton("🌐 Language"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,  # Make buttons smaller
        is_persistent=True     # Keep keyboard visible
    )


# ============ COMMAND HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message."""
    user = update.effective_user
    telegram_id = user.id
    username = user.username or user.first_name
    
    # Try to register user in database (optional - may not work locally)
    try:
        from .database import create_or_update_user
        create_or_update_user(telegram_id, username)
    except Exception as e:
        print(f"Database not available (running locally?): {e}")
    
    welcome_message = f"""
👋 Welcome to **Tech News Bot**, {username}!

I'll keep you updated with the latest tech and AI news from:
• 📰 Hacker News
• 💻 TechCrunch  
• 🤖 AI Company Blogs (OpenAI, Anthropic, Google AI, Mistral)

**Quick Actions:** Use the buttons below ⬇️

**Or type any question** and I'll answer using AI!

Your current schedule: **18:00** daily
Use /settime to change it!
"""
    await update.message.reply_text(
        welcome_message, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
📚 **LensAI Bot Commands**

📰 **News**
• /news - Get your personalized news digest
• /search <topic> - Search news by topic
• /sources - Toggle news sources

🔖 **Saved Articles**
• /save <url> - Save an article
• /saved - View saved articles
• /clear\\_saved - Clear all saved

⚙️ **Settings**
• /settime HH:MM - Set daily digest time
• /language - Change response language
• /status - Check your settings

💬 **Chat**
Just type any question and I'll answer using AI!

💡 **Tips:**
- Send me any URL to save it
- Use buttons below for quick access
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - fetch and send digest now."""
    from .cache import get_cached_digest, set_cached_digest, get_digest_timestamp, is_digest_cached
    from .rate_limiter import check_rate_limit
    
    telegram_id = update.effective_user.id
    
    # Check cache first (no rate limit for cached responses)
    if is_digest_cached():
        cached_digest = get_cached_digest()
        timestamp = get_digest_timestamp()
        
        await update.message.reply_text(
            f"📰 **Cached News Digest**\n_Last updated: {timestamp[:16] if timestamp else 'recently'}_\n\n" + 
            cached_digest[:3900],  # Leave room for header
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    # Rate limit fresh requests
    allowed, message = check_rate_limit(telegram_id, 'news')
    if not allowed:
        await update.message.reply_text(message)
        return
    
    # No cache - fetch fresh
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs_sync
    from .summarizer import summarize_news
    
    # Send "typing" indicator with realistic time estimate
    await update.message.reply_text(
        "🔄 **Gathering fresh news from all sources...**\n\n"
        "⏱️ This usually takes 1-3 minutes. I'll send your digest as soon as it's ready!\n\n"
        "_Fetching from Hacker News, TechCrunch, and AI blogs..._",
        parse_mode='Markdown'
    )
    
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
            await update.message.reply_text("😕 No news found. Please try again later.")
            return
        
        # Summarize with DeepSeek
        digest = summarize_news(all_news)
        
        # Cache the digest for 15 minutes
        set_cached_digest(digest, ttl_minutes=15)
        
        # Try to save digest to history (optional)
        try:
            from .database import save_digest
            save_digest(telegram_id, digest)
        except Exception:
            pass  # Skip saving if database not available
        
        # Send digest (split if too long for Telegram)
        if len(digest) > 4000:
            # Split into chunks
            chunks = [digest[i:i+4000] for i in range(0, len(digest), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await update.message.reply_text(digest, parse_mode='Markdown', disable_web_page_preview=True)
            
    except Exception as e:
        error_msg = f"❌ Error fetching news: {str(e)}"
        await update.message.reply_text(error_msg)


async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settime command - set daily digest time."""
    telegram_id = update.effective_user.id
    
    # Parse time from command arguments
    if not context.args:
        await update.message.reply_text(
            "⏰ Please provide a time in HH:MM format.\n"
            "Example: `/settime 14:45`",
            parse_mode='Markdown'
        )
        return
    
    time_str = context.args[0]
    
    # Validate time format
    time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(time_pattern, time_str):
        await update.message.reply_text(
            "❌ Invalid time format. Please use HH:MM (24-hour format).\n"
            "Examples: 09:00, 14:45, 18:30"
        )
        return
    
    # Normalize to HH:MM format
    parts = time_str.split(':')
    normalized_time = f"{int(parts[0]):02d}:{parts[1]}"
    
    try:
        from .database import create_or_update_user
        create_or_update_user(telegram_id, schedule_time=normalized_time)
        
        await update.message.reply_text(
            f"✅ Daily digest scheduled for **{normalized_time}**!\n\n"
            "You'll receive your personalized tech news at this time every day.",
            parse_mode='Markdown'
        )
    except Exception as e:
        # Database not available - still confirm to user
        await update.message.reply_text(
            f"⚠️ Schedule set to **{normalized_time}** (local mode - requires cloud deployment for scheduling).",
            parse_mode='Markdown'
        )


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sources command - show source management."""
    telegram_id = update.effective_user.id
    
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
        "📰 **Your News Sources**\n\n"
        "Tap to toggle sources on/off:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def toggle_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle source toggle button presses."""
    from .database import toggle_user_source
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
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
        "📰 **Your News Sources**\n\n"
        "Tap to toggle sources on/off:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current settings."""
    telegram_id = update.effective_user.id
    
    # Try to get user from database
    user = None
    try:
        from .database import get_user
        user = get_user(telegram_id)
    except Exception:
        pass  # Database not available
    
    if not user:
        # Show default settings for local mode
        status_text = """
📊 **Your Settings** (Local Mode)

⏰ **Daily Digest Time:** 18:00 (default)
🌍 **Timezone:** Asia/Baku

📰 **Active Sources:**
  • Hacker News
  • TechCrunch
  • AI Blogs

_Running locally - settings saved when deployed to cloud_
"""
        await update.message.reply_text(status_text, parse_mode='Markdown')
        return
    
    sources = user.get('sources', [])
    source_names = {
        'hackernews': 'Hacker News',
        'techcrunch': 'TechCrunch',
        'ai_blogs': 'AI Blogs'
    }
    
    sources_text = '\n'.join([f"  • {source_names.get(s, s)}" for s in sources])
    
    status_text = f"""
📊 **Your Settings**

⏰ **Daily Digest Time:** {user.get('schedule_time', 'Not set')}
🌍 **Timezone:** {user.get('timezone', 'Asia/Baku')}

📰 **Active Sources:**
{sources_text if sources else '  No sources selected'}

Use /settime to change schedule
Use /sources to toggle sources
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')


# ============ SAVED ARTICLES ============

async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /saved command - show saved articles."""
    from .user_storage import get_saved_articles
    
    telegram_id = update.effective_user.id
    articles = get_saved_articles(telegram_id, limit=10)
    
    if not articles:
        await update.message.reply_text(
            "🔖 **No saved articles yet!**\n\n"
            "When reading news, forward any article link to me and I'll save it for you.\n\n"
            "Or use `/save <url>` to save an article.",
            parse_mode='Markdown'
        )
        return
    
    message = "🔖 **Your Saved Articles**\n\n"
    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')[:50]
        url = article.get('url', '')
        source = article.get('source', '')
        message += f"{i}. [{title}]({url})"
        if source:
            message += f" _{source}_"
        message += "\n"
    
    message += "\n_Use /clear\\_saved to delete all_"
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown',
        disable_web_page_preview=True
    )


async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /save command - save an article."""
    from .user_storage import save_article
    
    telegram_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "📌 **How to save articles:**\n\n"
            "1. `/save <url>` - Save directly\n"
            "2. Forward me a message with a link\n"
            "3. Reply to a news digest with `/save`",
            parse_mode='Markdown'
        )
        return
    
    url = context.args[0]
    title = ' '.join(context.args[1:]) if len(context.args) > 1 else url[:50]
    
    if save_article(telegram_id, title, url):
        await update.message.reply_text("✅ Article saved! View with /saved")
    else:
        await update.message.reply_text("ℹ️ Article already saved!")


async def clear_saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_saved command."""
    from .user_storage import clear_saved_articles
    
    telegram_id = update.effective_user.id
    clear_saved_articles(telegram_id)
    await update.message.reply_text("🗑️ All saved articles cleared!")


# ============ SEARCH ============

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command - search news by topic."""
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .user_storage import add_search_history
    from .rate_limiter import check_rate_limit
    
    telegram_id = update.effective_user.id
    
    # Rate limit check
    allowed, message = check_rate_limit(telegram_id, 'search')
    if not allowed:
        await update.message.reply_text(message)
        return
    
    if not context.args:
        await update.message.reply_text(
            "🔍 **Search News**\n\n"
            "Usage: `/search <topic>`\n\n"
            "Examples:\n"
            "• `/search GPT-5`\n"
            "• `/search Apple`\n"
            "• `/search machine learning`",
            parse_mode='Markdown'
        )
        return
    
    query = ' '.join(context.args).lower()
    add_search_history(telegram_id, query)
    
    await update.message.reply_text(f"🔍 Searching for **{query}**...", parse_mode='Markdown')
    
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
                f"😕 No articles found for **{query}**.\n\nTry a different search term!",
                parse_mode='Markdown'
            )
            return
        
        # Format results
        message = f"🔍 **Results for '{query}'** ({len(results)} found)\n\n"
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
        await update.message.reply_text(f"❌ Search error: {str(e)}")


# ============ LANGUAGE ============

LANGUAGES = {
    'en': '🇬🇧 English',
    'ru': '🇷🇺 Русский',
    'az': '🇦🇿 Azərbaycan'
}

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command - change language."""
    from .user_storage import get_user_language
    
    telegram_id = update.effective_user.id
    current_lang = get_user_language(telegram_id)
    
    keyboard = []
    for code, name in LANGUAGES.items():
        check = "✓ " if code == current_lang else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"lang_{code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 **Select Language**\n\n"
        "Choose your preferred language for summaries:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback."""
    from .user_storage import set_user_language
    
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    lang_code = query.data.replace('lang_', '')
    
    set_user_language(telegram_id, lang_code)
    
    lang_name = LANGUAGES.get(lang_code, lang_code)
    await query.edit_message_text(
        f"✅ Language set to **{lang_name}**!\n\n"
        "Future summaries will be in this language.",
        parse_mode='Markdown'
    )


# ============ Q&A HANDLER ============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message - button presses or questions for DeepSeek."""
    user_message = update.message.text
    
    # Skip if message is too short
    if not user_message or len(user_message) < 2:
        return
    
    # Handle button presses
    if user_message == "📰 Get News":
        await news_command(update, context)
        return
    elif user_message == "🔍 Search":
        await update.message.reply_text(
            "🔍 **Search News**\n\nType `/search <topic>`\n\nExample: `/search GPT-5`",
            parse_mode='Markdown'
        )
        return
    elif user_message == "🔖 Saved":
        await saved_command(update, context)
        return
    elif user_message == "⚙️ Settings":
        await sources_command(update, context)
        return
    elif user_message == "🌐 Language":
        await language_command(update, context)
        return
    elif user_message == "❓ Help":
        await help_command(update, context)
        return
    
    # Check if it's a URL to save
    if user_message.startswith('http://') or user_message.startswith('https://'):
        from .user_storage import save_article
        telegram_id = update.effective_user.id
        if save_article(telegram_id, user_message[:50], user_message):
            await update.message.reply_text("✅ Link saved! View with /saved")
        else:
            await update.message.reply_text("ℹ️ Link already saved!")
        return
    
    # Otherwise, treat as a question for AI
    from .summarizer import get_client
    from .user_storage import get_user_language
    from .rate_limiter import check_rate_limit
    
    telegram_id = update.effective_user.id
    
    # Rate limit AI chat
    allowed, message = check_rate_limit(telegram_id, 'ai_chat')
    if not allowed:
        await update.message.reply_text(message)
        return
    
    user_lang = get_user_language(telegram_id)
    
    await update.message.reply_text("🤔 _Thinking..._", parse_mode='Markdown')
    
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
        
        # Send answer (split if too long)
        if len(answer) > 4000:
            chunks = [answer[i:i+4000] for i in range(0, len(answer), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await update.message.reply_text(answer, parse_mode='Markdown', disable_web_page_preview=True)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Sorry, I couldn't process that: {str(e)}")


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
