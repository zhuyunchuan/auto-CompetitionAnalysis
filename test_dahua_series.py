#!/usr/bin/env python3
"""
Test fetching WizSense 3 series page to find products.
"""

import httpx
from bs4 import BeautifulSoup
import re

def test_series_page():
    """Test fetching series page."""
    url = "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series"

    print(f"Fetching: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.content)}")

        # Save to file
        with open('/tmp/dahua_wizsense3.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("✓ Saved to /tmp/dahua_wizsense3.html")

        soup = BeautifulSoup(response.text, 'lxml')

        # Look for products
        print("\n=== Looking for products ===")

        # Try different patterns
        patterns = [
            ('div[class*="product"]', soup.find_all('div', class_=lambda x: x and 'product' in str(x).lower())),
            ('a[class*="product"]', soup.find_all('a', class_=lambda x: x and 'product' in str(x).lower())),
            ('div[class*="item"]', soup.find_all('div', class_=lambda x: x and 'item' in str(x).lower())),
            ('table tr', soup.find_all('tr')),
            ('div[class*="list"]', soup.find_all('div', class_=lambda x: x and 'list' in str(x).lower())),
        ]

        for pattern_name, elems in patterns:
            if elems:
                print(f"\n{pattern_name}: {len(elems)} elements")
                for i, elem in enumerate(elems[:3]):
                    text = elem.get_text(strip=True)[:100]
                    link = elem.find('a') if elem.name != 'a' else elem
                    href = link.get('href', '') if link else ''
                    print(f"  {i+1}. {text}")
                    if href:
                        print(f"     -> {href[:80]}")

        # Look for model numbers
        print("\n=== Looking for model numbers ===")
        model_pattern = re.compile(r'\b[A-Z]{2,4}-?\d{4}[A-Z0-9-]*\b')
        models = model_pattern.findall(response.text)

        unique_models = sorted(set(models))
        print(f"Found {len(unique_models)} unique model patterns:")
        for model in unique_models[:20]:
            print(f"  - {model}")

        # Look for product detail links
        print("\n=== Looking for product detail links ===")
        links = soup.find_all('a', href=True)
        product_links = []
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            # Look for product detail pages
            if any(pattern in href for pattern in ['/products/', 'detail']):
                if text and len(text) > 3:
                    product_links.append({
                        'text': text,
                        'href': href
                    })

        print(f"Found {len(product_links)} product links")
        for link in product_links[:15]:
            print(f"  [{link['text'][:60]}]({link['href'][:80]})")

        # Look for table structure
        print("\n=== Looking for tables ===")
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables")
        for i, table in enumerate(tables):
            print(f"\nTable {i+1}:")
            rows = table.find_all('tr')
            print(f"  Rows: {len(rows)}")
            if rows:
                # Get header row
                headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
                print(f"  Headers: {headers[:5]}")
                # Get first data row
                if len(rows) > 1:
                    cells = [td.get_text(strip=True) for td in rows[1].find_all(['td', 'th'])]
                    print(f"  First row: {cells[:5]}")

if __name__ == "__main__":
    test_series_page()
