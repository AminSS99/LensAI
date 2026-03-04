## 2025-02-27 - [Fix XXE Vulnerability in Scrapers]
**Vulnerability:** Found `xml.etree.ElementTree.fromstring` parsing untrusted XML data (RSS feeds) in `functions/scrapers/theverge.py` and `functions/scrapers/producthunt.py`. This is vulnerable to XML Entity Expansion (Billion Laughs) and XXE attacks.
**Learning:** Standard library XML parsers in Python are not secure by default. Untrusted input must not be passed to them.
**Prevention:** Always use `defusedxml.ElementTree.fromstring` as a drop-in replacement when parsing XML from external or untrusted sources.
