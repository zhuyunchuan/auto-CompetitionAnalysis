#!/usr/bin/env python3
"""
Collect Hikvision Value series products using the JSON API.
"""

import sqlite3
import time
import sys
from datetime import datetime

sys.path.insert(0, ".")
from src.adapters.hikvision_adapter import HikvisionAdapter

DB_PATH = "data/db/competition.db"
RUN_ID = "20260420_hikvision_value"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Initialize adapter with Value series in allowlist
    adapter = HikvisionAdapter(
        series_l1_allowlist=["Value"],
        use_playwright=False  # Use JSON API instead
    )

    print(f"=== Hikvision Value Series Collection ===")

    # Discover series
    series_list = adapter.discover_series()
    print(f"Discovered series: {series_list}")

    if not series_list:
        print("No series discovered!")
        adapter.close()
        conn.close()
        return

    total_products = 0
    total_new = 0

    # Collect products from each series
    for series_l1 in series_list:
        print(f"\n--- Processing {series_l1} ---")

        # Discover subseries
        subseries_list = adapter.discover_subseries(series_l1)
        print(f"Subseries: {subseries_list}")

        for series_l2 in subseries_list:
            print(f"  Collecting products for {series_l1} / {series_l2}...")

            # List products
            products = adapter.list_products(series_l1, series_l2)
            print(f"    Found {len(products)} products")

            # Insert into database
            for product in products:
                # Check if already exists
                cur.execute("""
                    SELECT 1 FROM product_catalog
                    WHERE brand = 'hikvision' AND product_model = ?
                """, (product.model,))
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
                    RUN_ID, "hikvision", series_l1, series_l2,
                    product.model, product.name, product.url, product.locale,
                    "active", now, now
                ))

                total_new += 1

            total_products += len(products)
            conn.commit()

        # Rate limiting between series
        time.sleep(2)

    # Verify results
    print("\n=== Verification ===")
    cur.execute("""
        SELECT brand, series_l1, COUNT(DISTINCT product_model) as products
        FROM product_catalog
        WHERE brand = 'hikvision'
        GROUP BY brand, series_l1
        ORDER BY series_l1
    """)
    print("Products by series:")
    for row in cur.fetchall():
        print(f"  {row[0]} | {row[1]}: {row[2]} products")

    cur.execute("""
        SELECT COUNT(DISTINCT product_model)
        FROM product_catalog
        WHERE brand = 'hikvision'
    """)
    total_hikvision = cur.fetchone()[0]
    print(f"\nTotal Hikvision products: {total_hikvision}")
    print(f"New products added: {total_new}")

    # Cleanup
    adapter.close()
    conn.close()

    print(f"\nCollection complete. Results saved to {DB_PATH}")

if __name__ == "__main__":
    main()
