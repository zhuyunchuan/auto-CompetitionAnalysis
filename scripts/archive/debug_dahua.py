#!/usr/bin/env python3
"""Debug Dahua adapter to understand why no products are found."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.dahua_adapter import DahuaAdapter


def debug_dahua():
    """Debug Dahua adapter step by step."""
    print("\n" + "="*80)
    print("DAHUA ADAPTER DEBUG")
    print("="*80)

    adapter = DahuaAdapter(use_playwright=False)  # Disable Playwright to avoid crashes

    try:
        # Step 1: Discover series
        print("\n[STEP 1] Discovering series from entry page...")
        print(f"Entry URL: {adapter.ENTRY_URL}")

        html = adapter._fetch(adapter.ENTRY_URL)
        print(f"Fetched HTML length: {len(html)} chars")

        series = adapter.discover_series()
        print(f"Discovered series: {series}")
        print(f"Series URLs: {adapter._series_urls}")

        # Step 2: Check WizSense 3 URL
        target_series = "WizSense 3 Series"
        if target_series in adapter._series_urls:
            series_url = adapter._series_urls[target_series]
            print(f"\n[STEP 2] {target_series} URL: {series_url}")

            # Fetch the series page
            print(f"Fetching series page...")
            series_html = adapter._fetch(series_url)
            print(f"Fetched HTML length: {len(series_html)} chars")

            # Save a sample of the HTML
            sample_file = Path("results/dahua_wizsense3_page_sample.html")
            sample_file.parent.mkdir(exist_ok=True)
            with open(sample_file, "w") as f:
                f.write(series_html[:10000])  # First 10KB
            print(f"Saved first 10KB to: {sample_file}")

            # Try to find product links
            from bs4 import BeautifulSoup
            import re

            soup = BeautifulSoup(series_html, "lxml")

            # Find all links
            all_links = soup.find_all("a", href=True)
            print(f"\n[STEP 3] Found {len(all_links)} total links")

            # Look for product links matching the pattern
            product_links = []
            for a in all_links:
                href = a.get("href", "")
                match = re.search(
                    r"/network-cameras/[\w-]+/([\w-]+)/(ipc-[\w-]+|dh-[\w-]+)",
                    href, re.I,
                )
                if match:
                    product_links.append({
                        "href": href,
                        "model_slug": match.group(2),
                        "text": a.get_text(strip=True)[:50],
                    })

            print(f"Found {len(product_links)} product links")

            if product_links:
                print("\nFirst 10 product links:")
                for i, link in enumerate(product_links[:10], 1):
                    print(f"  {i}. {link['model_slug']} - {link['text']}")
                    print(f"     href: {link['href'][:100]}")
            else:
                print("\nNo product links found. Let's check all href patterns...")
                href_patterns = set()
                for a in all_links[:50]:
                    href = a.get("href", "")
                    if "/network-cameras/" in href:
                        pattern = href.split("/network-cameras/")[1].split("/")[0] if "/" in href else href
                        href_patterns.add(pattern)

                print(f"URL patterns found: {list(href_patterns)[:20]}")

        else:
            print(f"\n[STEP 2] ERROR: {target_series} not in _series_urls")

        # Step 3: Try list_products directly
        print(f"\n[STEP 4] Trying list_products() directly...")
        products = adapter.list_products(target_series, target_series)
        print(f"list_products returned: {len(products)} products")

        if products:
            print("\nFirst 5 products:")
            for i, p in enumerate(products[:5], 1):
                print(f"  {i}. {p.model} - {p.url}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        adapter.close()


if __name__ == "__main__":
    debug_dahua()
