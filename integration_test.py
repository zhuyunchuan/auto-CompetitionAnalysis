#!/usr/bin/env python3
"""
Integration test for Hikvision scraper.
Tests the complete flow from series discovery to spec extraction.
"""

import sys
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.adapters.hikvision_adapter import HikvisionAdapter
from src.extractor.spec_extractor import SpecExtractor
from src.crawler.http_client import HttpClient

def test_hikvision_complete_flow():
    """Test complete Hikvision scraping flow."""

    print("="*80)
    print("HIKVISION INTEGRATION TEST")
    print("="*80)

    # Initialize adapter
    http_client = HttpClient(timeout_sec=30, retry_times=3, min_delay_ms=500, max_delay_ms=1000)
    adapter = HikvisionAdapter(http_client=http_client)
    extractor = SpecExtractor()

    run_id = "test_20260418"

    # Step 1: Discover series
    print("\n[Step 1] Discovering L1 series...")
    series_list = adapter.discover_series()
    print(f"✓ Found {len(series_list)} series: {series_list[:5]}...")

    if not series_list:
        print("✗ No series found, aborting test")
        return False

    # Test with Pro series (known to have products)
    test_series = "Pro" if "Pro" in series_list else series_list[0]
    print(f"\n[Step 2] Testing with series: {test_series}")

    # Step 2: Discover subseries
    print(f"\n[Step 3] Discovering L2 subseries for {test_series}...")
    subseries_list = adapter.discover_subseries(test_series)
    print(f"✓ Found {len(subseries_list)} subseries: {subseries_list}")

    if not subseries_list:
        print("✗ No subseries found, aborting test")
        return False

    # Test with first subseries
    test_subseries = subseries_list[0]
    print(f"\n[Step 4] Testing with subseries: {test_subseries}")

    # Step 3: List products
    print(f"\n[Step 5] Listing products for {test_series} / {test_subseries}...")
    products = adapter.list_products(test_series, test_subseries)
    print(f"✓ Found {len(products)} products")

    if not products:
        print("✗ No products found, aborting test")
        return False

    # Test with first product
    test_product = products[0]
    print(f"\n[Step 6] Testing with product: {test_product.model}")
    print(f"  URL: {test_product.url}")

    # Step 4: Fetch product detail
    print(f"\n[Step 7] Fetching product detail HTML...")
    html = adapter.fetch_product_detail(test_product.url)

    if not html:
        print("✗ Failed to fetch product detail")
        return False

    print(f"✓ Fetched {len(html)} bytes of HTML")

    # Step 5: Extract specifications
    print(f"\n[Step 8] Extracting specifications...")
    extraction_results, warnings = extractor.extract_all_fields(html, test_product.url)

    # Check 12 core fields
    core_fields = [
        "image_sensor",
        "max_resolution",
        "lens_type",
        "aperture",
        "supplement_light_type",
        "supplement_light_range",
        "main_stream_max_fps_resolution",
        "stream_count",
        "interface_items",
        "deep_learning_function_categories",
        "approval_protection",
        "approval_anti_corrosion_protection",
    ]

    print(f"\n[Step 9] Checking {len(core_fields)} core fields...")

    success_count = 0
    for field_code in core_fields:
        if field_code in extraction_results and extraction_results[field_code].raw_value:
            success_count += 1
            result = extraction_results[field_code]
            print(f"  ✓ {field_code}: {result.raw_value[:60]}{'...' if len(result.raw_value) > 60 else ''}")
        else:
            print(f"  ✗ {field_code}: NOT FOUND")

    print(f"\n[Step 10] Summary: {success_count}/{len(core_fields)} fields extracted")

    # Convert to SpecRecord
    print(f"\n[Step 11] Converting to SpecRecord format...")
    spec_records = extractor.to_spec_records(
        extraction_results,
        run_id=run_id,
        brand=test_product.brand,
        series_l1=test_product.series_l1,
        series_l2=test_product.series_l2,
        model=test_product.model
    )

    print(f"✓ Generated {len(spec_records)} SpecRecord objects")

    # Print sample records
    print(f"\n[Step 12] Sample records:")
    for record in spec_records[:5]:
        print(f"  - {record.field_code}: {record.normalized_value[:50]}{'...' if len(record.normalized_value) > 50 else ''}")

    # Final verdict
    print(f"\n{'='*80}")
    print("TEST RESULTS")
    print(f"{'='*80}")
    print(f"Series discovered: {len(series_list)}")
    print(f"Subseries discovered: {len(subseries_list)}")
    print(f"Products found: {len(products)}")
    print(f"Fields extracted: {success_count}/{len(core_fields)}")
    print(f"SpecRecords generated: {len(spec_records)}")

    if success_count >= 10:
        print(f"\n✅ TEST PASSED: At least 10/12 fields extracted successfully")
        return True
    else:
        print(f"\n❌ TEST FAILED: Less than 10/12 fields extracted")
        return False

if __name__ == "__main__":
    success = test_hikvision_complete_flow()
    sys.exit(0 if success else 1)
