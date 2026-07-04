1. **Goal**: Add a "🗑️ Unsave" button to the article reading view (`read_url_callback`) so users can remove an article after reading it.
2. **Implementation details**:
   - In `functions/telegram_bot.py`, `read_url_callback` renders chunks of text. The last chunk gets a `reply_markup` with "Original", "Summarize", and "Share".
   - We will add "🗑️ Unsave" with `callback_data=f"del_{url_hash}_read"`.
   - Update `delete_article_callback` to handle the `read` flag (like it handles `random`). When `is_read = True`, it will delete the article, answer the query, and delete the message without needing to call a command to re-render. Since `read_url_callback` splits messages, deleting the last message chunk is sufficient (or simply editing the last chunk's reply markup to remove the buttons, with an "Article deleted" notification). Wait, editing the buttons to remove them might be cleaner. Let's just edit the message reply markup.
3. **Plan steps**:
   1. Use `replace_with_git_merge_diff` to add the "Unsave" button in `read_url_callback`.
   2. Use `replace_with_git_merge_diff` to update `delete_article_callback` to handle `read` context.
   3. Verify changes using `grep` or `cat`.
   4. Run tests with `python -m pytest test*.py`.
   5. Complete pre commit steps to ensure proper testing, verification, review, and reflection are done.
   6. Submit the change.
