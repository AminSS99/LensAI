## 2024-05-23 - Markdown Injection in Telegram Messages
**Vulnerability:** User-controlled input (usernames, search queries, article titles) was directly inserted into Markdown-formatted messages without escaping.
**Learning:** Even in non-web applications like Telegram bots, input validation and output encoding are critical. Unescaped characters like `*` and `_` can break message formatting, leading to denial of service (message send failure) or spoofing.
**Prevention:** Always escape user input before interpolating it into message templates. Use a helper function like `escape_markdown_v1` for Legacy Markdown mode.
