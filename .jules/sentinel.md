## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2024-05-31 - [CRITICAL] Prevent Server-Side Request Forgery (SSRF) in link summarization
**Vulnerability:** The `summarize_url_callback` functionality in `functions/telegram_bot.py` was directly fetching user-provided URLs using `httpx.AsyncClient` with `follow_redirects=True`. This allowed malicious actors to potentially fetch internal services or local files on the server (e.g., bypassing network controls or accessing metadata endpoints) by supplying a URL that resolved to an internal IP address or by supplying an external URL that redirected to an internal IP address.
**Learning:** Even seemingly harmless functionalities like a "summarize this link" bot feature can be abused for SSRF if user-provided URLs are not strictly validated before fetching. The native HTTP client redirect following mechanisms are dangerous because the validation is only applied to the initial URL, not the subsequent redirects.
**Prevention:**
1. Establish a strict validation function (`is_safe_url`) that checks URLs against known private, loopback, and reserved IP ranges.
2. Disable automatic redirect following (`follow_redirects=False`) on HTTP clients when fetching user-provided URLs.
3. Handle redirects manually and run the validation check (`await is_safe_url()`) on the target URL of every single hop to prevent malicious actors from using a safe external URL that redirects to an internal, vulnerable endpoint.
