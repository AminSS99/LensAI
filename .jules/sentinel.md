## 2024-05-20 - Use SHA-256 for all hashing
**Vulnerability:** Weak cryptographic hashing algorithms (MD5, SHA-1) were used for generating IDs and cache keys.
**Learning:** Using weak hashing algorithms can lead to collisions, and modern standards require SHA-256 or higher. The project provides `functions.security_utils.stable_hash` for this purpose.
**Prevention:** Always use `functions.security_utils.stable_hash` instead of `hashlib.md5` or `hashlib.sha1`.
