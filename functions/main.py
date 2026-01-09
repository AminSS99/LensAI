"""
Main Entry Point for Cloud Functions
Contains all HTTP and scheduled function handlers.
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
import functions_framework
from flask import Request


# ============ WEBHOOK HANDLER FOR TELEGRAM ============

@functions_framework.http
def telegram_webhook(request: Request):
    """
    HTTP Cloud Function for Telegram webhook.
    Processes updates synchronously with timeout protection.
    
    IMPORTANT: Always returns 200 OK to prevent Telegram retries,
    even if processing fails or times out.
    """
    from telegram import Update
    from .telegram_bot import create_bot_application
    
    if request.method != 'POST':
        return 'OK', 200
    
    try:
        # Parse the incoming update
        update_data = request.get_json()
        
        if not update_data:
            return 'No data', 400
        
        # Create bot application and process update synchronously
        application = create_bot_application()
        
        async def process() -> None:
            try:
                # Initialize with timeout
                print("Initializing bot application...")
                await asyncio.wait_for(
                    application.initialize(),
                    timeout=10.0
                )
                print("Bot initialized successfully")
                
                update = Update.de_json(update_data, application.bot)
                print(f"Processing update from user {update.effective_user.id if update.effective_user else 'unknown'}")
                
                # Process with timeout (120s to allow for slow AI summarization)
                await asyncio.wait_for(
                    application.process_update(update),
                    timeout=120.0
                )
                print("Update processed successfully")
                
            except asyncio.TimeoutError:
                print(f"⚠️ Update processing timed out")
                traceback.print_exc()
            except Exception as e:
                print(f"❌ Error processing update: {e}")
                traceback.print_exc()
            finally:
                try:
                    print("Shutting down bot application...")
                    await asyncio.wait_for(
                        application.shutdown(),
                        timeout=5.0
                    )
                    print("Bot shutdown complete")
                except Exception as e:
                    print(f"Error during shutdown: {e}")
        
        asyncio.run(process())
        
        # Always return 200 OK to Telegram (even if processing failed)
        # This prevents infinite retries from Telegram
        return 'OK', 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        traceback.print_exc()
        return 'OK', 200  # Return OK to prevent retries


# ============ SCHEDULED DIGEST FUNCTION ============

async def process_scheduled_digest(target_time: str = None) -> dict:
    """
    Core logic for processing scheduled digests.
    Can be called by Cloud Scheduler or local JobQueue.
    
    Args:
        target_time: Optional time string HH:MM. If None, current Baku time is used.
    """
    from .database import get_users_for_time, save_digest
    from .telegram_bot import send_digest_to_user
    from .scrapers.hackernews import fetch_hackernews
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs
    from .scrapers.theverge import fetch_theverge
    from .scrapers.github_trending import fetch_github_trending
    from .summarizer import summarize_news
    
    # Get current time in HH:MM format (Baku timezone - UTC+4)
    from datetime import timezone, timedelta
    baku_tz = timezone(timedelta(hours=4))
    
    if target_time:
        current_time = target_time
    else:
        current_time = datetime.now(baku_tz).strftime("%H:00")
    
    print(f"Running scheduled digest for time: {current_time}")
    
    users = get_users_for_time(current_time)
    
    if not users:
        return {'message': f'No users scheduled for {current_time}', 'sent': 0}
    
    # Fetch news from all sources concurrently
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
            print(f"Error fetching news: {res}")
    
    if not all_news:
        return {'message': 'No news available', 'sent': 0}
    
    # Import user language function
    from .user_storage import get_user_language
    
    # Group users by language
    users_by_lang = {}
    for user in users:
        telegram_id = user.get('telegram_id')
        if telegram_id:
            lang = get_user_language(telegram_id)
            if lang not in users_by_lang:
                users_by_lang[lang] = []
            users_by_lang[lang].append(user)
    
    # Generate digests for each language (cache to avoid duplicate API calls)
    digests_by_lang = {}
    for lang in users_by_lang.keys():
        print(f"Generating digest for language: {lang}")
        digests_by_lang[lang] = await summarize_news(all_news, language=lang)
    
    # Send to all scheduled users with their language-specific digest
    sent_count = 0
    errors = []
    
    for lang, lang_users in users_by_lang.items():
        digest = digests_by_lang[lang]
        for user in lang_users:
            telegram_id = user.get('telegram_id')
            try:
                if telegram_id:
                    success = await send_digest_to_user(telegram_id, digest)
                    if success:
                        save_digest(telegram_id, digest)
                        sent_count += 1
                    else:
                        errors.append(telegram_id)
            except Exception as e:
                print(f"Error sending to {telegram_id}: {e}")
                errors.append(telegram_id)
                
    return {
        'message': f'Digest sent for {current_time}',
        'sent': sent_count,
        'total_users': len(users),
        'errors': errors
    }


@functions_framework.http
def scheduled_digest(request: Request):
    """
    HTTP Cloud Function triggered by Cloud Scheduler.
    Sends digests to users scheduled for the current time.
    """
    try:
        # Check for manual time override
        target_time = None
        if request.args.get('time'):
            target_time = request.args.get('time')
            
        result = asyncio.run(process_scheduled_digest(target_time))
        return json.dumps(result), 200
        
    except Exception as e:
        print(f"Scheduled digest error: {e}")
        return json.dumps({'error': str(e)}), 500


# ============ ON-DEMAND NEWS FETCH FUNCTION ============

@functions_framework.http
def fetch_news(request: Request):
    """
    HTTP Cloud Function to fetch and return news.
    Useful for testing or API access.
    """
    from .scrapers.hackernews import fetch_hackernews
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs
    from .scrapers.theverge import fetch_theverge
    from .scrapers.github_trending import fetch_github_trending
    from .summarizer import summarize_news
    
    try:
        sources_arg = request.args.get('sources', 'all').split(',')
        summarize = request.args.get('summarize', 'true').lower() == 'true'
        
        async def fetch_async():
            tasks = []
            
            if 'all' in sources_arg or 'hackernews' in sources_arg:
                tasks.append(fetch_hackernews(12))
            
            if 'all' in sources_arg or 'techcrunch' in sources_arg:
                tasks.append(asyncio.to_thread(fetch_techcrunch, 8))
            
            if 'all' in sources_arg or 'ai_blogs' in sources_arg:
                tasks.append(fetch_ai_blogs(3))
            
            if 'all' in sources_arg or 'theverge' in sources_arg:
                tasks.append(asyncio.to_thread(fetch_theverge, 5))
            
            if 'all' in sources_arg or 'github' in sources_arg:
                tasks.append(asyncio.to_thread(fetch_github_trending, 5))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_news = []
            for res in results:
                if isinstance(res, list):
                    all_news.extend(res)
                elif isinstance(res, Exception):
                    # Log error but continue
                    print(f"Error fetching source: {res}")
            
            if summarize and all_news:
                digest = await summarize_news(all_news)
                return {
                    'digest': digest,
                    'article_count': len(all_news)
                }
            else:
                return {
                    'articles': all_news,
                    'count': len(all_news)
                }

        result = asyncio.run(fetch_async())
        return json.dumps(result), 200
            
    except Exception as e:
        return json.dumps({'error': str(e)}), 500


# ============ HEALTH CHECK ============

@functions_framework.http
def health(request: Request):
    """Simple health check endpoint."""
    return json.dumps({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
