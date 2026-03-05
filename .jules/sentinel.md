## 2025-03-05 - [XML External Entity (XXE) Prevention]
**Vulnerability:** Found `xml.etree.ElementTree` being used to parse external untrusted RSS feeds in scrapers (`theverge.py` and `producthunt.py`). This standard library is vulnerable to XML vulnerabilities such as XXE and Billion Laughs.
**Learning:** External feeds must always be treated as untrusted data. Standard XML parsers often do not protect against recursive entities or external entity resolution.
**Prevention:** Always use `defusedxml.ElementTree` instead of the standard library `xml.etree.ElementTree` when parsing untrusted XML/RSS feeds to prevent XML-based attacks.
