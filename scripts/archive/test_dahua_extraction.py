#!/usr/bin/env python3
"""Test Dahua field extraction with correct SpecExtractor API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.extractor.spec_extractor import SpecExtractor
from src.crawler.http_client import HttpClient


def test_dahua_extraction():
    """Test field extraction on existing Dahua products."""
    print("\n" + "="*80)
    print("DAHUA FIELD EXTRACTION TEST")
    print("="*80)

    # Get product URLs from database
    product_urls = [
        'https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hdbw3541e-led',
        'https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3542t',
    ]

    # 12 required fields
    required_fields = [
        'image_sensor',
        'max_resolution',
        'lens_type',
        'aperture',
        'supplement_light_type',
        'supplement_light_range',
        'main_stream_max_fps_resolution',
        'stream_count',
        'interface_items',
        'deep_learning_function_categories',
        'approval_protection',
        'approval_anti_corrosion_protection',
    ]

    extractor = SpecExtractor()
    client = HttpClient(timeout_sec=30, retry_times=3)

    all_results = []

    for i, url in enumerate(product_urls, 1):
        print(f"\n[Product {i}] {url}")
        print("-" * 80)

        # Fetch HTML
        html = client.get(url)
        if not html:
            print("  ✗ Failed to fetch HTML")
            continue

        print(f"  ✓ Fetched HTML: {len(html)} chars")

        # Extract all fields
        results, warnings = extractor.extract_all_fields(html, url)

        if warnings:
            print(f"  ⚠ Warnings: {warnings}")

        # Check required fields
        extracted_count = 0
        for field_code in required_fields:
            result = results.get(field_code)
            if result and result.confidence > 0:
                extracted_count += 1
                value_preview = result.raw_value[:60] if result.raw_value else "N/A"
                print(f"  ✓ {field_code}: {value_preview}...")
            else:
                print(f"  ✗ {field_code}: NOT FOUND (confidence={result.confidence if result else 0})")

        success_rate = extracted_count / len(required_fields)
        print(f"\n  Summary: {extracted_count}/{len(required_fields)} fields ({success_rate*100:.1f}%)")

        all_results.append({
            "url": url,
            "extracted": extracted_count,
            "total": len(required_fields),
            "rate": success_rate
        })

    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)

    avg_rate = sum(r["rate"] for r in all_results) / len(all_results) if all_results else 0
    avg_extracted = sum(r["extracted"] for r in all_results) / len(all_results) if all_results else 0

    print(f"Tested {len(all_results)} products")
    print(f"Average extraction rate: {avg_extracted:.1f}/{len(required_fields)} ({avg_rate*100:.1f}%)")

    if avg_rate >= 0.8:
        print("\n✓ PASSED: Good extraction rate (>= 80%)")
        return 0
    elif avg_rate >= 0.6:
        print("\n⚠ PARTIAL: Moderate extraction rate (60-80%)")
        return 1
    else:
        print("\n✗ FAILED: Poor extraction rate (< 60%)")
        return 2


if __name__ == "__main__":
    sys.exit(test_dahua_extraction())
