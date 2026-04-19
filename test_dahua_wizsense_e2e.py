#!/usr/bin/env python3
"""
End-to-end test for Dahua WizSense 2 and WizSense 3 field extraction.

This script:
1. Discovers series and subseries using Playwright
2. Fetches product detail pages for both WizSense 2 and WizSense 3
3. Extracts all 12 required fields using SpecExtractor
4. Generates a comparison table showing extraction results
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor, ExtractionResult


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---\n")


def extract_fields_for_product(
    adapter: DahuaAdapter,
    extractor: SpecExtractor,
    series_l1: str,
    series_l2: str,
    product_index: int = 0
) -> Optional[Dict[str, ExtractionResult]]:
    """
    Extract fields for a specific product.

    Returns dict of field_code -> ExtractionResult, or None if failed.
    """
    print_subsection(f"Extracting from {series_l1} / {series_l2}")

    # List products in this subseries
    products = adapter.list_products(series_l1, series_l2)
    if not products:
        print(f"❌ No products found for {series_l2}")
        return None

    if product_index >= len(products):
        print(f"❌ Product index {product_index} out of range (found {len(products)} products)")
        return None

    product = products[product_index]
    print(f"📦 Product: {product.model}")
    print(f"   URL: {product.url}")

    # Fetch product detail page
    html = adapter.fetch_product_detail(product.url)
    if not html:
        print(f"❌ Failed to fetch product detail")
        return None

    print(f"✓ Fetched HTML ({len(html)} chars)")

    # Extract all fields
    results, warnings = extractor.extract_all_fields(html, product.url)

    if warnings:
        print(f"⚠ Warnings: {warnings}")

    return results


def compare_extraction_results(
    wizsense2_results: Dict[str, ExtractionResult],
    wizsense3_results: Dict[str, ExtractionResult]
) -> List[Dict]:
    """
    Compare extraction results between two products.

    Returns list of dicts with comparison data for each field.
    """
    comparison = []

    all_fields = set(wizsense2_results.keys()) | set(wizsense3_results.keys())

    for field_code in sorted(all_fields):
        wiz2_result = wizsense2_results.get(field_code)
        wiz3_result = wizsense3_results.get(field_code)

        comparison.append({
            'field_code': field_code,
            'wizsense2_raw': wiz2_result.raw_value if wiz2_result else None,
            'wizsense2_normalized': wiz2_result.normalized_value if wiz2_result else None,
            'wizsense2_confidence': wiz2_result.confidence if wiz2_result else 0.0,
            'wizsense2_method': wiz2_result.extraction_method if wiz2_result else 'N/A',
            'wizsense3_raw': wiz3_result.raw_value if wiz3_result else None,
            'wizsense3_normalized': wiz3_result.normalized_value if wiz3_result else None,
            'wizsense3_confidence': wiz3_result.confidence if wiz3_result else 0.0,
            'wizsense3_method': wiz3_result.extraction_method if wiz3_result else 'N/A',
        })

    return comparison


def print_comparison_table(comparison: List[Dict]):
    """Print a formatted comparison table."""
    print_subsection("Field Extraction Comparison")

    # Header
    print(f"{'Field Code':<40} | {'WizSense 2':<50} | {'WizSense 3':<50}")
    print(f"{'':40} | {'':50} | {'':50}")
    print(f"{'':40} | {'Value (Conf)':<50} | {'Value (Conf)':<50}")
    print("-" * 145)

    # Rows
    for row in comparison:
        field_code = row['field_code']

        # Format WizSense 2 value
        if row['wizsense2_raw']:
            wiz2_val = str(row['wizsense2_raw'])[:40]
            wiz2_conf = f"{row['wizsense2_confidence']:.1f}"
            wiz2_display = f"{wiz2_val} ({wiz2_conf})"
        else:
            wiz2_display = "❌ MISSING"

        # Format WizSense 3 value
        if row['wizsense3_raw']:
            wiz3_val = str(row['wizsense3_raw'])[:40]
            wiz3_conf = f"{row['wizsense3_confidence']:.1f}"
            wiz3_display = f"{wiz3_val} ({wiz3_conf})"
        else:
            wiz3_display = "❌ MISSING"

        print(f"{field_code:<40} | {wiz2_display:<50} | {wiz3_display:<50}")


def analyze_extraction_quality(comparison: List[Dict]) -> Dict:
    """Analyze extraction quality and return statistics."""
    stats = {
        'total_fields': len(comparison),
        'wizsense2_success': 0,
        'wizsense3_success': 0,
        'both_success': 0,
        'both_failed': 0,
        'high_confidence_wiz2': 0,
        'high_confidence_wiz3': 0,
        'failed_fields_wiz2': [],
        'failed_fields_wiz3': [],
    }

    for row in comparison:
        wiz2_success = row['wizsense2_raw'] is not None
        wiz3_success = row['wizsense3_raw'] is not None

        if wiz2_success:
            stats['wizsense2_success'] += 1
            if row['wizsense2_confidence'] >= 0.8:
                stats['high_confidence_wiz2'] += 1
        else:
            stats['failed_fields_wiz2'].append(row['field_code'])

        if wiz3_success:
            stats['wizsense3_success'] += 1
            if row['wizsense3_confidence'] >= 0.8:
                stats['high_confidence_wiz3'] += 1
        else:
            stats['failed_fields_wiz3'].append(row['field_code'])

        if wiz2_success and wiz3_success:
            stats['both_success'] += 1
        elif not wiz2_success and not wiz3_success:
            stats['both_failed'] += 1

    return stats


def print_statistics(stats: Dict):
    """Print extraction statistics."""
    print_subsection("Extraction Statistics")

    print(f"Total fields: {stats['total_fields']}")
    print()
    print(f"WizSense 2:")
    print(f"  - Success rate: {stats['wizsense2_success']}/{stats['total_fields']} ({100*stats['wizsense2_success']/stats['total_fields']:.1f}%)")
    print(f"  - High confidence (≥0.8): {stats['high_confidence_wiz2']}/{stats['wizsense2_success']}")
    if stats['failed_fields_wiz2']:
        print(f"  - Failed fields: {', '.join(stats['failed_fields_wiz2'])}")
    print()
    print(f"WizSense 3:")
    print(f"  - Success rate: {stats['wizsense3_success']}/{stats['total_fields']} ({100*stats['wizsense3_success']/stats['total_fields']:.1f}%)")
    print(f"  - High confidence (≥0.8): {stats['high_confidence_wiz3']}/{stats['wizsense3_success']}")
    if stats['failed_fields_wiz3']:
        print(f"  - Failed fields: {', '.join(stats['failed_fields_wiz3'])}")
    print()
    print(f"Both products:")
    print(f"  - Both extracted: {stats['both_success']}/{stats['total_fields']}")
    print(f"  - Both failed: {stats['both_failed']}/{stats['total_fields']}")


def main():
    """Main test execution."""
    print_section("Dahua WizSense E2E Test")

    # Initialize adapter and extractor
    print("Initializing adapter and extractor...")
    adapter = DahuaAdapter(use_playwright=True)
    extractor = SpecExtractor()

    try:
        # Discover series
        print_subsection("Discovering Series")
        series = adapter.discover_series()
        if not series:
            print("❌ No series discovered")
            return

        print(f"✓ Discovered series: {series}")

        # Discover subseries for each series
        all_subseries = {}
        for s in series:
            print_subsection(f"Discovering Subseries for {s}")
            subseries = adapter.discover_subseries(s)
            all_subseries[s] = subseries
            print(f"✓ Subseries: {subseries}")

        # Find target subseries
        wizsense2_series = "WizSense 2 Series"
        wizsense3_series = "WizSense 3 Series"

        wizsense2_subseries = all_subseries.get(wizsense2_series, [])
        wizsense3_subseries = all_subseries.get(wizsense3_series, [])

        # Find WizColor in WizSense 2
        wizcolor_subseries = None
        for sub in wizsense2_subseries:
            if "wizcolor" in sub.lower():
                wizcolor_subseries = sub
                break

        if not wizcolor_subseries:
            print(f"❌ WizColor subseries not found in WizSense 2")
            print(f"   Available: {wizsense2_subseries}")
            # Use first available
            if wizsense2_subseries:
                wizcolor_subseries = wizsense2_subseries[0]
                print(f"   Using: {wizcolor_subseries}")

        # Find TiOC PRO-WizColor in WizSense 3
        tioc_subseries = None
        for sub in wizsense3_subseries:
            if "tioc" in sub.lower() or "wizcolor" in sub.lower():
                tioc_subseries = sub
                break

        if not tioc_subseries:
            print(f"❌ TiOC PRO-WizColor subseries not found in WizSense 3")
            print(f"   Available: {wizsense3_subseries}")
            # Use first available
            if wizsense3_subseries:
                tioc_subseries = wizsense3_subseries[0]
                print(f"   Using: {tioc_subseries}")

        if not wizcolor_subseries or not tioc_subseries:
            print("❌ Could not find target subseries")
            return

        # Extract fields for WizSense 2 WizColor product
        wizsense2_results = extract_fields_for_product(
            adapter, extractor, wizsense2_series, wizcolor_subseries, product_index=0
        )

        if not wizsense2_results:
            print("❌ Failed to extract WizSense 2 fields")
            return

        # Extract fields for WizSense 3 TiOC product
        wizsense3_results = extract_fields_for_product(
            adapter, extractor, wizsense3_series, tioc_subseries, product_index=0
        )

        if not wizsense3_results:
            print("❌ Failed to extract WizSense 3 fields")
            return

        # Compare results
        comparison = compare_extraction_results(wizsense2_results, wizsense3_results)

        # Print comparison table
        print_comparison_table(comparison)

        # Analyze and print statistics
        stats = analyze_extraction_quality(comparison)
        print_statistics(stats)

        # Identify issues
        print_subsection("Issues to Fix")

        issues_found = False

        # Check for fields that failed on both
        both_failed = [row['field_code'] for row in comparison
                      if not row['wizsense2_raw'] and not row['wizsense3_raw']]
        if both_failed:
            issues_found = True
            print(f"❌ Fields failing on BOTH products:")
            for field in both_failed:
                print(f"   - {field}")

        # Check for low confidence extractions
        low_conf_wiz2 = [row['field_code'] for row in comparison
                        if row['wizsense2_raw'] and row['wizsense2_confidence'] < 0.8]
        if low_conf_wiz2:
            issues_found = True
            print(f"\n⚠ WizSense 2 low confidence (<0.8):")
            for field in low_conf_wiz2:
                conf = next(r['wizsense2_confidence'] for r in comparison if r['field_code'] == field)
                print(f"   - {field} ({conf:.1f})")

        low_conf_wiz3 = [row['field_code'] for row in comparison
                        if row['wizsense3_raw'] and row['wizsense3_confidence'] < 0.8]
        if low_conf_wiz3:
            issues_found = True
            print(f"\n⚠ WizSense 3 low confidence (<0.8):")
            for field in low_conf_wiz3:
                conf = next(r['wizsense3_confidence'] for r in comparison if r['field_code'] == field)
                print(f"   - {field} ({conf:.1f})")

        if not issues_found:
            print("✓ No issues found! All fields extracted successfully.")

        # Save detailed results to JSON
        print_subsection("Saving Results")
        output_file = Path("/tmp/dahua_wizsense_e2e_results.json")
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'wizsense2_series': wizsense2_series,
            'wizsense2_subseries': wizcolor_subseries,
            'wizsense3_series': wizsense3_series,
            'wizsense3_subseries': tioc_subseries,
            'comparison': comparison,
            'statistics': stats,
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Results saved to {output_file}")

    finally:
        # Clean up
        print_subsection("Cleanup")
        adapter.close()
        print("✓ Browser closed")


if __name__ == "__main__":
    main()
