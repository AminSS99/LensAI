---
name: ai
description: Maintain and deploy the LensAI Telegram news bot in this repository. Use when working on code in `functions/`, running local bot or scraper checks, handling environment/secrets setup, or deploying and operating Google Cloud Functions, Secret Manager, Firestore, and Cloud Scheduler jobs for LensAI.
---

# AI

## Objective

Implement and operate LensAI safely across local development and GCP production.
Use deterministic project-specific workflows instead of generic assumptions.

## Start Here

1. Read `references/project-map.md` to understand entry points, module ownership, and Firestore collections.
2. Read `references/gcp-deploy.md` before any cloud deployment, secret rotation, webhook change, or scheduler change.
3. Keep edits focused on requested behavior. Avoid broad refactors unless required by the task.

## Project Access Model

- Use `functions/main.py` as the canonical HTTP entry-point map.
- Treat `functions/telegram_bot.py` as the command/callback behavior source of truth.
- Treat `functions/summarizer.py` as the DeepSeek integration source of truth.
- Treat Firestore access helpers in `functions/database.py`, `functions/user_storage.py`, `functions/cache.py`, and `functions/distributed_lock.py` as the persistence layer.
- Do not hardcode secrets. Load from environment locally and from Secret Manager in GCP.
- Resolve Firestore project with `FIRESTORE_PROJECT_ID` first, then `GOOGLE_CLOUD_PROJECT`.

## Local Workflow

1. Create and activate virtualenv.
2. Install dependencies from `functions/requirements.txt` and `python-dotenv`.
3. Copy `.env.example` to `.env` and set:
- `TELEGRAM_BOT_TOKEN`
- `DEEPSEEK_API_KEY`
- `GOOGLE_CLOUD_PROJECT` (or `FIRESTORE_PROJECT_ID`)
4. Run quick checks:
- `python test_scrapers.py`
- `python test_new_scrapers.py`
5. Run local polling mode:
- `python run_local.py`
6. Use `python run_local.py --test-scrapers` when diagnosing source fetch failures.

## Deployment Workflow (GCP)

Follow the exact commands in `references/gcp-deploy.md`.
Deploy functions from `--source=functions` with explicit entry points from `functions/main.py`.

Deploy these entry points as separate Cloud Functions when needed:
- `telegram_webhook`
- `scheduled_digest`
- `weekly_trend_alerts`
- `fetch_news`
- `health`

After deploying `telegram_webhook`, set Telegram webhook URL to that function URL.
After deploying scheduler targets, ensure Cloud Scheduler jobs hit the correct URLs.

## Change Safety Rules

- Preserve resilience paths:
- AI summarization fallback chain in `functions/summarizer.py`
- distributed lock behavior in `functions/distributed_lock.py`
- per-user schedule + timezone logic in `process_scheduled_digest` (`functions/main.py`)
- Keep Telegram-safe message splitting via `functions/message_utils.py`.
- Prefer additive changes with tests or runnable checks.
- For deployment changes, verify function URLs, webhook state, and scheduler status after update.

## Validation Checklist

Run this minimum checklist before finalizing:

1. Lint or syntax-check changed Python files (if touched).
2. Run scraper smoke tests (`test_scrapers.py` and/or `test_new_scrapers.py`) for source-facing changes.
3. Run local bot (`run_local.py`) for bot-flow changes.
4. For deployed changes, run health check and function invocation smoke tests from `references/gcp-deploy.md`.
