"""
Translations Module
Bot message translations for different languages.
"""

# Message translations
MESSAGES = {
    'en': {
        'gathering_news': "🔄 **Gathering fresh news from all sources...**\n\n⏱️ This usually takes 1-3 minutes. I'll send your digest as soon as it's ready!\n\n_Fetching from Hacker News, TechCrunch, and AI blogs..._",
        'cached_news': "📰 **Cached News Digest**\n_Last updated: {timestamp}_\n\n",
        'no_news': "😕 No news found. Please try again later.",
        'error_fetching': "❌ Error fetching news: {error}",
        'thinking': "🤔 _Thinking..._",
        'rate_limited': "⏳ Rate limit reached. Please wait {seconds} seconds.",
        'link_saved': "✅ Link saved! View with /saved",
        'link_exists': "ℹ️ Link already saved!",
        'language_set': "✅ Language set to **{lang}**!\n\nFuture summaries will be in this language.",
        'search_prompt': "🔍 **Search News**\n\nType `/search <topic>`\n\nExample: `/search GPT-5`",
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
        'ai_error': "❌ Sorry, I couldn't process that: {error}",
    },
    'ru': {
        'gathering_news': "🔄 **Собираю свежие новости...**\n\n⏱️ Это обычно занимает 1-3 минуты. Отправлю дайджест, как только будет готов!\n\n_Загружаю с Hacker News, TechCrunch и AI блогов..._",
        'cached_news': "📰 **Кэшированный дайджест**\n_Обновлено: {timestamp}_\n\n",
        'no_news': "😕 Новости не найдены. Попробуйте позже.",
        'error_fetching': "❌ Ошибка загрузки: {error}",
        'thinking': "🤔 _Думаю..._",
        'rate_limited': "⏳ Лимит запросов. Подождите {seconds} секунд.",
        'link_saved': "✅ Ссылка сохранена! Смотреть: /saved",
        'link_exists': "ℹ️ Ссылка уже сохранена!",
        'language_set': "✅ Язык изменён на **{lang}**!\n\nБудущие дайджесты будут на этом языке.",
        'search_prompt': "🔍 **Поиск новостей**\n\nВведите `/search <тема>`\n\nПример: `/search GPT-5`",
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
        'ai_error': "❌ Не удалось обработать запрос: {error}",
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
