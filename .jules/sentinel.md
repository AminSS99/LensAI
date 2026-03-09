## 2024-05-20 - Prevent XML External Entity (XXE) and Billion Laughs Vulnerabilities
**Vulnerability:** Untrusted XML/RSS feeds were parsed using the standard library `xml.etree.ElementTree`, which is vulnerable to XXE (XML External Entity) and Billion Laughs attacks.
**Learning:** The project's scrapers fetch external RSS/Atom feeds and parse them directly. The standard Python XML parsers do not restrict external entities by default, leading to potential denial of service or information disclosure.
**Prevention:** Always use `defusedxml.ElementTree` instead of `xml.etree.ElementTree` when parsing untrusted XML data to mitigate these risks. Ensure the `defusedxml` package is included in `functions/requirements.txt`.
