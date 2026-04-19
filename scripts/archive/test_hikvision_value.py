#!/usr/bin/env python3
"""Test Hikvision adapter with Value series using Playwright."""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.hikvision_adapter import HikvisionAdapter


def test_value_series():
    """Test Hikvision adapter to discover and list Value series products."""
    print("Testing Hikvision adapter with Value series...")
    print("=" * 60)

    adapter = HikvisionAdapter(use_playwright=True)

    try:
        # Discover series
        print("\n1. Discovering series...")
        series = adapter.discover_series()
        print(f"   Found {len(series)} series: {series}")

        if "Value" not in series:
            print("   WARNING: 'Value' series not found, trying partial match...")
            value_series = [s for s in series if "value" in s.lower()]
            if value_series:
                print(f"   Found matching series: {value_series}")
                target_series = value_series[0]
            else:
                print("   ERROR: No Value series found!")
                return []
        else:
            target_series = "Value"

        # Discover subseries
        print(f"\n2. Discovering subseries for {target_series}...")
        subseries = adapter.discover_subseries(target_series)
        print(f"   Found {len(subseries)} subseries: {subseries}")

        # List products for each subseries
        print(f"\n3. Listing products for {target_series}...")
        all_products = []
        for sub in subseries:
            print(f"   Fetching products for subseries: {sub}")
            products = adapter.list_products(target_series, sub)
            print(f"   Found {len(products)} products")
            all_products.extend(products)
            time.sleep(1)  # Rate limiting

        # Print all models
        print(f"\n4. All products found ({len(all_products)} total):")
        print("-" * 60)
        for i, p in enumerate(all_products, 1):
            print(f"   {i}. {p.model} - {p.name}")
            print(f"      URL: {p.url}")

        # Verify we got at least 10 products
        if len(all_products) >= 10:
            print(f"\n✓ SUCCESS: Found {len(all_products)} products (target: 10+)")
            return all_products
        else:
            print(f"\n✗ FAILURE: Only found {len(all_products)} products (target: 10+)")
            return all_products

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        adapter.close()


if __name__ == "__main__":
    products = test_value_series()
    print(f"\nTest complete. Total products: {len(products)}")
