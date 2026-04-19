#!/usr/bin/env python3
"""
Collect products from ALL Dahua series, not just WizSense 2 and 3.

Available series:
- wizsense-2-series (already collected)
- wizsense-3-series (already collected)
- wizmind-5-series
- wizmind-7-series
- wizmind-8-series
- wizmind-panoramic-series
- special-series
"""

import sqlite3
import time
import sys
from datetime import datetime

sys.path.insert(0, ".")
from src.adapters.dahua_adapter import DahuaAdapter
from src.core.types import CatalogItem

DB_PATH = "data/db/competition.db"
RUN_ID = "20260420_all_dahua_series"
SLEEP_INTERVAL = 3  # seconds between requests

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Initialize adapter
    adapter = DahuaAdapter(use_playwright=True)

    # All available series slugs
    all_series = [
        "special-series",
        "wizmind-5-series",
        "wizmind-7-series",
        "wizmind-8-series",
        "wizmind-panoramic-series",
        # WizSense 2 and 3 already collected
    ]

    print(f"=== Dahua All Series Collection ===")
    print(f"Target series: {len(all_series)} new series")
    print(f"Series: {all_series}")
    print()

    # Map slugs to display names
    slug_to_name = {
        "special-series": "Special Series",
        "wizmind-5-series": "WizMind 5 Series",
        "wizmind-7-series": "WizMind 7 Series",
        "wizmind-8-series": "WizMind 8 Series",
        "wizmind-panoramic-series": "WizMind Panoramic Series",
    }

    total_products = 0
    total_new = 0

    for series_slug in all_series:
        series_name = slug_to_name.get(series_slug, series_slug)
        print(f"\n--- Processing {series_name} ---")

        # Build series URL
        series_url = f"{adapter.BASE_URL}/products/network-products/network-cameras/{series_slug}"
        print(f"URL: {series_url}")

        # Discover subseries by clicking tabs (try Playwright first, then httpx)
        tabs_html = {}
        try:
            from src.adapters.dahua_adapter import _playwright_get_with_filters
            tabs_html = _playwright_get_with_filters(series_url, wait_ms=2000)
        except Exception as e:
            print(f"  Playwright failed: {e}, falling back to httpx...")

        # If Playwright failed or returned no tabs, use httpx
        if not tabs_html:
            try:
                html = adapter.http_client.get(series_url)
                if html:
                    # Try to find subseries by parsing links
                    from bs4 import BeautifulSoup
                    import re

                    soup = BeautifulSoup(html, "lxml")
                    subseries = set()

                    # Look for subseries in URL patterns
                    for a in soup.find_all("a", href=True):
                        href = a.get("href", "")
                        match = re.search(r"/network-cameras/[\w-]+/([\w-]+)/(?:ipc|dh)", href, re.I)
                        if match:
                            sub = match.group(1)
                            subseries.add(sub.replace("-", " ").title())

                    if subseries:
                        print(f"  Found {len(subseries)} subseries via link parsing")
                        for sub in sorted(subseries):
                            tabs_html[sub] = html  # Use same HTML for all subseries
                    else:
                        # No subseries found, use default
                        tabs_html["default"] = html
            except Exception as e:
                print(f"  httpx also failed: {e}")
                continue

        if not tabs_html:
            print(f"  ERROR: Could not fetch page content")
            continue

        # Collect products from each subseries
        for subseries_name, html in tabs_html.items():
            print(f"  Subseries: {subseries_name}")

            # Parse products from HTML
            from bs4 import BeautifulSoup
            import re
            from urllib.parse import urljoin

            soup = BeautifulSoup(html, "lxml")
            products = []
            seen = set()

            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                match = re.search(
                    r"/network-cameras/[\w-]+/([\w-]+)/(ipc-[\w-]+|dh-[\w-]+)",
                    href, re.I,
                )
                if not match:
                    continue

                model_slug = match.group(2)
                model = model_slug.upper()

                if model in seen:
                    continue
                seen.add(model)

                product_url = urljoin(adapter.BASE_URL, href)
                products.append((model, product_url))

            print(f"    Found {len(products)} products")

            # Insert into database
            for model, url in products:
                # Check if already exists
                cur.execute("""
                    SELECT 1 FROM product_catalog
                    WHERE brand = 'dahua' AND product_model = ?
                """, (model,))
                if cur.fetchone():
                    continue

                # Insert new product
                now = datetime.now().isoformat()
                cur.execute("""
                    INSERT OR REPLACE INTO product_catalog
                    (run_id, brand, series_l1, series_l2, product_model, product_name,
                     product_url, locale, catalog_status, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    RUN_ID, "dahua", series_name, subseries_name, model, model,
                    url, "en", "active", now, now
                ))

                total_new += 1

            total_products += len(products)
            conn.commit()

        # Rate limiting between series
        time.sleep(SLEEP_INTERVAL)

    # Verify results
    print("\n=== Verification ===")
    cur.execute("""
        SELECT brand, series_l1, COUNT(DISTINCT product_model) as products
        FROM product_catalog
        WHERE brand = 'dahua'
        GROUP BY brand, series_l1
        ORDER BY series_l1
    """)
    print("Products by series:")
    for row in cur.fetchall():
        print(f"  {row[0]} | {row[1]}: {row[2]} products")

    cur.execute("""
        SELECT COUNT(DISTINCT product_model)
        FROM product_catalog
        WHERE brand = 'dahua'
    """)
    total_dahua = cur.fetchone()[0]
    print(f"\nTotal Dahua products: {total_dahua}")
    print(f"New products added: {total_new}")

    # Cleanup
    adapter.close()
    conn.close()

    print(f"\nCollection complete. Results saved to {DB_PATH}")

if __name__ == "__main__":
    main()
