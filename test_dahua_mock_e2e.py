#!/usr/bin/env python3
"""
Dahua extraction test with mock HTML data.

Since Playwright is not available in this environment, this test uses
mock HTML data that simulates the structure of real Dahua product pages.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.extractor.spec_extractor import SpecExtractor, ExtractionResult


# Mock HTML data simulating Dahua product page structure
# This represents typical HTML structure found on Dahua product pages
MOCK_DAHUA_HTML_WIZSENSE2 = """
<!DOCTYPE html>
<html>
<body>
    <div class="product-detail">
        <div class="specification-table">
            <table>
                <tr>
                    <td class="spec-label">Image Sensor</td>
                    <td class="spec-value">1/2.8" CMOS</td>
                </tr>
                <tr>
                    <td class="spec-label">Max. Resolution</td>
                    <td class="spec-value">2560×1440</td>
                </tr>
                <tr>
                    <td class="spec-label">Lens Type</td>
                    <td class="spec-value">Fixed focal</td>
                </tr>
                <tr>
                    <td class="spec-label">Aperture</td>
                    <td class="spec-value">F1.4</td>
                </tr>
                <tr>
                    <td class="spec-label">Supplement Light Type</td>
                    <td class="spec-value">IR</td>
                </tr>
                <tr>
                    <td class="spec-label">IR Range</td>
                    <td class="spec-value">50 m</td>
                </tr>
                <tr>
                    <td class="spec-label">Main Stream</td>
                    <td class="spec-value">2560×1440@30fps</td>
                </tr>
                <tr>
                    <td class="spec-label">Third Stream</td>
                    <td class="spec-value">Yes</td>
                </tr>
                <tr>
                    <td class="spec-label">Interface</td>
                    <td class="spec-value">
                        <ul>
                            <li>1 Network Port (RJ45)</li>
                            <li>1 Audio Input</li>
                            <li>1 Audio Output</li>
                            <li>1 Alarm Input</li>
                            <li>1 Alarm Output</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="spec-label">Intelligence</td>
                    <td class="spec-value">
                        <ul>
                            <li>SMD</li>
                            <li>Quick Target</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="spec-label">Protection</td>
                    <td class="spec-value">IP67</td>
                </tr>
                <tr>
                    <td class="spec-label">Anti-Corrosion Protection</td>
                    <td class="spec-value">N/A</td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

MOCK_DAHUA_HTML_WIZSENSE3 = """
<!DOCTYPE html>
<html>
<body>
    <div class="product-detail">
        <div class="specification-table">
            <table>
                <tr>
                    <td class="spec-label">Image Sensor</td>
                    <td class="spec-value">1/1.8" CMOS</td>
                </tr>
                <tr>
                    <td class="spec-label">Max. Resolution</td>
                    <td class="spec-value">3840×2160</td>
                </tr>
                <tr>
                    <td class="spec-label">Lens Type</td>
                    <td class="spec-value">Fixed focal</td>
                </tr>
                <tr>
                    <td class="spec-label">Aperture</td>
                    <td class="spec-value">F1.6</td>
                </tr>
                <tr>
                    <td class="spec-label">Supplement Light Type</td>
                    <td class="spec-value">Warm Light</td>
                </tr>
                <tr>
                    <td class="spec-label">IR Range</td>
                    <td class="spec-value">30 m</td>
                </tr>
                <tr>
                    <td class="spec-label">Main Stream</td>
                    <td class="spec-value">3840×2160@30fps</td>
                </tr>
                <tr>
                    <td class="spec-label">Third Stream</td>
                    <td class="spec-value">Yes</td>
                </tr>
                <tr>
                    <td class="spec-label">Interface</td>
                    <td class="spec-value">
                        <ul>
                            <li>1 Network Port (RJ45)</li>
                            <li>1 Audio Input</li>
                            <li>1 Audio Output</li>
                            <li>2 Alarm Input</li>
                            <li>2 Alarm Output</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="spec-label">Intelligence</td>
                    <td class="spec-value">
                        <ul>
                            <li>SMD Plus</li>
                            <li>AcuPick</li>
                            <li>AI SSA</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="spec-label">Protection</td>
                    <td class="spec-value">IP67</td>
                </tr>
                <tr>
                    <td class="spec-label">Anti-Corrosion Protection</td>
                    <td class="spec-value">N/A</td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>
"""


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---\n")


def print_comparison_table(results: list):
    """Print comparison table of extraction results."""
    print_subsection("Extraction Results Comparison")

    # Required fields
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

    # Header
    print(f"{'Field Code':<40} | {'WizSense 2':<30} | {'WizSense 3':<30}")
    print("-" * 105)

    # Rows
    for field_code in required_fields:
        result1 = results[0]['extractions'].get(field_code)
        result2 = results[1]['extractions'].get(field_code)

        # Format status and value
        if result1 and result1.confidence > 0:
            val1 = str(result1.normalized_value or result1.raw_value)[:27]
            status1 = f"✓ {val1}"
        else:
            status1 = "✗ MISSING"

        if result2 and result2.confidence > 0:
            val2 = str(result2.normalized_value or result2.raw_value)[:27]
            status2 = f"✓ {val2}"
        else:
            status2 = "✗ MISSING"

        print(f"{field_code:<40} | {status1:<30} | {status2:<30}")

    print()


