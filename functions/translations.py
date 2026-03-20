"""
Translations Module
Bot message translations for different languages.
"""

# Message translations
MESSAGES = {
    'en': {
        # Existing keys
        'gathering_news': "🔄 **Gathering fresh news from all sources...**\n\n⏱️ This usually takes 1-3 minutes. I'll send your digest as soon as it's ready!\n\n_Fetching from Hacker News, TechCrunch, and AI blogs..._",
        'cached_news': "📰 **Tech News**\n_Last updated: {timestamp}_\n\n",
        'no_news': "😕 No news found. Please try again later.",
        'error_fetching': "❌ Error fetching news: {error}",
        'thinking': "🤔 _Thinking..._",
        'rate_limited': "⏳ Rate limit reached. Please wait {seconds} seconds.",
        'link_saved': "✅ Link saved! View with /saved",
        'link_exists': "ℹ️ Link already saved!",
        'language_set': "✅ Language set to **{language_name}**!\n\nFuture summaries will be in this language.",
        'search_prompt': "🔍 **Search News**\n\nType `/search <topic>`\n\nExample: `/search GPT-5`",
        'search_history_header': "🕒 *Recent searches:*",
        'searching': "🔍 Searching for **{query}**...",
        'no_results': "😕 No articles found for **{query}**.\n\nTry a different search term!",
        'search_results': "🔍 **Results for '{query}'** ({count} found)\n\n",
        'schedule_prompt': "⏰ **Set Daily Digest Time**\n\nUse `/settime HH:MM` to schedule your daily news digest.\n\nExamples:\n• `/settime 09:00` - Morning digest\n• `/settime 18:30` - Evening digest\n• `/settime 12:00` - Lunch digest",
        'no_saved': "🔖 **No saved articles yet!**\n\nWhen reading news, forward any article link to me and I'll save it for you.\n\nOr use `/save <url>` to save an article.",
        'saved_header': "🔖 **Your Saved Articles**\n\n",
        'saved_footer': "\n_Use /clear\\_saved to delete all_",
        'article_saved': "✅ Article saved! View with /saved",
        'article_exists': "ℹ️ Article already saved!",
        'cleared_saved': "🗑️ All saved articles cleared!",
        'export_empty': "🔖 **No saved articles to export yet!**\n\nSave an article first, then try `/export` again.",
        'export_caption': "📚 **Saved Articles Export**\n\nExported {count} saved articles as a Markdown file.",
        'ai_error': "❌ Sorry, I couldn't process that: {error}",
        'refresh_limit': "✅ **You're all caught up!**\n\nI've generated 2 digests for you and you've seen the top news. Check back later for more updates!",
        
        # New keys for full coverage
        'welcome': """👋 Welcome to *Tech News Bot*, {username}!

I'll keep you updated with the latest tech and AI news from:
• 📰 Hacker News
• 💻 TechCrunch  
• 🤖 AI Company Blogs (Anthropic, Google AI, Mistral, DeepMind)

*Quick Actions:* Use the buttons below ⬇️

*Or type any question* and I'll answer using AI!

Your current schedule: *18:00* daily
Use /settime to change it!""",
        
        'help_text': """📚 **LensAI Bot Commands**

📰 **News**
• /news - Get your personalized news digest
• /search <topic> - Search news by topic
• /sources - Toggle news sources on/off

🔖 **Saved Articles**
• /save <url> - Save an article
• /saved - View all saved articles
• /export - Export saved articles as a Markdown file
• /filter <category> - Filter by category (ai, security, crypto, startups, hardware, software, tech)
• /recap - Weekly recap of saved articles
• /clear_saved - Clear all saved articles

⚙️ **Settings**
• /schedule - Set daily digest time
• /language - Change response language
• /status - Check your settings

💬 **Chat**
Just type any question and I'll answer using AI!

📤 **Share**
• /share - Share the bot with friends

💡 **Tips:**
- Send me any URL to save it
- Use buttons below for quick access
- Click individual save buttons in digests""",
        
        'settime_prompt': "⏰ Please provide a time in HH:MM format.\nExample: `/settime 14:45`",
        'settime_invalid': "❌ Invalid time format. Please use HH:MM (24-hour format).\nExamples: 09:00, 14:45, 18:30",
        'settime_success': "✅ Daily digest scheduled for **{time}**!\n\nYou'll receive your personalized tech news at this time every day.",
        'settime_local': "⚠️ Schedule set to **{time}** (local mode - requires cloud deployment for scheduling).",
        
        'status_local': """📊 **Your Settings** (Local Mode)

⏰ **Daily Digest Time:** 18:00 (default)
🌍 **Timezone:** Asia/Baku

📰 **Active Sources:**
  • Hacker News
  • TechCrunch
  • AI Blogs

_Running locally - settings saved when deployed to cloud_""",
        
        'status_cloud': """📊 **Your Settings**

⏰ **Daily Digest Time:** {schedule_time}
🌍 **Timezone:** {timezone}

📰 **Active Sources:**
{sources}

Use /settime to change schedule
Use /sources to toggle sources""",
        
        'sources_header': "📰 **Your News Sources**\n\nTap to toggle sources on/off:",
        'save_help': "📌 **How to save articles:**\n\n1. `/save <url>` - Save directly\n2. Forward me a message with a link\n3. Reply to a news digest with `/save`",
        'select_language': "🌐 **Select Language**\n\nChoose your preferred language for summaries:",
        'az_coming_soon': "🇦🇿 **Azərbaycan dili tezliklə!**\n\nAzerbaijani language support is coming soon. Stay tuned!",
        
        # New features
        'share_bot': "📤 **Share LensAI Bot**\n\nShare this bot with friends:\n\n🔗 https://t.me/LensAI_bot\n\n_Stay updated with the latest tech news!_",
        'filter_prompt': "📂 **Filter by Category**\n\nUse `/filter <category>` to see saved articles by category.\n\nCategories: `ai`, `security`, `crypto`, `startups`, `hardware`, `software`, `tech`",
        'filter_results': "📂 **{category}** ({count} articles)\n\n",
        'filter_empty': "📂 No articles in category **{category}**.\n\nSave some articles first!",
        'recap_header': "📊 **Weekly Recap**\n_Your top saved articles this week:_\n\n",
        'recap_empty': "📊 **Weekly Recap**\n\nNo articles saved this week. Start saving articles to see your recap!",
        'article_deleted': "🗑️ Article deleted!",
        'article_saved_single': "✅ Article saved! Category: {category}",
        'btn_summarize': "🧠 Summarize",
        'summarizing_link': "🔄 Analyzing article...",
        'summary_error': "❌ Could not summarize article: {error}",
        'clear_all_btn': "🗑️ Clear All",
        'clear_all_prompt': "⚠️ **Are you sure you want to delete ALL saved articles?**\n\nThis action cannot be undone.",
        'clear_all_confirm_btn': "✅ Yes, delete all",
        'clear_all_cancel_btn': "❌ Cancel",
        
        # Category labels
        'cat_ai': "🤖 AI",
        'cat_security': "🔒 Security",
        'cat_crypto': "💰 Crypto",
        'cat_startups': "🚀 Startups",
        'cat_hardware': "💻 Hardware",
        'cat_software': "📱 Software",
        'cat_tech': "🔧 Tech",
        
        # Keyboard button labels
        'btn_news': "📰 Get News",
        'btn_search': "🔍 Search",
        'btn_saved': "🔖 Saved",
        'btn_status': "📊 Status",
        'btn_language': "🌐 Language",
        'btn_settings': "⚙️ Settings",
        'btn_schedule': "⏰ Schedule",
        'btn_help': "❓ Help",
        'btn_share': "📤 Share",
    },
    'ru': {
        # Existing keys
        'gathering_news': "🔄 **Собираю свежие новости...**\n\n⏱️ Это обычно занимает 1-3 минуты. Отправлю дайджест, как только будет готов!\n\n_Загружаю с Hacker News, TechCrunch и AI блогов..._",
        'cached_news': "📰 **Новости технологий**\n_Обновлено: {timestamp}_\n\n",
        'no_news': "😕 Новости не найдены. Попробуйте позже.",
        'error_fetching': "❌ Ошибка загрузки: {error}",
        'thinking': "🤔 _Думаю..._",
        'rate_limited': "⏳ Лимит запросов. Подождите {seconds} секунд.",
        'link_saved': "✅ Ссылка сохранена! Смотреть: /saved",
        'link_exists': "ℹ️ Ссылка уже сохранена!",
        'language_set': "✅ Язык изменён на **{language_name}**!\n\nБудущие дайджесты будут на этом языке.",
        'search_prompt': "🔍 **Поиск новостей**\n\nВведите `/search <тема>`\n\nПример: `/search GPT-5`",
        'search_history_header': "🕒 *Недавние запросы:*",
        'searching': "🔍 Ищу **{query}**...",
        'no_results': "😕 Ничего не найдено по запросу **{query}**.\n\nПопробуйте другой запрос!",
        'search_results': "🔍 **Результаты по '{query}'** ({count} найдено)\n\n",
        'schedule_prompt': "⏰ **Настройка ежедневного дайджеста**\n\nИспользуйте `/settime ЧЧ:ММ` для планирования.\n\nПримеры:\n• `/settime 09:00` - Утренний дайджест\n• `/settime 18:30` - Вечерний дайджест\n• `/settime 12:00` - Обеденный дайджест",
        'no_saved': "🔖 **Нет сохранённых статей!**\n\nОтправьте мне ссылку, и я сохраню её.\n\nИли используйте `/save <ссылка>`.",
        'saved_header': "🔖 **Ваши сохранённые статьи**\n\n",
        'saved_footer': "\n_Используйте /clear\\_saved чтобы удалить все_",
        'article_saved': "✅ Статья сохранена! Смотреть: /saved",
        'article_exists': "ℹ️ Статья уже сохранена!",
        'cleared_saved': "🗑️ Все сохранённые статьи удалены!",
        'export_empty': "🔖 **Пока нечего экспортировать!**\n\nСначала сохраните статью, затем попробуйте `/export` снова.",
        'export_caption': "📚 **Экспорт сохранённых статей**\n\nЭкспортировано {count} сохранённых статей в файл Markdown.",
        'ai_error': "❌ Не удалось обработать запрос: {error}",
        'refresh_limit': "✅ **Вы узнали всё главное!**\n\nЯ уже сделал для вас 2 уникальных дайджеста. Заходите позже за новыми новостями!",
        
        # New keys for full coverage
        'welcome': """👋 Добро пожаловать в *Tech News Bot*, {username}!

Я буду держать вас в курсе последних новостей технологий и ИИ:
• 📰 Hacker News
• 💻 TechCrunch  
• 🤖 Блоги AI-компаний (Anthropic, Google AI, Mistral, DeepMind)

*Быстрые действия:* Используйте кнопки ниже ⬇️

*Или задайте любой вопрос* и я отвечу с помощью ИИ!

Ваше расписание: ежедневно в *18:00*
Используйте /settime чтобы изменить!""",
        
        'help_text': """📚 **Команды бота LensAI**

📰 **Новости**
• /news - Получить персональный дайджест
• /search <тема> - Поиск по теме
• /sources - Настроить источники новостей

🔖 **Сохранённые статьи**
• /save <ссылка> - Сохранить статью
• /saved - Просмотреть все сохранённые
• /export - Экспорт сохранённых статей в Markdown
• /filter <категория> - Фильтр по категории (ai, security, crypto, startups, hardware, software, tech)
• /recap - Недельный обзор сохранённых
• /clear_saved - Очистить все сохранённые

⚙️ **Настройки**
• /schedule - Время ежедневного дайджеста
• /language - Изменить язык
• /status - Проверить настройки

💬 **Чат**
Просто напишите любой вопрос и я отвечу с помощью ИИ!

📤 **Поделиться**
• /share - Поделиться ботом с друзьями

💡 **Советы:**
- Отправьте мне URL чтобы сохранить
- Используйте кнопки ниже для быстрого доступа
- Нажимайте кнопки сохранения в дайджестах""",
        
        'settime_prompt': "⏰ Укажите время в формате ЧЧ:ММ.\nПример: `/settime 14:45`",
        'settime_invalid': "❌ Неверный формат времени. Используйте ЧЧ:ММ (24-часовой формат).\nПримеры: 09:00, 14:45, 18:30",
        'settime_success': "✅ Ежедневный дайджест запланирован на **{time}**!\n\nВы будете получать персональные новости технологий в это время каждый день.",
        'settime_local': "⚠️ Расписание установлено на **{time}** (локальный режим - для планирования требуется развёртывание в облаке).",
        
        'status_local': """📊 **Ваши настройки** (Локальный режим)

⏰ **Время дайджеста:** 18:00 (по умолчанию)
🌍 **Часовой пояс:** Баку

📰 **Активные источники:**
  • Hacker News
  • TechCrunch
  • AI Блоги

_Работает локально - настройки сохранятся при развёртывании в облаке_""",
        
        'status_cloud': """📊 **Ваши настройки**

⏰ **Время дайджеста:** {schedule_time}
🌍 **Часовой пояс:** {timezone}

📰 **Активные источники:**
{sources}

Используйте /settime чтобы изменить расписание
Используйте /sources чтобы настроить источники""",
        
        'sources_header': "📰 **Ваши источники новостей**\n\nНажмите чтобы включить/выключить:",
        'save_help': "📌 **Как сохранить статьи:**\n\n1. `/save <ссылка>` - Сохранить напрямую\n2. Перешлите мне сообщение со ссылкой\n3. Ответьте на дайджест командой `/save`",
        'select_language': "🌐 **Выберите язык**\n\nВыберите предпочитаемый язык для дайджестов:",
        'az_coming_soon': "🇦🇿 **Azərbaycan dili tezliklə!**\n\nПоддержка азербайджанского языка скоро появится. Следите за обновлениями!",
        
        # New features
        'share_bot': "📤 **Поделиться LensAI Bot**\n\nПоделитесь ботом с друзьями:\n\n🔗 https://t.me/LensAI_bot\n\n_Будьте в курсе последних новостей технологий!_",
        'filter_prompt': "📂 **Фильтр по категории**\n\nИспользуйте `/filter <категория>` для просмотра статей.\n\nКатегории: `ai`, `security`, `crypto`, `startups`, `hardware`, `software`, `tech`",
        'filter_results': "📂 **{category}** ({count} статей)\n\n",
        'filter_empty': "📂 Нет статей в категории **{category}**.\n\nСначала сохраните статьи!",
        'recap_header': "📊 **Недельный обзор**\n_Ваши топ статьи за эту неделю:_\n\n",
        'recap_empty': "📊 **Недельный обзор**\n\nНет сохранённых статей за неделю. Начните сохранять!",
        'article_deleted': "🗑️ Статья удалена!",
        'article_saved_single': "✅ Статья сохранена! Категория: {category}",
        'btn_summarize': "🧠 Краткое содержание",
        'summarizing_link': "🔄 Анализирую статью...",
        'summary_error': "❌ Не удалось суммаризировать статью: {error}",
        'clear_all_btn': "🗑️ Очистить всё",
        'clear_all_prompt': "⚠️ **Вы уверены, что хотите удалить ВСЕ сохранённые статьи?**\n\nЭто действие нельзя отменить.",
        'clear_all_confirm_btn': "✅ Да, удалить всё",
        'clear_all_cancel_btn': "❌ Отмена",
        
        # Category labels
        'cat_ai': "🤖 ИИ",
        'cat_security': "🔒 Безопасность",
        'cat_crypto': "💰 Крипто",
        'cat_startups': "🚀 Стартапы",
        'cat_hardware': "💻 Железо",
        'cat_software': "📱 Софт",
        'cat_tech': "🔧 Технологии",
        
        # Keyboard button labels
        'btn_news': "📰 Новости",
        'btn_search': "🔍 Поиск",
        'btn_saved': "🔖 Сохранённые",
        'btn_status': "📊 Статус",
        'btn_language': "🌐 Язык",
        'btn_settings': "⚙️ Настройки",
        'btn_schedule': "⏰ Расписание",
        'btn_help': "❓ Помощь",
        'btn_share': "📤 Поделиться",
    }
}



def get_message(key: str, lang: str = 'en', **kwargs) -> str:
    """
    Get a translated message.
    
    Args:
        key: Message key
        lang: Language code ('en', 'ru')
        **kwargs: Format arguments for the message
        
    Returns:
        Translated and formatted message
    """
    messages = MESSAGES.get(lang, MESSAGES['en'])
    message = messages.get(key, MESSAGES['en'].get(key, key))
    
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
    return message


def t(key: str, lang: str = 'en', **kwargs) -> str:
    """Shorthand for get_message."""
    return get_message(key, lang, **kwargs)
