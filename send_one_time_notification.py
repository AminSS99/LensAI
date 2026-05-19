"""
One-Time Notification Script
Sends apology message + weekly news digest to ALL active users.
Run this script ONCE to notify users about bot downtime.
"""

import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add functions directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Localized apology messages with explanation
APOLOGY_MESSAGES = {
    'en': """🔔 **Important Notice from LensAI**

We sincerely apologize! Our bot has been unavailable for the past 10 days.

🔧 **What happened?**
We experienced a critical infrastructure issue — our cloud billing account was suspended, which caused all bot services to stop responding. We failed to catch this immediately and deeply regret the disruption.

We've now resolved the underlying issue and restored full service. We are also adding better monitoring to ensure this never happens again.

📰 **Here's your tech news catch-up — everything you may have missed:**

""",
    'ru': """🔔 **Важное уведомление от LensAI**

Приносим глубочайшие извинения! Наш бот был недоступен последние 10 дней.

🔧 **Что произошло?**
У нас возникла критическая проблема с инфраструктурой — наш облачный биллинговый аккаунт был приостановлен, из-за чего все сервисы бота перестали работать. К сожалению, мы не сразу обнаружили эту проблему, и приносим извинения за доставленные неудобства.

Мы уже устранили причину и полностью восстановили работу бота. Также мы внедряем улучшенный мониторинг, чтобы подобное больше не повторилось.

📰 **Вот ваша сводка технологических новостей — всё, что вы могли пропустить:**

"""
}



async def send_one_time_notification():
    """Send one-time notification to all active users."""
    from functions.database import get_all_active_users
    from functions.user_storage import get_user_language
    from functions.telegram_bot import send_digest_to_user
    from functions.scrapers.hackernews import fetch_hackernews
    from functions.scrapers.techcrunch import fetch_techcrunch
    from functions.scrapers.ai_blogs import fetch_ai_blogs
    from functions.scrapers.theverge import fetch_theverge
    from functions.scrapers.github_trending import fetch_github_trending
    from functions.summarizer import summarize_news
    
    print("=" * 50)
    print("  One-Time Notification Script")
    print(f"  Time: {datetime.now(timezone(timedelta(hours=4))).strftime('%Y-%m-%d %H:%M')} (Baku)")
    print("=" * 50)
    
    # Get all active users
    print("\n📋 Fetching all active users...")
    try:
        users = get_all_active_users()
        print(f"   Found {len(users)} active users")
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        return
    
    if not users:
        print("⚠️ No active users found!")
        return
    
    # Fetch news from all sources
    print("\n📰 Fetching news from all sources...")
    tasks = []
    tasks.append(fetch_hackernews(15))
    tasks.append(asyncio.to_thread(fetch_techcrunch, 10))
    tasks.append(fetch_ai_blogs(5))
    tasks.append(asyncio.to_thread(fetch_theverge, 8))
    tasks.append(asyncio.to_thread(fetch_github_trending, 8))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_news = []
    for res in results:
        if isinstance(res, list):
            all_news.extend(res)
        elif isinstance(res, Exception):
            print(f"   ⚠️ Error fetching source: {res}")
    
    print(f"   Fetched {len(all_news)} articles total")
    
    if not all_news:
        print("❌ No news available!")
        return
    
    # Group users by language
    users_by_lang = {}
    for user in users:
        telegram_id = user.get('telegram_id')
        if telegram_id:
            lang = get_user_language(telegram_id)
            if lang not in users_by_lang:
                users_by_lang[lang] = []
            users_by_lang[lang].append(user)
    
    print(f"\n🌐 Users by language:")
    for lang, lang_users in users_by_lang.items():
        print(f"   {lang}: {len(lang_users)} users")
    
    # Generate digest for each language
    print("\n🤖 Generating digests...")
    digests_by_lang = {}
    for lang in users_by_lang.keys():
        print(f"   Generating {lang} digest...")
        digest = await summarize_news(all_news, language=lang)
        # Prepend apology message
        apology = APOLOGY_MESSAGES.get(lang, APOLOGY_MESSAGES['en'])
        digests_by_lang[lang] = apology + digest
        print(f"   ✅ {lang} digest ready")
    
    # Send to all users
    print("\n📤 Sending notifications...")
    sent_count = 0
    errors = []
    
    for lang, lang_users in users_by_lang.items():
        digest = digests_by_lang[lang]
        for user in lang_users:
            telegram_id = user.get('telegram_id')
            username = user.get('username', 'Unknown')
            
            try:
                print(f"   Sending to {username} ({telegram_id}) [{lang}]...", end=" ")
                success = await send_digest_to_user(telegram_id, digest)
                if success:
                    print("✅")
                    sent_count += 1
                else:
                    print("❌")
                    errors.append(telegram_id)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                errors.append(telegram_id)
    
    # Summary
    print("\n" + "=" * 50)
    print(f"  ✅ Successfully sent: {sent_count}/{len(users)}")
    if errors:
        print(f"  ❌ Errors: {len(errors)} users")
        print(f"     Failed IDs: {errors}")
    print("=" * 50)


if __name__ == "__main__":
    print("\n⚠️  This script will send a one-time notification to ALL users.")
    print("    Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        asyncio.run(send_one_time_notification())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
