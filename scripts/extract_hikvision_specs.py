#!/usr/bin/env python3
"""
Extract specs for Hikvision Value series products.
"""

import sqlite3
import time
import sys
from datetime import datetime

sys.path.insert(0, ".")
from src.adapters.hikvision_adapter import HikvisionAdapter
from src.extractor.spec_extractor import SpecExtractor
from src.extractor.field_registry import FieldRegistry

DB_PATH = "data/db/competition.db"
RUN_ID = "20260420_hikvision_value"
SLEEP_INTERVAL = 2  # seconds between requests

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all Hikvision products
    cur.execute("""
        SELECT product_model, product_url, brand, series_l1, series_l2
        FROM product_catalog
        WHERE brand = 'hikvision'
        ORDER BY product_model
    """)
    all_products = cur.fetchall()

    # Find products without specs
    cur.execute("SELECT DISTINCT product_model FROM product_specs_long WHERE brand='hikvision'")
    done_models = set(r[0] for r in cur.fetchall())

    todo = [(m, u, b, s1, s2) for m, u, b, s1, s2 in all_products if m not in done_models]

    print(f"=== Hikvision Value Series Specs Extraction ===")
    print(f"Total products: {len(all_products)}")
    print(f"Already extracted: {len(done_models)}")
    print(f"Remaining to extract: {len(todo)}")
    print()

    if not todo:
        print("No remaining products to extract!")
        conn.close()
        return

    # Initialize adapter and extractor
    adapter = HikvisionAdapter(use_playwright=False)  # Use httpx for detail pages
    extractor = SpecExtractor()
    field_registry = FieldRegistry()

    now = datetime.now().isoformat()
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, (model, url, brand, s1, s2) in enumerate(todo):
        print(f"[{i+1}/{len(todo)}] {model}...", end=" ", flush=True)

        try:
            # Fetch product detail page
            html = adapter.fetch_product_detail(url)

            if len(html) < 2000:
                print(f"SKIP (HTML too short: {len(html)} bytes)")
                skip_count += 1
                continue

            # Extract all fields
            results, _ = extractor.extract_all_fields(html, url)

            # Count successful extractions
            hit_count = sum(1 for r in results.values() if r.raw_value)
            print(f"{hit_count}/12 fields")

            # Insert into database
            for code, result in results.items():
                if result.raw_value:
                    field_info = field_registry._FIELDS.get(code)
                    field_name = field_info.field_name if field_info else code

                    cur.execute("""
                        INSERT OR REPLACE INTO product_specs_long
                        (run_id, brand, series_l1, series_l2, product_model, field_code, field_name,
                         raw_value, normalized_value, unit, value_type, source_url, extract_confidence,
                         is_manual_override, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        RUN_ID, brand, s1, s2, model, code, field_name,
                        result.raw_value, result.normalized_value or "", "", "text",
                        url, result.confidence, 0, now
                    ))

            success_count += 1

        except Exception as e:
            print(f"ERROR: {e}")
            error_count += 1

        # Rate limiting
        time.sleep(SLEEP_INTERVAL)

        # Periodic commit
        if (i + 1) % 10 == 0:
            conn.commit()
            print(f"  → Committed at {i+1} products")

    # Final commit
    conn.commit()

    # Verify results
    print("\n=== Verification ===")
    cur.execute("SELECT COUNT(DISTINCT product_model) FROM product_specs_long WHERE brand='hikvision'")
    total_with_specs = cur.fetchone()[0]
    print(f"Products with specs: {total_with_specs}")

    cur.execute("SELECT COUNT(*) FROM product_specs_long WHERE brand='hikvision'")
    total_records = cur.fetchone()[0]
    print(f"Total spec records: {total_records}")

    print(f"\n=== Summary ===")
    print(f"Successfully extracted: {success_count}")
    print(f"Skipped (short HTML): {skip_count}")
    print(f"Errors: {error_count}")

    # Cleanup
    adapter.close()
    conn.close()

    print(f"\nExtraction complete. Results saved to {DB_PATH}")

if __name__ == "__main__":
    main()
