## 2025-03-11 - Enforce Cryptographically Secure Hashing
**Vulnerability:** Weak hashing algorithms (MD5 and SHA-1) were used for cache keys, article hashes, and unique identifiers.
**Learning:** The application codebase mistakenly relied on legacy algorithms instead of using the secure, deterministic SHA-256 implementation established in `functions.security_utils.stable_hash`. Even when generating short identifiers (like 8-character hashes for Telegram callbacks), modern hashes should be truncated rather than using outdated fast-hashing functions.
**Prevention:** Always use `stable_hash` from `functions.security_utils` for hashing requirements. Avoid `hashlib.md5` and `hashlib.sha1` completely across the application.
