"""
Script to remove old keyboard buttons from all users.
Sends a simple message with ReplyKeyboardRemove to clear cached keyboards.
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


CLEANUP_MESSAGES = {
    'en': "✨ **Interface Updated!**\n\nWe've cleaned up the interface. Use the **Menu** button (≡) at the bottom left to access all commands.",
    'ru': "✨ **Интерфейс обновлён!**\n\nМы обновили интерфейс. Используйте кнопку **Меню** (≡) внизу слева для доступа ко всем командам."
}


async def remove_keyboards():
    """Send message with ReplyKeyboardRemove to all users."""
    from telegram import Bot, ReplyKeyboardRemove
    from functions.database import get_all_active_users
    from functions.user_storage import get_user_language
    from functions.telegram_bot import get_bot_token
    
    print("=" * 50)
    print("  Keyboard Cleanup Script")
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
    
    # Create bot instance
    bot = Bot(token=get_bot_token())
    
    # Send cleanup message to all users
    print("\n📤 Sending keyboard cleanup messages...")
    sent_count = 0
    errors = []
    
    for user in users:
        telegram_id = user.get('telegram_id')
        username = user.get('username', 'Unknown')
        
        if not telegram_id:
            continue
            
        try:
            lang = get_user_language(telegram_id)
            message = CLEANUP_MESSAGES.get(lang, CLEANUP_MESSAGES['en'])
            
            print(f"   Sending to {username} ({telegram_id}) [{lang}]...", end=" ")
            
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()  # This removes the keyboard!
            )
            
            print("✅")
            sent_count += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            errors.append(telegram_id)
    
    # Summary
    print("\n" + "=" * 50)
    print(f"  ✅ Successfully sent: {sent_count}/{len(users)}")
    if errors:
        print(f"  ❌ Errors: {len(errors)} users")
    print("=" * 50)


if __name__ == "__main__":
    print("\n⚠️  This script will remove old keyboard buttons for ALL users.")
    print("    Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        asyncio.run(remove_keyboards())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
