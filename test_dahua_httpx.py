#!/usr/bin/env python3
"""
Test what httpx can fetch from Dahua.
"""

import httpx
from bs4 import BeautifulSoup

def test_httpx_fetch():
    """Test fetching with httpx."""
    url = "https://www.dahuasecurity.com/products/network-products/network-cameras"

    print(f"Fetching with httpx: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.content)}")

        soup = BeautifulSoup(response.text, 'lxml')

        # Save to file
        with open('/tmp/dahua_httpx.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("✓ Saved to /tmp/dahua_httpx.html")

        # Look for product items
        print("\n--- Looking for product items ---")
        items = soup.find_all(['div', 'a'], class_=lambda x: x and 'product' in x.lower())
        print(f"Found {len(items)} elements with 'product' in class")

        for i, item in enumerate(items[:5]):
            print(f"\nItem {i+1}:")
            print(f"  Tag: {item.name}")
            print(f"  Class: {item.get('class')}")
            text = item.get_text(strip=True)[:150]
            print(f"  Text: {text}")

        # Look for headings
        print("\n--- Looking for headings ---")
        headings = soup.find_all(['h1', 'h2', 'h3'])
        print(f"Found {len(headings)} headings")
        for h in headings[:10]:
            text = h.get_text(strip=True)
            if any(kw in text.lower() for kw in ['wizsense', 'series', 'camera']):
                print(f"  {h.name}: {text}")

        # Look for links
        print("\n--- Looking for links ---")
        links = soup.find_all('a', href=True)
        product_links = [l for l in links if any(kw in l.get('href', '').lower() for kw in ['product', 'series', 'camera'])]
        print(f"Found {len(product_links)} product-related links")
        for link in product_links[:10]:
            href = link.get('href', '')[:80]
            text = link.get_text(strip=True)[:80]
            print(f"  [{text}]({href})")

if __name__ == "__main__":
    test_httpx_fetch()
