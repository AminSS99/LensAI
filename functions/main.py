"""
Main Entry Point for Cloud Functions
Contains all HTTP and scheduled function handlers.
"""

import os
import json
import asyncio
from datetime import datetime
import functions_framework
from flask import Request


# ============ WEBHOOK HANDLER FOR TELEGRAM ============

@functions_framework.http
def telegram_webhook(request: Request):
    """
    HTTP Cloud Function for Telegram webhook.
    Receives updates from Telegram and processes them.
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
        
        # Create bot application and process update
        application = create_bot_application()
        
        # Run async processing
        async def process():
            await application.initialize()
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update)
            await application.shutdown()
        
        asyncio.run(process())
        
        return 'OK', 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return str(e), 500


# ============ SCHEDULED DIGEST FUNCTION ============

@functions_framework.http
def scheduled_digest(request: Request):
    """
    HTTP Cloud Function triggered by Cloud Scheduler.
    Sends digests to users scheduled for the current time.
    """
    from .database import get_users_for_time, save_digest
    from .telegram_bot import send_digest_to_user
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs_sync
    from .summarizer import summarize_news
    
    # Get current time in HH:MM format
    # Note: You might need to adjust for timezone
    current_time = datetime.utcnow().strftime("%H:%M")
    
    # For testing, allow time override via query param
    if request.args.get('time'):
        current_time = request.args.get('time')
    
    print(f"Running scheduled digest for time: {current_time}")
    
    try:
        # Get users scheduled for this time
        users = get_users_for_time(current_time)
        
        if not users:
            return json.dumps({'message': f'No users scheduled for {current_time}', 'sent': 0}), 200
        
        # Fetch news once for all users
        all_news = []
        all_news.extend(fetch_hackernews_sync(15))
        all_news.extend(fetch_techcrunch(10))
        all_news.extend(fetch_ai_blogs_sync(3))
        
        if not all_news:
            return json.dumps({'message': 'No news available', 'sent': 0}), 200
        
        # Generate digest
        digest = summarize_news(all_news)
        
        # Send to all scheduled users
        sent_count = 0
        errors = []
        
        async def send_all():
            nonlocal sent_count
            for user in users:
                telegram_id = user.get('telegram_id')
                if telegram_id:
                    success = await send_digest_to_user(telegram_id, digest)
                    if success:
                        save_digest(telegram_id, digest)
                        sent_count += 1
                    else:
                        errors.append(telegram_id)
        
        asyncio.run(send_all())
        
        result = {
            'message': f'Digest sent for {current_time}',
            'sent': sent_count,
            'total_users': len(users),
            'errors': errors
        }
        
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
    from .scrapers.hackernews import fetch_hackernews_sync
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs_sync
    from .summarizer import summarize_news
    
    try:
        sources = request.args.get('sources', 'all').split(',')
        summarize = request.args.get('summarize', 'true').lower() == 'true'
        
        all_news = []
        
        if 'all' in sources or 'hackernews' in sources:
            all_news.extend(fetch_hackernews_sync(15))
        
        if 'all' in sources or 'techcrunch' in sources:
            all_news.extend(fetch_techcrunch(10))
        
        if 'all' in sources or 'ai_blogs' in sources:
            all_news.extend(fetch_ai_blogs_sync(3))
        
        if summarize and all_news:
            digest = summarize_news(all_news)
            return json.dumps({
                'digest': digest,
                'article_count': len(all_news)
            }), 200
        else:
            return json.dumps({
                'articles': all_news,
                'count': len(all_news)
            }), 200
            
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
