#!/usr/bin/env python3
"""
Test script to analyze Dahua page structure using Playwright.

This script fetches the main page and analyzes the DOM structure
to find the correct selectors for series, subseries, and products.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import time


def analyze_page_structure(url: str):
    """Fetch and analyze page structure."""
    print(f"\n{'='*80}")
    print(f"Analyzing: {url}")
    print(f"{'='*80}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print("Loading page...")
        try:
            # Try with different wait strategies
            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            print(f"✓ Page loaded, status: {response.status if response else 'unknown'}")
        except Exception as e:
            print(f"⚠ Warning during page load: {e}")
            print("  Continuing anyway...")

        # Wait for dynamic content
        print("Waiting for dynamic content...")
        try:
            page.wait_for_load_state('domcontentloaded', timeout=10000)
        except:
            pass

        # Wait a bit for any delayed JS rendering
        time.sleep(5)

        html = page.content()
        soup = BeautifulSoup(html, 'lxml')

        # Save raw HTML for inspection
        with open('/tmp/dahua_main_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ Saved HTML to /tmp/dahua_main_page.html")

        # Analyze structure
        print("\n--- Page Structure Analysis ---\n")

        # Look for product items/series cards
        print("1. Looking for product items/series cards...")
        product_items = soup.find_all(['a', 'div'], class_=lambda x: x and 'product' in x.lower())
        print(f"   Found {len(product_items)} elements with 'product' in class")

        for i, item in enumerate(product_items[:5]):
            print(f"\n   Item {i+1}:")
            print(f"      Tag: {item.name}")
            print(f"      Class: {item.get('class')}")
            if item.name == 'a':
                print(f"      href: {item.get('href')}")
            title = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if title:
                print(f"      Title: {title.get_text(strip=True)[:100]}")

        # Look for series titles
        print("\n2. Looking for series titles (h1-h6)...")
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        print(f"   Found {len(headings)} headings")

        series_keywords = ['wizsense', 'series', 'camera', 'network']
        for h in headings[:10]:
            text = h.get_text(strip=True)
            if any(kw in text.lower() for kw in series_keywords):
                print(f"   - {h.name}: {text[:100]}")

        # Look for links to product pages
        print("\n3. Looking for product links...")
        links = soup.find_all('a', href=True)
        product_links = []
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            # Look for links that might be products
            if any(kw in href.lower() for kw in ['product', 'series', 'camera']):
                if text and len(text) > 3:
                    product_links.append({
                        'text': text[:100],
                        'href': href[:100],
                        'class': link.get('class', [])
                    })

        print(f"   Found {len(product_links)} potential product/series links")
        for i, link in enumerate(product_links[:10]):
            print(f"\n   Link {i+1}:")
            print(f"      Text: {link['text']}")
            print(f"      href: {link['href']}")
            print(f"      Class: {link['class']}")

        # Look for any JavaScript data or JSON-LD
        print("\n4. Looking for JSON-LD or embedded data...")
        scripts = soup.find_all('script', type='application/ld+json')
        print(f"   Found {len(scripts)} JSON-LD scripts")

        for i, script in enumerate(scripts[:3]):
            try:
                data = json.loads(script.string)
                print(f"\n   JSON-LD {i+1}:")
                print(f"      {json.dumps(data, indent=2)[:500]}")
            except:
                pass

        # Look for data attributes
        print("\n5. Looking for elements with data-* attributes...")
        data_elems = soup.find_all(attrs={"data-series": True})
        print(f"   Found {len(data_elems)} elements with data-series")

        browser.close()

        print("\n✓ Analysis complete!")


def test_wizsense_series():
    """Test fetching WizSense 3 series page."""
    series_url = "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series"

    print(f"\n{'='*80}")
    print(f"Testing WizSense 3 Series Page")
    print(f"{'='*80}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print("Loading WizSense 3 series page...")
        try:
            response = page.goto(series_url, wait_until='domcontentloaded', timeout=60000)
            print(f"✓ Page loaded, status: {response.status if response else 'unknown'}")
        except Exception as e:
            print(f"⚠ Warning during page load: {e}")
            print("  Continuing anyway...")

        time.sleep(5)

        html = page.content()
        soup = BeautifulSoup(html, 'lxml')

        # Save for inspection
        with open('/tmp/dahua_wizsense3_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ Saved HTML to /tmp/dahua_wizsense3_page.html")

        # Look for products
        print("\n--- Looking for products ---\n")

        # Try different patterns
        patterns = [
            ('div.product-item', soup.find_all('div', class_=lambda x: x and 'product' in x.lower())),
            ('a.product-item', soup.find_all('a', class_=lambda x: x and 'product' in x.lower())),
            ('table tr', soup.find_all('tr')),
            ('div[class*="item"]', soup.find_all('div', class_=lambda x: x and 'item' in x.lower())),
        ]

        for pattern_name, elems in patterns:
            print(f"\nPattern '{pattern_name}': {len(elems)} elements")
            for i, elem in enumerate(elems[:3]):
                text = elem.get_text(strip=True)[:100]
                print(f"  {i+1}. {text}")

        # Look for model numbers
        print("\n--- Looking for model numbers ---\n")
        import re
        model_pattern = re.compile(r'\b[A-Z]{2,4}-?\d{4}[A-Z0-9-]*\b')
        models = model_pattern.findall(html)

        print(f"Found {len(set(models))} unique model patterns:")
        for model in sorted(set(models))[:10]:
            print(f"  - {model}")

        browser.close()


if __name__ == "__main__":
    # Analyze main page
    analyze_page_structure("https://www.dahuasecurity.com/products/network-products/network-cameras")

    # Test series page
    test_wizsense_series()

    print("\n" + "="*80)
    print("All tests complete!")
    print("="*80)
