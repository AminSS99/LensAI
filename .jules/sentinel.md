## 2024-05-20 - Prevent XML External Entity (XXE) and Billion Laughs Vulnerabilities
**Vulnerability:** Use of standard library `xml.etree.ElementTree` to parse untrusted XML/RSS feeds in `theverge.py` and `producthunt.py` scrapers.
**Learning:** The built-in `xml.etree` module in Python is vulnerable to malicious XML payloads such as XML External Entities (XXE) and Billion Laughs attacks. Parsing feeds from external, untrusted sources without defensive measures creates severe security risks (DoS or data exfiltration).
**Prevention:** Always use `defusedxml.ElementTree` instead of `xml.etree.ElementTree` when parsing any XML data from an untrusted source or network request. Ensure `defusedxml` is included in project dependencies.
