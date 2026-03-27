## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2025-02-28 - [CRITICAL] Prevented SSRF in URL Summarization
**Vulnerability:** The `/summarize_url` functionality in the Telegram bot fetched user-provided URLs using `httpx.AsyncClient` without any validation against internal network addresses. Furthermore, it automatically followed redirects, opening a vector for TOCTOU attacks where an initially safe URL redirects to a malicious internal endpoint (e.g., cloud metadata or internal services).
**Learning:** Even if the initial user input points to a public domain, the underlying application can be coerced into accessing internal resources via HTTP redirects. Asynchronous web clients like `httpx` abstract away redirect handling, which can bypass initial input validation if not carefully managed.
**Prevention:**
1. Implemented a robust `is_safe_url` utility that resolves hostnames asynchronously and explicitly blocks loopback, private, multicast, and link-local (cloud metadata) IP ranges.
2. Disabled automatic redirect following (`follow_redirects=False`) in `httpx.AsyncClient`.
3. Manually resolved and evaluated every redirect hop using `urllib.parse.urljoin` to ensure every step of the redirect chain is validated against `is_safe_url` before issuing the next GET request.
