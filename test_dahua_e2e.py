"""
End-to-end test for Dahua adapter and spec extractor.

This test:
1. Uses DahuaAdapter(use_playwright=True) to fetch product detail pages
2. Tests WizSense 2 (WizColor) and WizSense 3 (TiOC PRO-WizColor) products
3. Extracts all 12 required fields using SpecExtractor
4. Outputs extraction results comparison table
5. Analyzes failures and provides fixes
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor, ExtractionResult


@dataclass
class ProductTestResult:
    """Result of testing a single product."""
    series_l1: str
    series_l2: str
    model: str
    url: str
    extractions: Dict[str, ExtractionResult]
    success_count: int
    fail_count: int


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_section(title: str):
    """Print a section header."""
    print_separator()
    print(f"  {title}")
    print_separator()


def extract_field_name(result: ExtractionResult) -> str:
    """Extract a clean field name from field_code."""
    return result.field_code.replace("_", " ").title()


def print_extraction_table(results: List[ProductTestResult]):
    """Print comparison table of extraction results."""
    print_section("EXTRACTION RESULTS COMPARISON")

    # Header row
    header = f"{'Field Code':<40} | {'WizSense 2':<25} | {'WizSense 3':<25}"
    print(header)
    print("-" * len(header))

    # Get all 12 required fields
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

    for field_code in required_fields:
        # Get results from both products
        ws2_result = results[0].extractions.get(field_code)
        ws3_result = results[1].extractions.get(field_code)

        # Format status indicators
        ws2_status = "✓" if ws2_result and ws2_result.confidence > 0 else "✗"
        ws3_status = "✓" if ws3_result and ws3_result.confidence > 0 else "✗"

        # Format values (truncate if too long)
        ws2_value = (ws2_result.normalized_value or ws2_result.raw_value or "MISSING")[:25] if ws2_result else "N/A"
        ws3_value = (ws3_result.normalized_value or ws3_result.raw_value or "MISSING")[:25] if ws3_result else "N/A"

        # Format row
        row = f"{field_code:<40} | {ws2_status} {ws2_value:<23} | {ws3_status} {ws3_value:<23}"
        print(row)

    print_separator()


def analyze_failures(results: List[ProductTestResult]):
    """Analyze extraction failures and provide insights."""
    print_section("FAILURE ANALYSIS")

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

    all_failures = []

    for i, product_result in enumerate(results):
        product_name = f"WizSense {'2' if i == 0 else '3'} ({product_result.series_l2})"

        for field_code in required_fields:
            result = product_result.extractions.get(field_code)
            if not result or result.confidence == 0:
                all_failures.append({
                    "product": product_name,
                    "field": field_code,
                    "reason": result.extraction_method if result else "No result object"
                })

    if all_failures:
        print(f"Found {len(all_failures)} extraction failures:\n")
        for failure in all_failures:
            print(f"  - {failure['product']}: {failure['field']}")
            print(f"    Reason: {failure['reason']}\n")
    else:
        print("✓ All fields extracted successfully!")

    print_separator()


def print_summary(results: List[ProductTestResult]):
    """Print test summary statistics."""
    print_section("TEST SUMMARY")

    for i, result in enumerate(results):
        product_name = f"WizSense {'2' if i == 0 else '3'} ({result.series_l2})"
        total_fields = 12
        success_rate = (result.success_count / total_fields) * 100

        print(f"\n{product_name}:")
        print(f"  Model: {result.model}")
        print(f"  URL: {result.url}")
        print(f"  Success: {result.success_count}/{total_fields} fields ({success_rate:.1f}%)")
        print(f"  Failed: {result.fail_count} fields")

    print_separator()


def main():
    """Run end-to-end test."""
    print_section("DAHUA E2E TEST - Starting")

    # Initialize adapter and extractor
    print("\n[1/4] Initializing DahuaAdapter with Playwright...")
    adapter = DahuaAdapter(use_playwright=True)
    extractor = SpecExtractor()

    try:
        # Discover series
        print("\n[2/4] Discovering series...")
        series_list = adapter.discover_series()
        print(f"Found series: {series_list}")

        if not series_list:
            print("ERROR: No series discovered. Check network connectivity or selectors.")
            return

        # Test WizSense 2
        print("\n[3/4] Testing WizSense 2 (WizColor)...")
        ws2_subseries = adapter.discover_subseries("WizSense 2 Series")
        print(f"WizSense 2 subseries: {ws2_subseries}")

        ws2_products = []
        if "WizColor" in ws2_subseries:
            ws2_products = adapter.list_products("WizSense 2 Series", "WizColor")
        elif ws2_subseries:
            # Use first available subseries
            ws2_products = adapter.list_products("WizSense 2 Series", ws2_subseries[0])

        if not ws2_products:
            print("ERROR: No WizSense 2 products found.")
            # Try to find any product from WizSense 2
            for subseries in ws2_subseries:
                products = adapter.list_products("WizSense 2 Series", subseries)
                if products:
                    ws2_products = products
                    break

        if not ws2_products:
            print("ERROR: Still no products found for WizSense 2.")
            return

        ws2_product = ws2_products[0]
        print(f"Selected product: {ws2_product.model} - {ws2_product.url}")

        # Fetch detail page
        ws2_html = adapter.fetch_product_detail(ws2_product.url)
        if not ws2_html:
            print(f"ERROR: Failed to fetch detail page for {ws2_product.model}")
            return

        print(f"Fetched HTML: {len(ws2_html)} characters")

        # Extract fields
        ws2_extractions, ws2_warnings = extractor.extract_all_fields(ws2_html, ws2_product.url)
        ws2_success = sum(1 for r in ws2_extractions.values() if r.confidence > 0)
        ws2_fail = sum(1 for r in ws2_extractions.values() if r.confidence == 0)

        print(f"Extraction results: {ws2_success} successful, {ws2_fail} failed")
        if ws2_warnings:
            print(f"Warnings: {ws2_warnings}")

        # Test WizSense 3
        print("\nTesting WizSense 3 (TiOC PRO-WizColor)...")
        ws3_subseries = adapter.discover_subseries("WizSense 3 Series")
        print(f"WizSense 3 subseries: {ws3_subseries}")

        ws3_products = []
        target_subseries = "TiOC PRO-WizColor"
        if target_subseries in ws3_subseries:
            ws3_products = adapter.list_products("WizSense 3 Series", target_subseries)
        elif ws3_subseries:
            # Use first available subseries
            ws3_products = adapter.list_products("WizSense 3 Series", ws3_subseries[0])

        if not ws3_products:
            print(f"WARNING: No products found for {target_subseries}")
            # Try to find any product from WizSense 3
            for subseries in ws3_subseries:
                products = adapter.list_products("WizSense 3 Series", subseries)
                if products:
                    ws3_products = products
                    break

        if not ws3_products:
            print("ERROR: Still no products found for WizSense 3.")
            return

        ws3_product = ws3_products[0]
        print(f"Selected product: {ws3_product.model} - {ws3_product.url}")

        # Fetch detail page
        ws3_html = adapter.fetch_product_detail(ws3_product.url)
        if not ws3_html:
            print(f"ERROR: Failed to fetch detail page for {ws3_product.model}")
            return

        print(f"Fetched HTML: {len(ws3_html)} characters")

        # Extract fields
        ws3_extractions, ws3_warnings = extractor.extract_all_fields(ws3_html, ws3_product.url)
        ws3_success = sum(1 for r in ws3_extractions.values() if r.confidence > 0)
        ws3_fail = sum(1 for r in ws3_extractions.values() if r.confidence == 0)

        print(f"Extraction results: {ws3_success} successful, {ws3_fail} failed")
        if ws3_warnings:
            print(f"Warnings: {ws3_warnings}")

        # Compile results
        results = [
            ProductTestResult(
                series_l1="WizSense 2 Series",
                series_l2=ws2_product.series_l2,
                model=ws2_product.model,
                url=ws2_product.url,
                extractions=ws2_extractions,
                success_count=ws2_success,
                fail_count=ws2_fail
            ),
            ProductTestResult(
                series_l1="WizSense 3 Series",
                series_l2=ws3_product.series_l2,
                model=ws3_product.model,
                url=ws3_product.url,
                extractions=ws3_extractions,
                success_count=ws3_success,
                fail_count=ws3_fail
            )
        ]

        # [4/4] Output results
        print_section("EXTRACTION COMPLETE")
        print_extraction_table(results)
        analyze_failures(results)
        print_summary(results)

        # Save detailed results to JSON
        output_file = Path("test_results.json")
        detailed_results = {
            "wizsense_2": {
                "product": {
                    "model": ws2_product.model,
                    "series_l2": ws2_product.series_l2,
                    "url": ws2_product.url
                },
                "extractions": {
                    field_code: {
                        "raw_value": result.raw_value,
                        "normalized_value": result.normalized_value,
                        "confidence": result.confidence,
                        "method": result.extraction_method,
                        "issues": result.issues
                    }
                    for field_code, result in ws2_extractions.items()
                },
                "success_count": ws2_success,
                "fail_count": ws2_fail
            },
            "wizsense_3": {
                "product": {
                    "model": ws3_product.model,
                    "series_l2": ws3_product.series_l2,
                    "url": ws3_product.url
                },
                "extractions": {
                    field_code: {
                        "raw_value": result.raw_value,
                        "normalized_value": result.normalized_value,
                        "confidence": result.confidence,
                        "method": result.extraction_method,
                        "issues": result.issues
                    }
                    for field_code, result in ws3_extractions.items()
                },
                "success_count": ws3_success,
                "fail_count": ws3_fail
            }
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Detailed results saved to {output_file}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        print("\n[Cleanup] Closing browser...")
        adapter.close()


if __name__ == "__main__":
    main()
