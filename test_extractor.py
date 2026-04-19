#!/usr/bin/env python3
"""
Test the fixed spec_extractor on Hikvision product page.
"""

import sys
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.extractor.spec_extractor import SpecExtractor
import httpx

def test_extraction():
    """Test extraction on a real Hikvision product page."""

    url = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/DS-2CD2085G1-I/"

    print(f"Fetching: {url}")
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    html = response.text

    # Create extractor
    extractor = SpecExtractor()

    # Extract all fields
    results, warnings = extractor.extract_all_fields(html, url)

    # Check the 12 core fields
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

    print("\n=== Extraction Results ===")
    print(f"Warnings: {len(warnings)}")
    for warning in warnings:
        print(f"  - {warning}")

    success_count = 0
    for field_code in core_fields:
        if field_code in results:
            result = results[field_code]
            if result.raw_value:
                success_count += 1
                print(f"\n✅ {field_code}:")
                print(f"   Raw: {result.raw_value[:100]}{'...' if len(result.raw_value) > 100 else ''}")
                print(f"   Normalized: {result.normalized_value[:100] if result.normalized_value else 'N/A'}{'...' if result.normalized_value and len(result.normalized_value) > 100 else ''}")
                print(f"   Confidence: {result.confidence} ({result.extraction_method})")
            else:
                print(f"\n❌ {field_code}: NOT FOUND")
                print(f"   Method: {result.extraction_method}")
                if result.issues:
                    for issue in result.issues:
                        print(f"   Issue: {issue}")
        else:
            print(f"\n❌ {field_code}: NOT IN RESULTS")

    print(f"\n=== Summary ===")
    print(f"Success: {success_count}/{len(core_fields)} fields extracted")
    print(f"Target: At least 10/12 fields should be extracted")

    # Convert to SpecRecord list
    spec_records = extractor.to_spec_records(
        results,
        run_id="test_001",
        brand="hikvision",
        series_l1="Pro",
        series_l2="EasyIP",
        model="DS-2CD2085G1-I"
    )

    print(f"\n=== SpecRecord Conversion ===")
    print(f"Generated {len(spec_records)} SpecRecord objects")

    for record in spec_records[:5]:
        print(f"  - {record.field_code}: {record.normalized_value[:50]}...")

    return success_count >= 10

if __name__ == "__main__":
    success = test_extraction()
    if success:
        print("\n✅ Test PASSED: At least 10/12 fields extracted")
        sys.exit(0)
    else:
        print("\n❌ Test FAILED: Less than 10/12 fields extracted")
        sys.exit(1)
