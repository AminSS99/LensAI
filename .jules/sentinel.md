## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2024-05-24 - [HIGH] Fix Server-Side Request Forgery (SSRF) risk in URL summarization
**Vulnerability:** The application was vulnerable to SSRF as user-provided URLs were directly passed into an HTTP GET request inside `summarize_url_callback` (and stored via `handle_message`) without validation, allowing access to internal networks or metadata services.
**Learning:** Unrestricted outbound requests triggered by user inputs can expose internal systems and metadata (like GCP Metadata server). Always validate and sanitize user-provided URLs before fetching them.
**Prevention:** Utilize URL validation techniques (e.g. `urllib.parse` and `ipaddress`) to reject local, loopback, private IP ranges, and internal hostnames such as `localhost` or `metadata.google.internal` before initiating requests.
