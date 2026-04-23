"""
Main Entry Point for Cloud Functions
Contains all HTTP and scheduled function handlers.
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
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
    
    secret_token = os.environ.get('TELEGRAM_WEBHOOK_SECRET_TOKEN')
    if secret_token:
        import hmac
        header_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if not header_token or not hmac.compare_digest(header_token, secret_token):
            return 'Forbidden', 403

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
                print("WARNING: Update processing timed out")
                traceback.print_exc()
            except Exception as e:
                print(f"ERROR: Error processing update: {e}")
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

def _is_within_quiet_hours(local_dt: datetime, quiet_hours: dict) -> bool:
    """Check if local datetime falls inside configured quiet hours."""
    if not quiet_hours or not isinstance(quiet_hours, dict):
        return False

    start = quiet_hours.get("start")
    end = quiet_hours.get("end")
    if not start or not end:
        return False

    try:
        start_h, start_m = map(int, start.split(":"))
        end_h, end_m = map(int, end.split(":"))
    except Exception:
        return False

    now_minutes = local_dt.hour * 60 + local_dt.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    # Same start/end means disabled.
    if start_minutes == end_minutes:
        return False

    # Handles both normal and overnight ranges.
    if start_minutes < end_minutes:
        return start_minutes <= now_minutes < end_minutes
    return now_minutes >= start_minutes or now_minutes < end_minutes


def _is_user_due_now(user: dict, now_utc: datetime) -> bool:
    """
    Decide whether user should receive digest now (timezone + quiet-hours aware).
    """
    if not user.get("is_active", False):
        return False

    schedule_time = user.get("schedule_time")
    if not schedule_time:
        return False

    timezone_name = user.get("timezone") or "Asia/Baku"
    try:
        user_tz = ZoneInfo(timezone_name)
    except Exception:
        user_tz = ZoneInfo("UTC")

    local_now = now_utc.astimezone(user_tz)
    local_hhmm = local_now.strftime("%H:%M")
    local_hh00 = local_now.strftime("%H:00")

    if schedule_time not in {local_hhmm, local_hh00}:
        return False

    if _is_within_quiet_hours(local_now, user.get("quiet_hours")):
        return False

    return True

async def process_scheduled_digest(target_time: str = None) -> dict:
    """
    Core logic for processing scheduled digests.
    Can be called by Cloud Scheduler or local JobQueue.
    
    Args:
        target_time: Optional time string HH:MM. If None, current Baku time is used.
    """
    from .database import get_users_for_time, get_all_active_users, save_digest
    from .telegram_bot import send_digest_to_user
    from .scrapers.hackernews import fetch_hackernews
    from .scrapers.techcrunch import fetch_techcrunch
    from .scrapers.ai_blogs import fetch_ai_blogs
    from .scrapers.theverge import fetch_theverge
    from .scrapers.github_trending import fetch_github_trending
    from .scrapers.producthunt import fetch_producthunt
    from .summarizer import summarize_news
    
    if target_time:
        # Manual override mode: keep legacy behavior.
        current_time = target_time
        users = get_users_for_time(current_time)
    else:
        # Automatic mode: timezone-aware per-user scheduling.
        from datetime import timezone as dt_timezone
        now_utc = datetime.now(dt_timezone.utc)
        current_time = now_utc.strftime("%H:00")
        active_users = get_all_active_users()
        users = [u for u in active_users if _is_user_due_now(u, now_utc)]
    
    print(f"Running scheduled digest for time: {current_time}")
    
    if not users:
        return {'message': f'No users scheduled for {current_time}', 'sent': 0}
    
    # Fetch news from all sources concurrently
    tasks = []
    tasks.append(fetch_hackernews(12))
    tasks.append(asyncio.to_thread(fetch_techcrunch, 8))
    tasks.append(fetch_ai_blogs(3))
    tasks.append(asyncio.to_thread(fetch_theverge, 5))
    tasks.append(asyncio.to_thread(fetch_github_trending, 5))
    tasks.append(asyncio.to_thread(fetch_producthunt, 8))
    
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
        digests_by_lang[lang] = await summarize_news(all_news, max_items=18, language=lang)
    
    # Send to all scheduled users with their language-specific digest
    sent_count = 0
    errors = []
    
    for lang, lang_users in users_by_lang.items():
        digest = digests_by_lang[lang]
        for user in lang_users:
            telegram_id = user.get('telegram_id')
            try:
                if telegram_id:
                    success = await send_digest_to_user(telegram_id, digest, articles_meta=all_news[:20])
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


async def process_weekly_trend_alerts() -> dict:
    """Send weekly trend alerts to opted-in users."""
    from telegram import Bot
    from .database import get_all_active_users
    from .trend_analysis import calculate_weekly_trends, format_trends_message
    from .telegram_bot import get_bot_token
    from .user_storage import get_user_preferences, get_user_language

    trends = calculate_weekly_trends()
    if not trends:
        return {"message": "No trend data available", "sent": 0}

    rising_changes = [d.get("change", 0.0) for d in trends.values() if d.get("trend") == "rising"]
    max_rising_change = max(rising_changes) if rising_changes else 0.0

    users = get_all_active_users()
    if not users:
        return {"message": "No active users", "sent": 0}

    bot = Bot(token=get_bot_token())
    sent = 0
    skipped = 0
    errors = []

    for user in users:
        telegram_id = user.get("telegram_id")
        if not telegram_id:
            continue

        prefs = get_user_preferences(telegram_id) or {}
        enabled = bool(prefs.get("trend_alerts_enabled", False))
        threshold = int(prefs.get("trend_alert_threshold", 30))

        if not enabled:
            skipped += 1
            continue

        if max_rising_change < threshold:
            skipped += 1
            continue

        user_lang = get_user_language(telegram_id)
        message = format_trends_message(user_lang)

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception as e:
            errors.append({"telegram_id": telegram_id, "error": str(e)})

    return {
        "message": "Weekly trend alerts processed",
        "sent": sent,
        "skipped": skipped,
        "max_rising_change": round(max_rising_change, 1),
        "errors": errors[:25],
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


@functions_framework.http
def weekly_trend_alerts(request: Request):
    """
    HTTP Cloud Function for weekly trend alerts.
    Intended to be called by Cloud Scheduler once per week.
    """
    try:
        result = asyncio.run(process_weekly_trend_alerts())
        return json.dumps(result), 200
    except Exception as e:
        print(f"Weekly trend alert error: {e}")
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
    from .scrapers.producthunt import fetch_producthunt
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

            if 'all' in sources_arg or 'producthunt' in sources_arg:
                tasks.append(asyncio.to_thread(fetch_producthunt, 5))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_news = []
            for res in results:
                if isinstance(res, list):
                    all_news.extend(res)
                elif isinstance(res, Exception):
                    # Log error but continue
                    print(f"Error fetching source: {res}")
            
            if not all_news:
                return {
                    'articles': [],
                    'count': 0
                }

            # Shuffle and limit items for both summarized and non-summarized output
            import random
            random.shuffle(all_news)
            processed_news = all_news[:30] # Limit to 30 items for consistency
            
            if summarize:
                digest = await summarize_news(processed_news, max_items=18)
                return {
                    'digest': digest,
                    'article_count': len(processed_news)
                }
            else:
                return {
                    'articles': processed_news,
                    'count': len(processed_news)
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
