## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.
## 2024-05-25 - [CRITICAL] Fix SSRF vulnerability in URL fetching
**Vulnerability:** The application was fetching arbitrary user-provided URLs in `summarize_url_callback` using `httpx` with `follow_redirects=True`, allowing attackers to access internal or private network resources.
**Learning:** Automatically following redirects or fetching unvalidated URLs can expose private IP addresses and loopback interfaces (SSRF).
**Prevention:** An asynchronous `is_safe_url` function was implemented to resolve the URL's hostname and check against private/local IP ranges. We also disabled `follow_redirects=True` in `httpx` and manually followed redirects up to a maximum limit, validating each hop with `is_safe_url`.
