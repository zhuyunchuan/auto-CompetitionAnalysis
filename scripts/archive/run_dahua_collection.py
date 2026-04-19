#!/usr/bin/env python3
"""
Dahua full collection script using httpx fallback.

Note: Playwright is currently crashing on dahuasecurity.com domain.
This script uses httpx which works successfully.
"""

import sys
import time
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor
from src.storage.db import Database
from src.storage.schema import ProductCatalog, ProductSpecLong
from datetime import datetime

def init_database():
    """Initialize database tables if they don't exist."""
    db = Database()
    db.init_db()
    return db

def save_catalog(db, products):
    """Save products to catalog table."""
    count = 0
    for product in products:
        try:
            db.insert_catalog(product)
            count += 1
        except Exception as e:
            # May be duplicate, that's ok
            pass
    return count

def save_specs(db, run_id, product, spec_records):
    """Save specification records to database."""
    count = 0
    for field_code, record in spec_records.items():
        if record.raw_value:
            try:
                db.insert_spec(
                    run_id=run_id,
                    brand=product.brand,
                    series_l1=product.series_l1,
                    series_l2=product.series_l2,
                    model=product.model,
                    field_code=field_code,
                    raw_value=record.raw_value,
                    normalized_value=record.normalized_value,
                    unit=record.unit,
                    source_url=product.url,
                    is_manual_override=False,
                )
                count += 1
            except Exception as e:
                print(f"    ✗ Failed to save {field_code}: {e}")
    return count

def main():
    print("=" * 80)
    print("Dahua Full Collection Script")
    print("=" * 80)

    # Initialize
    print("\n[1/5] Initializing database...")
    db = init_database()
    print("✓ Database ready")

    # Create adapter with httpx (playwright=False to avoid crashes)
    print("\n[2/5] Creating adapter (using httpx, Playwright disabled)...")
    adapter = DahuaAdapter(use_playwright=False)
    extractor = SpecExtractor()

    # Discover series
    print("\n[3/5] Discovering series...")
    series_list = adapter.discover_series()
    print(f"✓ Found {len(series_list)} series: {series_list}")

    if not series_list:
        print("✗ No series found, exiting")
        adapter.close()
        return

    # Collect all products
    print("\n[4/5] Collecting products...")
    all_products = []

    for series_l1 in series_list:
        print(f"\n  Processing {series_l1}...")

        # Discover subseries
        subseries_list = adapter.discover_subseries(series_l1)
        print(f"    Found {len(subseries_list)} subseries")

        for series_l2 in subseries_list:
            # List products
            products = adapter.list_products(series_l1, series_l2)
            print(f"    {series_l2}: {len(products)} products")
            all_products.extend(products)

    print(f"\n✓ Total products discovered: {len(all_products)}")

    if not all_products:
        print("✗ No products found, exiting")
        adapter.close()
        return

    # Save catalog
    print("\n[5/5] Extracting specs and saving to database...")
    run_id = datetime.now().strftime("%Y%m%d_manual_01")

    catalog_count = save_catalog(db, all_products)
    print(f"✓ Saved {catalog_count} products to catalog")

    # Extract specs for each product
    stats = {
        'total': len(all_products),
        'success': 0,
        'failed': 0,
        'fields_extracted': 0,
        'field_stats': {},
    }

    for i, product in enumerate(all_products, 1):
        print(f"\n  [{i}/{len(all_products)}] {product.model}...")

        try:
            # Fetch detail page
            html = adapter.fetch_product_detail(product.url)

            if not html or len(html) < 1000:
                print(f"    ✗ Page too short or empty ({len(html) if html else 0} chars)")
                stats['failed'] += 1
                time.sleep(2)
                continue

            # Extract specs
            spec_records, _ = extractor.extract_all_fields(html, product.url)

            # Count successful extractions
            hit = sum(1 for r in spec_records.values() if r.raw_value)
            stats['fields_extracted'] += hit

            # Update field stats
            for field_code, record in spec_records.items():
                if record.raw_value:
                    stats['field_stats'][field_code] = stats['field_stats'].get(field_code, 0) + 1

            # Save to database
            saved = save_specs(db, run_id, product, spec_records)

            print(f"    ✓ Extracted {hit}/{len(spec_records)} fields, saved {saved} records")
            stats['success'] += 1

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"    ✗ Failed: {e}")
            stats['failed'] += 1
            time.sleep(2)

    # Summary
    print("\n" + "=" * 80)
    print("Collection Summary")
    print("=" * 80)
    print(f"Run ID: {run_id}")
    print(f"Total products: {stats['total']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Success rate: {stats['success']/stats['total']*100:.1f}%")
    print(f"\nTotal fields extracted: {stats['fields_extracted']}")
    print(f"Average fields per product: {stats['fields_extracted']/stats['total']:.1f}")

    print("\nField extraction success rates:")
    for field_code in sorted(stats['field_stats'].keys()):
        count = stats['field_stats'][field_code]
        rate = count / stats['total'] * 100
        print(f"  {field_code}: {count}/{stats['total']} ({rate:.1f}%)")

    adapter.close()
    print("\n✓ Collection complete!")

if __name__ == "__main__":
    main()
