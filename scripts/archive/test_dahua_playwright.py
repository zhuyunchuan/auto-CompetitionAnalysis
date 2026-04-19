#!/usr/bin/env python3
"""Quick test to verify DahuaAdapter with Playwright is working."""

import sys
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor

def main():
    print("=" * 60)
    print("Step 1: Testing DahuaAdapter with Playwright")
    print("=" * 60)

    a = DahuaAdapter(use_playwright=True)

    try:
        # Test 1: Discover series
        print("\n[Test 1] Discovering series...")
        series = a.discover_series()
        print(f"✓ Found {len(series)} series: {series}")

        if not series:
            print("✗ No series found, aborting test")
            return

        # Test 2: Discover subseries
        print(f"\n[Test 2] Discovering subseries for '{series[0]}'...")
        subs = a.discover_subseries(series[0])
        print(f"✓ Found {len(subs)} subseries: {subs[:3]}...")

        if not subs:
            print("✗ No subseries found, aborting test")
            return

        # Test 3: List products
        print(f"\n[Test 3] Listing products for '{series[0]}' / '{subs[0]}'...")
        prods = a.list_products(series[0], subs[0])
        print(f"✓ Found {len(prods)} products")
        if prods:
            print(f"  Sample: {prods[0].model} - {prods[0].url}")

        if not prods:
            print("✗ No products found, aborting test")
            return

        # Test 4: Fetch product detail
        print(f"\n[Test 4] Fetching detail page for '{prods[0].model}'...")
        html = a.fetch_product_detail(prods[0].url)
        print(f"✓ HTML length: {len(html)} chars")

        if len(html) < 1000:
            print("✗ HTML too short, might be error page")
            return

        # Test 5: Extract specs
        print(f"\n[Test 5] Extracting specs from '{prods[0].model}'...")
        ext = SpecExtractor()
        results, _ = ext.extract_all_fields(html, prods[0].url)

        hit = sum(1 for r in results.values() if r.raw_value)
        total = len(results)
        print(f"✓ Extracted {hit}/{total} fields")

        if hit > 0:
            print("\n  Sample extracted fields:")
            for field_code, record in list(results.items())[:5]:
                if record.raw_value:
                    print(f"    - {field_code}: {record.raw_value[:50]}...")

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - Playwright is working!")
        print("=" * 60)

    finally:
        a.close()
        print("\nBrowser closed.")

if __name__ == "__main__":
    main()
