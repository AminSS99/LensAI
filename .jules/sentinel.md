## 2025-02-27 - [Fix XML Parsing Vulnerabilities]
**Vulnerability:** Found `xml.etree.ElementTree` being used in `functions/scrapers/theverge.py` and `functions/scrapers/producthunt.py` to parse potentially untrusted XML feeds, exposing the system to XML External Entity (XXE) and Billion Laughs attacks.
**Learning:** External feeds are inherently untrusted and using the standard Python library XML parsers directly on untrusted input is a known security vulnerability.
**Prevention:** Always use `defusedxml.ElementTree` when parsing any XML or RSS feed that is fetched from the internet. Do not use the standard `xml.etree.ElementTree` directly.
