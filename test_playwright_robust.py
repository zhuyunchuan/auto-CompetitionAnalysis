#!/usr/bin/env python3
"""
Robust Playwright test with better error handling.
"""

from playwright.sync_api import sync_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup
import time

def test_playwright_fetch(url: str, output_file: str):
    """Fetch page with Playwright."""
    print(f"\nFetching with Playwright: {url}")
    print(f"Output: {output_file}")

    try:
        with sync_playwright() as p:
            # Try with different launch options
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )

            page = context.new_page()

            print("Navigating to page...")
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                print("✓ Page loaded (domcontentloaded)")
            except PlaywrightError as e:
                print(f"⚠ Warning: {e}")
                print("  Continuing anyway...")

            # Wait for content to load
            print("Waiting for dynamic content...")
            time.sleep(5)

            # Try to wait for specific elements
            try:
                page.wait_for_selector('text=WizSense', timeout=10000)
                print("✓ Found 'WizSense' text")
            except:
                print("⚠ Timeout waiting for WizSense text")

            # Get HTML
            html = page.content()

            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✓ Saved HTML ({len(html)} bytes)")

            browser.close()
            return html

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_wizsense3():
    """Fetch and analyze WizSense 3 series page."""
    url = "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series"
    html = test_playwright_fetch(url, '/tmp/wizsense3_playwright.html')

    if not html:
        print("Failed to fetch page")
        return

    print("\n=== Analyzing page ===")
    soup = BeautifulSoup(html, 'lxml')

    # Look for products
    import re

    # Look for model numbers
    print("\n=== Model numbers ===")
    model_pattern = re.compile(r'\b(?:IPC|SD|NVR|HCVR|XVR|DHI)[A-Z0-9-]{4,}\b')
    models = model_pattern.findall(html)
    unique_models = sorted(set(models))
    print(f"Found {len(unique_models)} unique models:")
    for model in unique_models[:20]:
        print(f"  - {model}")

    # Look for product cards/links
    print("\n=== Product elements ===")
    product_divs = soup.find_all(['div', 'a'], class_=lambda x: x and any(kw in str(x).lower() for kw in ['product', 'item', 'card', 'model']))
    print(f"Found {len(product_divs)} product-related elements")

    for i, elem in enumerate(product_divs[:10]):
        text = elem.get_text(strip=True)[:100]
        href = elem.get('href', '') if elem.name == 'a' else ''
        if href:
            link = elem.find('a')
            if link:
                href = link.get('href', '')
        print(f"  {i+1}. {text}")
        if href:
            print(f"     -> {href[:80]}")

    # Look for all links in the main content
    print("\n=== All links from main content ===")
    main_content = soup.find('div', class_='products-right') or soup.find('main') or soup.body
    if main_content:
        links = main_content.find_all('a', href=True)
        print(f"Found {len(links)} links in main content")

        # Filter for potential product links
        product_links = []
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            # Look for links that might be products
            if text and len(text) > 3:
                if any(kw in href.lower() for kw in ['detail', 'product', 'model']):
                    product_links.append((text, href))

        print(f"Found {len(product_links)} potential product links:")
        for text, href in product_links[:15]:
            print(f"  [{text[:60]}]({href[:80]})")


if __name__ == "__main__":
    analyze_wizsense3()
