1. **Goal**: Introduce a "Summarize" inline button for saved articles so users can quickly generate AI summaries of specific URLs without manually sending the link or re-copying it.
2. **Where to Add Summarize Buttons**:
   - `saved_command`: Currently paginates and shows inline "Delete 🗑️" buttons. We will add a "Summarize 🧠" inline button alongside each "Delete 🗑️" button.
   - `random_command`: Currently shows a random article with no reply markup. We will add a "Summarize 🧠" inline button.
   - `filter_command`: Currently lists filtered articles. We will add "Summarize 🧠" buttons for the first few items or attach a generic keyboard for the listed items.
   - `search_command`: Currently lists search results. We will attach summarize buttons here too if applicable, or we'll stick to just saved items as per "Summarize saved URL". The feature description implies making "Summarize" easily accessible where articles are listed. The `/random` and `/saved` commands are perfect places.
3. **Existing Infrastructure**: The `summarize_url_<hash>` callback handler is already implemented (`summarize_url_callback`). We just need to add the buttons that trigger it.
4. **Execution**:
   - Update `_render_saved_page` in `functions/telegram_bot.py` to include a summarize button before the delete button in the inline keyboard array.
   - Update `random_command` in `functions/telegram_bot.py` to add a reply markup containing a summarize button for the chosen article.
   - Run tests and `pre_commit_instructions` to ensure safety and functionality.
