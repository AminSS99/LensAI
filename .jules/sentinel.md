## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2026-04-05 - [CRITICAL] Prevent SSRF in AI summarize
**Vulnerability:** In `summarize_url_callback`, `httpx.AsyncClient` used `follow_redirects=True` with unvalidated user-provided URLs. This could allow an attacker to bypass domain checks via a 301/302 redirect and force the bot to fetch sensitive internal network services (like cloud metadata on `169.254.169.254` or local host services), leading to a Server-Side Request Forgery (SSRF) attack.
**Learning:** Automatically following redirects via HTTP clients (like `httpx` or `requests`) defeats URL-based domain validation filters because the client will silently hop to an internal IP address without re-evaluating safety.
**Prevention:** To prevent SSRF, always disable automatic redirects (`follow_redirects=False`), manually inspect the `Location` header, and independently evaluate *every single hop* of the redirect chain against strict IP restrictions (e.g., rejecting `ip.is_link_local`, `ip.is_unspecified`, and non-`is_global`) using asynchronous DNS resolution (`asyncio.get_running_loop().getaddrinfo(hostname, None)`).

## 2024-04-16 - [HIGH] Missing Telegram Webhook Secret Token Validation
**Vulnerability:** The Telegram webhook handler in `functions/main.py` accepted incoming requests without verifying the `X-Telegram-Bot-Api-Secret-Token` header against a stored secret.
**Learning:** Any endpoint configured as a webhook should authenticate the sender. Without validation, anyone who discovers the webhook URL can send forged updates to the bot.
**Prevention:** Implement webhook sender validation using secrets provided in headers (such as `X-Telegram-Bot-Api-Secret-Token` for Telegram) and verify them against environment variables before processing any payload.
