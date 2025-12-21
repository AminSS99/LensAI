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
        [KeyboardButton("📰 Get News"), KeyboardButton("⚙️ Settings")],
        [KeyboardButton("📊 Status"), KeyboardButton("❓ Help")]
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
📚 **Tech News Bot Commands**

• /news - Get your personalized news digest right now
• /settime HH:MM - Set daily digest time (e.g., /settime 14:45)
• /sources - View and toggle news sources
• /status - Check your current settings
• /help - Show this help message

💡 **Tips:**
- Use 24-hour format for time (e.g., 14:45, not 2:45 PM)
- Toggle sources on/off with /sources
- News is curated and summarized by AI

Questions? The bot is open source! 🚀
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - fetch and send digest now."""
    from .cache import get_cached_digest, set_cached_digest, get_digest_timestamp, is_digest_cached
    
    telegram_id = update.effective_user.id
    
    # Check cache first
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
    elif user_message == "⚙️ Settings":
        await sources_command(update, context)
        return
    elif user_message == "📊 Status":
        await status_command(update, context)
        return
    elif user_message == "❓ Help":
        await help_command(update, context)
        return
    
    # Otherwise, treat as a question for AI
    from .summarizer import get_client
    
    await update.message.reply_text("🤔 _Thinking..._", parse_mode='Markdown')
    
    try:
        client = get_client()
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system", 
                    "content": """You are a helpful tech news assistant. Users may ask you:
- Questions about tech news, AI developments, or industry trends
- To explain what a news item means
- For more details about a technology or company
- General tech questions

Be concise, informative, and friendly. Use emojis sparingly. 
If the question is about a specific news item, provide context and explain its significance.
Keep responses under 300 words unless more detail is needed."""
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
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(toggle_source_callback, pattern='^toggle_'))
    
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
