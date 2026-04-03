import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath('functions'))

from functions.telegram_bot import stats_command

@pytest.mark.asyncio
@patch('functions.telegram_bot.get_user_language', return_value='en', create=True)
@patch('functions.telegram_bot.get_all_saved_articles', return_value=[], create=True)
@patch('functions.translations.t')
async def test_stats_command_empty(mock_t, mock_get_all_saved_articles, mock_get_user_language):
    # Setup mocks
    mock_get_user_language.return_value = 'en'
    mock_get_all_saved_articles.return_value = []

    # We patch `t` globally because we're patching creating things that don't exist directly on `telegram_bot`.
    def mock_t_func(key, lang, **kwargs):
        if key == 'stats_empty':
            return "You haven't saved any articles yet."
        elif key == 'stats_header':
            return "Your Reading Profile"
        elif key == 'stats_total':
            return f"\nTotal saved articles: {kwargs.get('total')}"
        elif key.startswith('cat_'):
            return key.replace('cat_', '').title()
        return key
    mock_t.side_effect = mock_t_func

    update = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()

    context = MagicMock()

    # Run
    # Use patch to inject the imports
    with patch('functions.user_storage.get_user_language', return_value='en'), \
         patch('functions.user_storage.get_all_saved_articles', return_value=[]), \
         patch('functions.translations.t', side_effect=mock_t_func):
        await stats_command(update, context)

    # Verify
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "You haven't saved any articles yet" in args[0]


@pytest.mark.asyncio
async def test_stats_command_with_articles():
    # Setup mocks
    def mock_t_func(key, lang, **kwargs):
        if key == 'stats_empty':
            return "You haven't saved any articles yet."
        elif key == 'stats_header':
            return "Your Reading Profile\n"
        elif key == 'stats_total':
            return f"\nTotal saved articles: {kwargs.get('total')}"
        elif key.startswith('cat_'):
            return key.replace('cat_', '').title()
        return key

    update = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()

    context = MagicMock()

    # Run
    articles = [
        {'title': '1', 'url': 'a', 'category': 'ai'},
        {'title': '2', 'url': 'b', 'category': 'ai'},
        {'title': '3', 'url': 'c', 'category': 'security'},
        {'title': '4', 'url': 'd', 'category': 'tech'},
    ]
    with patch('functions.user_storage.get_user_language', return_value='en'), \
         patch('functions.user_storage.get_all_saved_articles', return_value=articles), \
         patch('functions.translations.t', side_effect=mock_t_func):
        await stats_command(update, context)

    # Verify
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    text = args[0]

    # Sort order: AI (2) > Security (1), Tech (1)
    assert "Your Reading Profile" in text
    assert "Ai: 2" in text
    assert "Security: 1" in text
    assert "Tech: 1" in text
    assert "Total saved articles: 4" in text
