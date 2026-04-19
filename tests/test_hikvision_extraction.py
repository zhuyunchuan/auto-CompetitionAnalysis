#!/usr/bin/env python3
"""
Hikvision Extraction Test

Test script for validating Hikvision product detail extraction.
Tests against a known good product page (DS-2CD2085G1-I).

Usage:
    python tests/test_hikvision_extraction.py

Expected Result:
    - 10/12 MVP fields successfully extracted (83.3%+)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.extractor.spec_extractor import SpecExtractor
from src.crawler.http_client import HttpClient


def test_hikvision_extraction():
    """Test Hikvision product detail extraction."""

    print("="*80)
    print("HIKVISION EXTRACTION TEST")
    print("="*80)

    # Test configuration
    url = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/DS-2CD2085G1-I/"
    model = "DS-2CD2085G1-I"
    expected_mvp_fields = 10  # Minimum threshold

    # Step 1: Fetch page
    print(f"\n[1/3] Fetching detail page...")
    print(f"Model: {model}")

    http_client = HttpClient(timeout_sec=30, retry_times=3)
    html = http_client.get(url)

    if not html:
        print("❌ Failed to fetch page")
        return False

    print(f"✓ Fetched {len(html)} bytes")

    # Step 2: Extract specifications
    print(f"\n[2/3] Extracting specifications...")
    extractor = SpecExtractor()
    results, warnings = extractor.extract_all_fields(html, source_url=url)

    success_fields = [f for f, r in results.items() if r.raw_value]
    print(f"✓ Extracted {len(success_fields)} fields")

    # Step 3: Validate MVP fields
    print(f"\n[3/3] Validating MVP 12 fields...")

    mvp_fields = [
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
        "approval_anti_corrosion_protection"
    ]

    mvp_success = 0
    for field in mvp_fields:
        result = results.get(field)
        if result and result.raw_value:
            mvp_success += 1
            print(f"  ✓ {field}")
        else:
            print(f"  ✗ {field}")

    # Summary
    print(f"\n{'='*80}")
    print(f"RESULT: {mvp_success}/12 MVP fields extracted ({mvp_success/12*100:.1f}%)")
    print(f"TARGET: {expected_mvp_fields}/12 ({expected_mvp_fields/12*100:.1f}%)")
    print(f"{'='*80}")

    if mvp_success >= expected_mvp_fields:
        print("\n✅ TEST PASSED\n")
        return True
    else:
        print(f"\n❌ TEST FAILED - Need {expected_mvp_fields - mvp_success} more fields\n")
        return False


if __name__ == "__main__":
    success = test_hikvision_extraction()
    sys.exit(0 if success else 1)
