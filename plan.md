1. **Understand the Goal**: The user wants *ONE meaningful feature improvement* that increases the product's usefulness, clarity, or capability. The feature must be *small but impactful* and implemented safely within the existing architecture (e.g. keeping it under 120 lines, avoiding major rewrites).
2. **Current Finding**: In `functions/telegram_bot.py`, the user can search articles with `/search <query>`. A great feature enhancement to add for an article aggregator and bookmark manager would be **Inline Queries**. This allows users to search and share their *saved* articles directly into *any* chat by typing `@BotName <query>`. It is incredibly useful for sharing saved links, fits easily within the current architecture, requires no DB schema changes, and is highly expected by Telegram power users.
3. **Proposed Action - Add Inline Query Support**:
   - Register `InlineQueryHandler(inline_query_handler)` in `functions/telegram_bot.py`.
   - Create `inline_query_handler(update, context)` in `functions/telegram_bot.py`.
   - The handler will take the user's `inline_query.query`.
   - Call `get_all_saved_articles(update.inline_query.from_user.id)` to fetch their saved articles.
   - Filter the saved articles based on the `query` (case-insensitive substring match on title/url). If query is empty, show the most recently saved articles.
   - Map the matching articles to `InlineQueryResultArticle` containing the title, URL, category, and an `InputTextMessageContent` that sends the link formatted nicely.
   - Await `update.inline_query.answer(results, cache_time=10, is_personal=True)`.
4. **Implementation Details**:
   - Limit the results to 50 (Telegram limit for inline queries).
   - The UI for inline query result will be a nicely formatted text like:
     `[Title](URL)`
   - Add translation texts for the inline query (though we mostly just return the articles, we can add a placeholder like "Search saved articles..." for the button or description).
5. **Run tests** and use `pre_commit_instructions` before submitting.
