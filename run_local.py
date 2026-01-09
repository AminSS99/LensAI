"""
Local Development Runner
Run the Telegram bot in polling mode for local testing.
"""

import os
import sys
import asyncio
from datetime import datetime, time, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add functions directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_env_vars():
    """Check that required environment variables are set."""
    required = ['TELEGRAM_BOT_TOKEN', 'DEEPSEEK_API_KEY']
    missing = [var for var in required if not os.environ.get(var)]

    if missing:
        print("❌ Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    print("✅ Environment variables loaded")


def test_scrapers():
    """Quick test of all scrapers."""
    print("\n📰 Testing scrapers...")

    try:
        from functions.scrapers.hackernews import fetch_hackernews_sync
        hn = fetch_hackernews_sync(3)
        print(f"  ✅ Hacker News: {len(hn)} articles")
    except Exception as e:
        print(f"  ❌ Hacker News: {e}")

    try:
        from functions.scrapers.techcrunch import fetch_techcrunch
        tc = fetch_techcrunch(3)
        print(f"  ✅ TechCrunch: {len(tc)} articles")
    except Exception as e:
        print(f"  ❌ TechCrunch: {e}")

    try:
        from functions.scrapers.ai_blogs import fetch_ai_blogs_sync
        ai = fetch_ai_blogs_sync(2)
        print(f"  ✅ AI Blogs: {len(ai)} articles")
    except Exception as e:
        print(f"  ❌ AI Blogs: {e}")


def run_bot():
    """Run the bot in polling mode with local scheduler."""
    from functions.telegram_bot import create_bot_application
    from functions.main import process_scheduled_digest
    
    print("\n🤖 Starting Telegram bot in polling mode w/ Schedule...")
    print("Press Ctrl+C to stop\n")

    application = create_bot_application()
    
    # Define scheduled job callback
    async def check_schedule(context):
        """Check for scheduled digests every minute."""
        # Get current time in Baku timezone
        baku_tz = timezone(timedelta(hours=4))
        now = datetime.now(baku_tz)
        
        # Only run at top of the hour
        if now.minute == 0:
            current_time_str = now.strftime("%H:00")
            print(f"⏰ Top of hour ({current_time_str}) - checking schedule...")
            
            try:
                # Call the shared digest processing logic
                result = await process_scheduled_digest(current_time_str)
                if result.get('sent', 0) > 0:
                    print(f"✅ Sent {result['sent']} digests")
                elif result.get('message'):
                    print(f"ℹ️ {result['message']}")
            except Exception as e:
                print(f"❌ Scheduled digest error: {e}")
    
    # Add recurring job to the job queue
    if application.job_queue:
        # Check every 60 seconds
        application.job_queue.run_repeating(check_schedule, interval=60, first=10)
        print("✅ Local scheduler activated (checks every minute)")
    else:
        print("⚠️ Warning: JobQueue not available")

    application.run_polling(allowed_updates=['message', 'callback_query'])


if __name__ == "__main__":
    print("=" * 50)
    print("  Tech News AI Workflow - Local Development")
    print("=" * 50)

    check_env_vars()

    # Optional: test scrapers first
    if '--test-scrapers' in sys.argv:
        test_scrapers()
        print()
    
    # Run the bot
    run_bot()
