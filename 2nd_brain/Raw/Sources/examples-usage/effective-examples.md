---
Title: "Effective Use of Code Examples"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-09-13
Processed: true
tags: ["source", "examples", "methodology"]
---

# Effective Use of Code Examples

## When to Copy vs Adapt vs Rewrite

| Situation | Action | Why |
|-----------|--------|-----|
| Exact match to need | Copy | Time efficiency |
| Similar but different context | Adapt | Maintain correctness |
| Complex/legacy code | Rewrite | Understand and improve |
| Learning exercise | Type manually | Build muscle memory |

## Understanding Context

Before using an example, check:
1. **Language version** — is it compatible with your version?
2. **Dependencies** — are they available in your environment?
3. **Scale** — does it work for your data size?
4. **Security** — does it have vulnerabilities?
5. **License** — can you use it in your project?

## Adapting Examples

### Step 1: Identify the Core Logic
```python
# Original: web scraping
import requests
from bs4 import BeautifulSoup

url = "https://example.com"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')
titles = soup.find_all('h2')
```

### Step 2: Adapt to Your Needs
```python
# Adapted: with error handling and specific extraction
import requests
from bs4 import BeautifulSoup

def fetch_titles(url: str) -> list[str]:
    """Fetch all h2 titles from a webpage."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    return [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
```

### Step 3: Test Before Production
```python
# Test with your actual data
titles = fetch_titles("https://your-actual-url.com")
assert isinstance(titles, list)
assert all(isinstance(t, str) for t in titles)
```

## Common Pitfalls

1. **Not handling edge cases** — examples often skip error handling
2. **Outdated dependencies** — check version compatibility
3. **Hardcoded values** — extract to configuration
4. **No tests** — add tests for adapted code
5. **Security holes** — review for injection, auth issues

## Citing Sources

When using examples from documentation or tutorials:

```python
# Based on: Python docs — pathlib usage
# Source: https://docs.python.org/3/library/pathlib.html
# Adapted for: batch file processing with error handling
from pathlib import Path
```

## Building a Personal Example Library

Organize examples by:
```
examples/
├── web-scraping/
│   ├── basic-fetch.py
│   ├── with-login.py
│   └── rate-limited.py
├── data-processing/
│   ├── csv-transform.py
│   ├── json-normalize.py
│   └── parallel-process.py
└── api/
    ├── rest-client.py
    ├── graphql.py
    └── websocket.py
```
