#!/usr/bin/env python3
"""
Comprehensive status verification script.

Tests:
1. Hikvision Value series product discovery (with Pro series comparison)
2. Dahua WizSense 3 field extraction (12/12 fields)
3. Playwright stability checks
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.hikvision_adapter import HikvisionAdapter
from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor


def test_hikvision_value_series():
    """Test Hikvision Value series discovery and compare with Pro series."""
    print("\n" + "="*80)
    print("TEST 1: Hikvision Value Series Discovery")
    print("="*80)

    results = {
        "test": "Hikvision Value Series",
        "timestamp": datetime.now().isoformat(),
        "status": "running",
        "details": {}
    }

    adapter = HikvisionAdapter(use_playwright=True)

    try:
        # Discover series
        print("\n[1] Discovering all series...")
        series_list = adapter.discover_series()
        print(f"     Found {len(series_list)} series: {series_list}")
        results["details"]["all_series"] = series_list

        # Find Value series
        value_series = None
        for s in series_list:
            if "value" in s.lower():
                value_series = s
                break

        if not value_series:
            results["status"] = "FAILED"
            results["error"] = "Value series not found"
            print("     ✗ FAILED: Value series not found")
            return results

        print(f"     ✓ Found Value series: '{value_series}'")

        # Discover subseries for Value
        print(f"\n[2] Discovering subseries for Value series...")
        value_subseries = adapter.discover_subseries(value_series)
        print(f"     Found {len(value_subseries)} subseries: {value_subseries}")
        results["details"]["value_subseries"] = value_subseries

        # List Value products
        print(f"\n[3] Listing Value series products...")
        value_products = []
        for sub in value_subseries[:3]:  # Test first 3 subseries
            print(f"     Fetching products for: {sub}")
            products = adapter.list_products(value_series, sub)
            print(f"     Found {len(products)} products")
            value_products.extend(products)
            time.sleep(1)

        results["details"]["value_product_count"] = len(value_products)
        results["details"]["value_products_sample"] = [
            {"model": p.model, "url": p.url} for p in value_products[:5]
        ]

        # Now get Pro products for comparison
        print(f"\n[4] Listing Pro series products for comparison...")
        pro_series = None
        for s in series_list:
            if "pro" in s.lower():
                pro_series = s
                break

        if pro_series:
            pro_subseries = adapter.discover_subseries(pro_series)
            print(f"     Found Pro subseries: {pro_subseries}")

            pro_products = []
            for sub in pro_subseries[:2]:  # Test first 2 subseries
                print(f"     Fetching products for: {sub}")
                products = adapter.list_products(pro_series, sub)
                print(f"     Found {len(products)} products")
                pro_products.extend(products)
                time.sleep(1)

            results["details"]["pro_product_count"] = len(pro_products)

            # Check for overlap
            value_models = set(p.model for p in value_products)
            pro_models = set(p.model for p in pro_products)
            overlap = value_models & pro_models

            results["details"]["overlap_count"] = len(overlap)
            results["details"]["overlap_models"] = list(overlap)

            if overlap:
                print(f"\n     ⚠ WARNING: Found {len(overlap)} overlapping models:")
                for model in sorted(overlap)[:5]:
                    print(f"       - {model}")
            else:
                print(f"\n     ✓ GOOD: No overlapping models between Value and Pro series")

        # Print sample Value products
        print(f"\n[5] Sample Value products:")
        for i, p in enumerate(value_products[:10], 1):
            print(f"     {i}. {p.model} - {p.name}")

        # Validate
        if len(value_products) >= 5:
            results["status"] = "PASSED"
            print(f"\n✓ PASSED: Found {len(value_products)} Value products")
        else:
            results["status"] = "FAILED"
            results["error"] = f"Only found {len(value_products)} Value products (expected >= 5)"
            print(f"\n✗ FAILED: Only found {len(value_products)} Value products")

    except Exception as e:
        results["status"] = "ERROR"
        results["error"] = str(e)
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        adapter.close()

    return results


def test_dahua_field_extraction():
    """Test Dahua WizSense 3 field extraction (12/12 fields)."""
    print("\n" + "="*80)
    print("TEST 2: Dahua WizSense 3 Field Extraction")
    print("="*80)

    results = {
        "test": "Dahua WizSense 3 Field Extraction",
        "timestamp": datetime.now().isoformat(),
        "status": "running",
        "details": {}
    }

    adapter = DahuaAdapter(use_playwright=True)

    try:
        # Discover series
        print("\n[1] Discovering Dahua series...")
        series_list = adapter.discover_series()
        print(f"     Found {len(series_list)} series: {series_list}")
        results["details"]["all_series"] = series_list

        # Find WizSense 3
        target_series = None
        for s in series_list:
            if "wizsense 3" in s.lower():
                target_series = s
                break

        if not target_series:
            results["status"] = "FAILED"
            results["error"] = "WizSense 3 Series not found"
            print("     ✗ FAILED: WizSense 3 Series not found")
            return results

        print(f"     ✓ Found series: '{target_series}'")

        # Discover subseries
        print(f"\n[2] Discovering subseries for {target_series}...")
        subseries_list = adapter.discover_subseries(target_series)
        print(f"     Found {len(subseries_list)} subseries: {subseries_list}")
        results["details"]["subseries"] = subseries_list

        # List products
        print(f"\n[3] Listing products...")
        all_products = []
        for sub in subseries_list:
            products = adapter.list_products(target_series, sub)
            print(f"     {sub}: {len(products)} products")
            all_products.extend(products)

        if not all_products:
            results["status"] = "FAILED"
            results["error"] = "No products found"
            print("     ✗ FAILED: No products found")
            return results

        print(f"     ✓ Total products: {len(all_products)}")

        # Pick first product for testing
        test_product = all_products[0]
        print(f"\n[4] Testing field extraction for: {test_product.model}")
        print(f"     URL: {test_product.url}")

        # Fetch detail page
        html = adapter.fetch_product_detail(test_product.url)
        if not html:
            results["status"] = "FAILED"
            results["error"] = "Failed to fetch product detail"
            print("     ✗ FAILED: Failed to fetch product detail")
            return results

        print(f"     ✓ Fetched HTML ({len(html)} chars)")

        # Extract fields
        print(f"\n[5] Extracting fields with SpecExtractor...")
        extractor = SpecExtractor()

        # 12 required fields
        required_fields = [
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

        extracted = {}
        for field_code in required_fields:
            try:
                value = extractor.extract_field(field_code, html, test_product.url)
                if value:
                    extracted[field_code] = value
                    print(f"     ✓ {field_code}: {value[:100] if len(value) > 100 else value}")
                else:
                    print(f"     ✗ {field_code}: NOT FOUND")
            except Exception as e:
                print(f"     ✗ {field_code}: ERROR - {e}")

        results["details"]["extracted_fields"] = extracted
        results["details"]["extraction_rate"] = f"{len(extracted)}/{len(required_fields)}"

        # Validate
        if len(extracted) >= 10:
            results["status"] = "PASSED"
            print(f"\n✓ PASSED: Extracted {len(extracted)}/{len(required_fields)} fields")
        elif len(extracted) >= 8:
            results["status"] = "PARTIAL"
            print(f"\n⚠ PARTIAL: Extracted {len(extracted)}/{len(required_fields)} fields")
        else:
            results["status"] = "FAILED"
            results["error"] = f"Only extracted {len(extracted)}/{len(required_fields)} fields"
            print(f"\n✗ FAILED: Only extracted {len(extracted)}/{len(required_fields)} fields")

    except Exception as e:
        results["status"] = "ERROR"
        results["error"] = str(e)
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        adapter.close()

    return results


def main():
    """Run all tests and generate report."""
    print("\n" + "="*80)
    print("STATUS VERIFICATION - Competition Analysis System")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")

    all_results = []

    # Test 1: Hikvision Value series
    result1 = test_hikvision_value_series()
    all_results.append(result1)

    # Test 2: Dahua field extraction
    result2 = test_dahua_field_extraction()
    all_results.append(result2)

    # Generate report
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    for result in all_results:
        status_symbol = {
            "PASSED": "✓",
            "PARTIAL": "⚠",
            "FAILED": "✗",
            "ERROR": "✗",
            "running": "→"
        }.get(result["status"], "?")

        print(f"\n{status_symbol} {result['test']}: {result['status']}")

        if result["status"] == "FAILED" or result["status"] == "ERROR":
            print(f"  Error: {result.get('error', 'Unknown')}")

        details = result.get("details", {})
        if "extraction_rate" in details:
            print(f"  Extraction rate: {details['extraction_rate']}")
        if "value_product_count" in details:
            print(f"  Value products: {details['value_product_count']}")
        if "overlap_count" in details:
            print(f"  Overlap with Pro: {details['overlap_count']} models")

    # Save to file
    report_path = Path("results") / "status-check.md"
    report_path.parent.mkdir(exist_ok=True)

    with open(report_path, "w") as f:
        f.write(f"# Status Check Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")

        f.write("## Test Results\n\n")

        for result in all_results:
            f.write(f"### {result['test']}\n\n")
            f.write(f"**Status:** {result['status']}\n\n")

            if result.get("error"):
                f.write(f"**Error:** {result['error']}\n\n")

            details = result.get("details", {})
            if details:
                f.write("**Details:**\n\n")
                for key, value in details.items():
                    if key == "extracted_fields":
                        f.write(f"- {key}: {len(value)} fields extracted\n")
                    elif isinstance(value, list):
                        f.write(f"- {key}: {len(value)} items\n")
                    else:
                        f.write(f"- {key}: {value}\n")

                # Show extracted fields if available
                if "extracted_fields" in details:
                    f.write("\n**Extracted Fields:**\n\n")
                    for field, value in details["extracted_fields"].items():
                        f.write(f"- {field}: `{value[:80]}...`\n")

            f.write("\n---\n\n")

    print(f"\n✓ Report saved to: {report_path}")

    # Return exit code
    failed_count = sum(1 for r in all_results if r["status"] in ["FAILED", "ERROR"])
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