def analyze_results(results: list):
    """Analyze extraction results and provide statistics."""
    print_subsection("Statistics & Analysis")

    for i, result in enumerate(results, 1):
        product_info = result['product']
        extractions = result['extractions']

        total_fields = 12
        success_count = sum(1 for r in extractions.values() if r.raw_value is not None)
        fail_count = total_fields - success_count
        success_rate = (success_count / total_fields) * 100

        print(f"Product {i}: {product_info['name']}")
        print(f"  Model: {product_info.get('model', 'N/A')}")
        print(f"  Success: {success_count}/{total_fields} ({success_rate:.1f}%)")
        print(f"  Failed: {fail_count}")

        # List failed fields
        failed_fields = [fc for fc, r in extractions.items() if r.raw_value is None]
        if failed_fields:
            print(f"  Failed fields: {', '.join(failed_fields)}")
        print()


def identify_issues(results: list):
    """Identify and report extraction issues."""
    print_subsection("Issues & Recommendations")

    issues = []

    # Check for fields that failed on both products
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

    both_failed = []
    for field_code in required_fields:
        result1 = results[0]['extractions'].get(field_code)
        result2 = results[1]['extractions'].get(field_code)

        if (not result1 or result1.confidence == 0) and (not result2 or result2.confidence == 0):
            both_failed.append(field_code)

    if both_failed:
        issues.append({
            'severity': 'HIGH',
            'description': 'Fields failing on BOTH products',
            'fields': both_failed
        })

    # Check for low confidence extractions
    low_conf_fields = []
    for i, result in enumerate(results, 1):
        for field_code, extraction in result['extractions'].items():
            if 0 < extraction.confidence < 0.8:
                low_conf_fields.append({
                    'product': i,
                    'field': field_code,
                    'confidence': extraction.confidence,
                    'method': extraction.extraction_method
                })

    if low_conf_fields:
        issues.append({
            'severity': 'MEDIUM',
            'description': 'Low confidence extractions (<0.8)',
            'fields': low_conf_fields
        })

    # Print issues
    if not issues:
        print("✓ No critical issues found!")
    else:
        for issue in issues:
            print(f"[{issue['severity']}] {issue['description']}")
            if issue['severity'] == 'HIGH':
                for field in issue['fields']:
                    print(f"   - {field}")
            else:
                for item in issue['fields']:
                    print(f"   - Product {item['product']}: {item['field']} (conf: {item['confidence']:.1f}, method: {item['method']})")
            print()

    # Provide recommendations
    print("Recommendations:")
    if both_failed:
        print("  1. For failed fields, check if they exist on the page with different labels")
        print("  2. Add field aliases to field_registry.py if needed")
        print("  3. Consider Dahua-specific extraction logic in spec_extractor.py")
    if low_conf_fields:
        print("  4. Improve extraction logic for low-confidence fields")
        print("  5. Add more specific selectors or patterns")


def main():
    """Run extraction test with mock data."""
    print_section("Dahua Extraction Test (Mock Data)")

    # Initialize extractor
    print("Initializing extractor...")
    extractor = SpecExtractor()

    results = []

    # Test WizSense 2
    print_subsection("Testing: WizSense 2 (Mock)")
    ws2_extractions, ws2_warnings = extractor.extract_all_fields(MOCK_DAHUA_HTML_WIZSENSE2)
    ws2_success = sum(1 for r in ws2_extractions.values() if r.raw_value is not None)
    print(f"✓ Extracted {ws2_success}/12 fields")

    results.append({
        'product': {
            'name': 'WizSense 2 - WizColor (Mock)',
            'model': 'IPC-HFW3541E-SP-ASED'
        },
        'extractions': ws2_extractions,
        'warnings': ws2_warnings
    })

    # Test WizSense 3
    print_subsection("Testing: WizSense 3 (Mock)")
    ws3_extractions, ws3_warnings = extractor.extract_all_fields(MOCK_DAHUA_HTML_WIZSENSE3)
    ws3_success = sum(1 for r in ws3_extractions.values() if r.raw_value is not None)
    print(f"✓ Extracted {ws3_success}/12 fields")

    results.append({
        'product': {
            'name': 'WizSense 3 - TiOC PRO (Mock)',
            'model': 'IPC-HFW3541T1-ASP-SED'
        },
        'extractions': ws3_extractions,
        'warnings': ws3_warnings
    })

    # Print comparison table
    print_comparison_table(results)

    # Analyze results
    analyze_results(results)

    # Identify issues
    identify_issues(results)

    # Save detailed results
    print_subsection("Saving Results")
    output_file = Path("test_dahua_mock_results.json")

    # Prepare output data
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'note': 'This test used mock HTML data due to Playwright unavailability',
        'products': []
    }

    for result in results:
        product_data = {
            'info': result['product'],
            'extractions': {
                field_code: {
                    'raw_value': r.raw_value,
                    'normalized_value': r.normalized_value,
                    'confidence': r.confidence,
                    'method': r.extraction_method,
                    'issues': r.issues
                }
                for field_code, r in result['extractions'].items()
            },
            'warnings': result['warnings']
        }
        output_data['products'].append(product_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Results saved to {output_file}")

    # Final summary
    print_section("Test Complete")

    total_success = sum(
        sum(1 for r in result['extractions'].values() if r.raw_value is not None)
        for result in results
    )
    total_possible = len(results) * 12
    overall_rate = (total_success / total_possible) * 100

    print(f"Overall success rate: {total_success}/{total_possible} ({overall_rate:.1f}%)")
    print(f"\nNOTE: This test used mock HTML data to validate extraction logic.")
    print(f"Real-world testing requires Playwright in a supported environment.")


if __name__ == "__main__":
    main()
