## 2025-05-15 - [Prevent HTTP Parameter Pollution via URL Interpolation]
**Vulnerability:** Found HTTP Parameter Pollution / Server-Side Request Forgery (SSRF) risk in `functions/deep_dive.py` when interpolating unsanitized URL string directly into `httpx` GET requests.
**Learning:** Constructing query strings manually with user-provided input (e.g. `f"?query={url}"`) is prone to parameter injection or malformed requests since special characters are not safely encoded.
**Prevention:** Always use the `params` dictionary argument in HTTP clients like `httpx` or `requests` (e.g. `client.get(api_url, params={"query": url})`) to ensure automatic and secure URL encoding of user inputs.
