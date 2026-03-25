## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2024-05-28 - [CRITICAL] Prevent SSRF when fetching user URLs
**Vulnerability:** The bot fetched user-provided URLs in `summarize_url_callback` using `httpx.AsyncClient` with `follow_redirects=True`, without validating the destination IP address or redirect hops, exposing the internal network to SSRF.
**Learning:** Automatically following redirects allows attackers to bypass initial URL checks by pointing a safe-looking domain to an internal IP (like `169.254.169.254` or `127.0.0.1`) via HTTP 3xx redirects.
**Prevention:** Always set `follow_redirects=False` when making requests to untrusted URLs. Manually handle redirects by extracting the `Location` header, resolving the new URL, and explicitly checking its safety (e.g., using `is_safe_url` to resolve hostnames and block private/loopback IPs) before executing the next request. Implement a strict limit on the number of redirect hops.
