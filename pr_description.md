🎯 **What:**
Added unit tests for the `extract_github_repo` function to ensure it properly handles edge cases such as malformed URLs and unexpected non-string inputs. During implementation, a defensive type check and a `try/except` block were added to the function to handle these types gracefully.

📊 **Coverage:**
- Happy paths with valid GitHub HTTP and HTTPS URLs.
- Edge cases with non-GitHub URLs or empty inputs.
- Error conditions with improperly typed arguments like integers, dictionaries, and lists.

✨ **Result:**
Increased reliability and test coverage. The `extract_github_repo` function will now safely handle arbitrary inputs and will no longer raise a `TypeError` if fed malformed data from unpredictable payloads, such as those caused by scraping edge-cases.
