# LensAI Project Map

## Purpose
LensAI is a Telegram-based tech and AI news assistant.
It aggregates content from multiple sources, builds digests with DeepSeek, and sends results to users with personalization, scheduling, and fallback logic.

## Runtime Entry Points
All HTTP Cloud Function entry points live in `functions/main.py`:

- `telegram_webhook(request)`: handles Telegram updates.
- `scheduled_digest(request)`: sends scheduled digests (direct call or Cloud Scheduler).
- `weekly_trend_alerts(request)`: sends weekly trend alerts.
- `fetch_news(request)`: on-demand fetch/summarize endpoint.
- `health(request)`: health check endpoint.

## Key Modules

- `functions/telegram_bot.py`: bot commands, callbacks, menus, and message handling.
- `functions/summarizer.py`: DeepSeek client and digest generation with fallback.
- `functions/scrapers/*.py`: source fetchers (Hacker News, TechCrunch, AI blogs, The Verge, GitHub Trending, Product Hunt).
- `functions/database.py`: core Firestore CRUD for users/articles/digests.
- `functions/user_storage.py`: user preferences, saved articles, ratings, temp digest context.
- `functions/personalization.py`: ranking + feedback loop.
- `functions/trend_analysis.py`: daily topic trend recording and weekly trend computation.
- `functions/cache.py`: digest caching with TTL.
- `functions/distributed_lock.py`: Firestore lock to avoid duplicate processing.
- `functions/rate_limiter.py`: request rate limits.
- `functions/message_utils.py`: Telegram-safe message splitting.
- `functions/observability.py`: admin runtime snapshot helpers.

## Environment Variables

- `TELEGRAM_BOT_TOKEN`: required for bot send/receive operations.
- `DEEPSEEK_API_KEY`: required for AI summarization and Q/A.
- `GOOGLE_CLOUD_PROJECT`: default GCP project and Firestore project fallback.
- `FIRESTORE_PROJECT_ID`: optional explicit Firestore project override.
- `ADMIN_TELEGRAM_IDS`: optional comma-separated IDs for admin commands.
- `GOOGLE_APPLICATION_CREDENTIALS`: optional local credential path for Firestore.

## Firestore Collections

- `users`
- `articles`
- `digests`
- `cache`
- `locks`
- `rate_limits`
- `user_preferences`
- `article_ratings`
- `refresh_sessions`
- `digests_temp`
- `daily_trends`
- `user_profiles`
- `digest_context`

Subcollections:
- `users/{telegram_id}/saved_articles`
- `users/{telegram_id}/search_history`

## Local Development Commands

```bash
python -m venv venv
venv\Scripts\activate
pip install -r functions/requirements.txt python-dotenv
python test_scrapers.py
python test_new_scrapers.py
python run_local.py
```

Optional scraper-only check:

```bash
python run_local.py --test-scrapers
```
