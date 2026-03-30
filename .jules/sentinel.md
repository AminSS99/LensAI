## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2024-05-18 - [SSRF vulnerability in URL summarization]
**Vulnerability:** Server-Side Request Forgery (SSRF) in `summarize_url_callback` and potentially other places that fetch user-provided URLs. The bot doesn't check if the URL resolves to local, loopback, or private networks before making an HTTP request via `httpx`.
**Learning:** Telegram bots often accept links from users. Any link fetching mechanism can be abused to probe internal network services if input isn't validated properly.
**Prevention:** Implement `is_safe_url` checking to reject non-public IPs.
