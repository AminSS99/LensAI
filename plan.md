1.  **Add Translation Keys:** Add `btn_mark_read` translation keys to `functions/translations.py` for 'en' and 'ru' languages.
    -   `'btn_mark_read': "📖✅ Mark Read"` for 'en'.
    -   `'btn_mark_read': "📖✅ Отметить как прочитанное"` for 'ru'.
2.  **Update `_render_saved_page` (functions/telegram_bot.py):**
    -   Modify the loop where we build the keyboard.
    -   If an article `is_read` is False (not read), add a new button on the next line using the `btn_mark_read` translation and callback data `mark_read_{url_hash}_{page}`. Similar to the current logic for `btn_mark_unread`.
3.  **Create Callback Handler:**
    -   Create `mark_read_callback` in `functions/telegram_bot.py`, patterned exactly after `mark_unread_callback`.
    -   Extract `url_hash`. Find the `url`.
    -   Call `mark_article_read(telegram_id, url)`.
    -   Re-render the page (`_render_saved_page`).
4.  **Register Callback Handler:**
    -   Add `application.add_handler(CallbackQueryHandler(mark_read_callback, pattern='^mark_read_'))` in `setup_bot_commands` or `create_bot_application` in `functions/telegram_bot.py`.
5.  **Pre-commit Steps:**
    -   Run tests.
    -   Lint/syntax check Python.
