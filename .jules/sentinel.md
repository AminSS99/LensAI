## 2024-05-24 - [HIGH] Fix weak hashing algorithms
**Vulnerability:** MD5 and SHA-1 algorithms were being used for cryptographic hashes (e.g. `hashlib.md5` and `hashlib.sha1`) in several modules (`functions/cache.py`, `functions/telegram_bot.py`, `functions/user_storage.py`).
**Learning:** Usage of insecure algorithms like MD5 and SHA1 poses a security risk due to known vulnerabilities and collision weaknesses. Even when used for non-critical identifiers, it is a bad practice and violates security policies.
**Prevention:** Establish and strictly enforce a coding standard that mandates the use of modern, secure hash functions (such as SHA-256) for all hashing purposes. Here, we implemented a centralized `stable_hash` utility (using SHA-256) to ensure consistent and secure hashing across the codebase.

## 2026-04-05 - [CRITICAL] Prevent SSRF in AI summarize
**Vulnerability:** In `summarize_url_callback`, `httpx.AsyncClient` used `follow_redirects=True` with unvalidated user-provided URLs. This could allow an attacker to bypass domain checks via a 301/302 redirect and force the bot to fetch sensitive internal network services (like cloud metadata on `169.254.169.254` or local host services), leading to a Server-Side Request Forgery (SSRF) attack.
**Learning:** Automatically following redirects via HTTP clients (like `httpx` or `requests`) defeats URL-based domain validation filters because the client will silently hop to an internal IP address without re-evaluating safety.
**Prevention:** To prevent SSRF, always disable automatic redirects (`follow_redirects=False`), manually inspect the `Location` header, and independently evaluate *every single hop* of the redirect chain against strict IP restrictions (e.g., rejecting `ip.is_link_local`, `ip.is_unspecified`, and non-`is_global`) using asynchronous DNS resolution (`asyncio.get_running_loop().getaddrinfo(hostname, None)`).

## 2026-04-27 - [HIGH] Prevent SSRF in scrapers by enforcing safe redirect following
**Vulnerability:** In scraper modules (`functions/scrapers/producthunt.py`, `functions/scrapers/theverge.py`, and `functions/scrapers/ai_blogs.py`), `httpx.Client` was configured with `follow_redirects=True`. This allowed the client to silently follow HTTP redirects (e.g., 301, 302) to potentially unsafe internal IP addresses or private network resources.
**Learning:** Automatically following redirects with HTTP clients enables SSRF bypasses, as the domain validation is only performed on the initial request, ignoring subsequent hops.
**Prevention:** Always disable automatic redirect following (`follow_redirects=False`) in HTTP clients. Implement a manual redirect loop (with a maximum count, e.g., 5) and independently validate every redirect URL using strict checks (like `is_safe_url` or `is_safe_url_sync`) to ensure the destination is safe.

## 2026-04-27 - [HIGH] Prevent Cross-Site Scripting (XSS) in HTML parsing
**Vulnerability:** Scrapers (`producthunt.py`, `theverge.py`, `techcrunch.py`) used a naive regex `re.sub(r'<[^>]+>', '', text)` to strip HTML tags from RSS summaries/descriptions. This insecurely leaves the contents of `<script>` and `<style>` tags intact, allowing potential Cross-Site Scripting (XSS) if the summarized text is rendered directly in an unsafe web context or messaging client without further sanitization.
**Learning:** Regex is insufficient for secure HTML sanitization. Extracting text from untrusted HTML using a naive regex can lead to data pollution and XSS by exposing hidden javascript or CSS. Furthermore, simple removal merges adjacent text nodes (e.g. `<p>A</p><p>B</p>` becomes `AB`).
**Prevention:** Always use a proper HTML parser (like `BeautifulSoup`) to explicitly decompose dangerous elements (`['script', 'style']`) before extracting text. When extracting text, use a space separator (`soup.get_text(separator=' ')`) to preserve formatting and prevent word merging. This was centralized into a `sanitize_html` utility in `security_utils.py`.

## 2025-02-27 - [HIGH] Prevent Timing Attacks on Webhook Secret Tokens
**Vulnerability:** The Telegram webhook and internal API endpoints in `functions/main.py` validated authorization headers (`X-Telegram-Bot-Api-Secret-Token` and `X-Internal-Secret`) using a simple string equality comparison (`!=`). This allowed attackers to potentially use timing attacks to guess the secret token byte by byte.
**Learning:** Normal string comparison checks operators short-circuit, returning false on the first mismatched character. By measuring the precise time it takes for the server to reject a request, an attacker can determine how many characters of their guess were correct.
**Prevention:** Always use constant-time comparison functions, such as `hmac.compare_digest()`, when verifying cryptographic materials like passwords, MACs, API tokens, or webhook secrets.

## 2024-05-22 - [CRITICAL] Fix fail-open Authorization Bypass
**Vulnerability:** The internal API authentication check `_require_internal_secret` in `functions/main.py` was implemented to fail open if the `INTERNAL_SECRET` environment variable was missing or empty (`if expected and not (...)`).
**Learning:** Checking for the presence of an expected secret via `if expected` allows the code block to be bypassed if `expected` evaluates to false, making the authorization check fail open and allowing unauthorized access. Also, missing headers would pass `None` to `hmac.compare_digest`, causing a `TypeError`.
**Prevention:** Always implement authentication and authorization checks using a fail-closed conditional structure (e.g., `if not expected or ...`), ensuring that missing environment variables block access rather than bypassing the check. Also, provide fallback strings when reading headers for cryptographic checks.

## 2024-06-05 - [HIGH] Prevent HTTP Parameter Pollution via F-string URL Construction
**Vulnerability:** The Algolia HN API URL in `functions/deep_dive.py` was built using f-string string interpolation: `api_url = f"https://hn.algolia.com/api/v1/search?query={url}&tags=story&hitsPerPage=3"`. This allowed for HTTP Parameter Pollution or manipulation if the `url` variable contained special URL characters (e.g., `&`, `=`, `#`).
**Learning:** Constructing HTTP queries with basic string formatting is prone to injection flaws and URL malformation because variables are not safely URL-encoded before being appended.
**Prevention:** Always use the dedicated `params` dictionary argument provided by modern HTTP clients (like `httpx.get(url, params=...)` or `requests.get(url, params=...)`) to ensure all user input or variable data is automatically and safely URL-encoded prior to transmission.
## 2026-10-31 - [HIGH] Prevent Path Traversal and SSRF via permissive regex in URL parsing
**Vulnerability:** The `extract_github_repo` function in `functions/deep_dive.py` used a permissive regex `[^/]+/[^/]+` to extract repository paths from user-provided URLs. This allowed capturing URL-encoded characters (like `%2F..`) and query parameters, which were subsequently injected into GitHub API request URLs.
**Learning:** When using regular expressions to extract repository paths from URLs (e.g., `github.com/...`), avoid permissive matchers like `[^/]+` as they can capture URL-encoded traversal payloads or query parameters, leading to SSRF and path traversal vulnerabilities.
**Prevention:** Always use strict character classes (e.g., `[A-Za-z0-9\-]+/[A-Za-z0-9\-_.]+`) that align with the platform's naming conventions when parsing and extracting parameters from URLs for external API requests.
