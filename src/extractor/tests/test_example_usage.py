"""
Example usage and demonstration of the extractor module.

This script shows how to use the various extractor components
for parsing and normalizing product specification fields.
"""

from src.extractor.field_registry import FieldRegistry
from src.extractor.spec_extractor import SpecExtractor
from src.extractor.normalizer import Normalizer
from src.extractor.parsers import ResolutionParser, StreamParser, RangeParser


def demo_field_registry():
    """Demonstrate field registry usage."""
    print("=" * 60)
    print("Field Registry Demo")
    print("=" * 60)

    registry = FieldRegistry()

    # Get all field codes
    print(f"\nTotal Phase 1 fields: {len(registry.get_all_field_codes())}")
    print(f"Required fields: {len(registry.get_required_field_codes())}")

    # Get specific field definition
    field = registry.get_field("max_resolution")
    if field:
        print(f"\nField: {field.field_name}")
        print(f"  Code: {field.field_code}")
        print(f"  Required: {field.required}")
        print(f"  Type: {field.value_type}")
        print(f"  Unit: {field.canonical_unit}")
        print(f"  Aliases: {field.aliases}")


def demo_resolution_parser():
    """Demonstrate resolution parsing."""
    print("\n" + "=" * 60)
    print("Resolution Parser Demo")
    print("=" * 60)

    parser = ResolutionParser()

    test_cases = [
        "1920x1080",
        "4608 × 2592",
        "2592P",
        "5MP",
        "3840x2160 (4K)",
    ]

    for case in test_cases:
        normalized = parser.normalize(case)
        mp = parser.calculate_megapixels(normalized) if normalized else None
        aspect = parser.get_aspect_ratio(normalized) if normalized else None
        print(f"\n  Input: {case}")
        print(f"  Output: {normalized}")
        print(f"  MP: {mp}, Aspect: {aspect}")


def demo_stream_parser():
    """Demonstrate stream parsing."""
    print("\n" + "=" * 60)
    print("Stream Parser Demo")
    print("=" * 60)

    parser = StreamParser()

    test_cases = [
        "30fps (1920x1080)",
        "60fps@2560x1440",
        "25 fps 2048x1536",
        "15fps",
    ]

    for case in test_cases:
        normalized = parser.normalize(case)
        fps = parser.extract_fps(case)
        res = parser.extract_resolution(case)
        print(f"\n  Input: {case}")
        print(f"  Output: {normalized}")
        print(f"  FPS: {fps}, Resolution: {res}")


def demo_range_parser():
    """Demonstrate distance range parsing."""
    print("\n" + "=" * 60)
    print("Range Parser Demo")
    print("=" * 60)

    parser = RangeParser()

    test_cases = [
        "50m",
        "100 ft",
        "10-30m",
        "up to 50m",
        "30 inches",
    ]

    for case in test_cases:
        normalized = parser.normalize(case)
        max_dist = parser.get_max_distance_in_meters(case)
        is_range = parser.is_range(case)
        print(f"\n  Input: {case}")
        print(f"  Output: {normalized}")
        print(f"  Max (m): {max_dist}, Is Range: {is_range}")


def demo_normalizer():
    """Demonstrate field normalization."""
    print("\n" + "=" * 60)
    print("Normalizer Demo")
    print("=" * 60)

    normalizer = Normalizer()

    test_fields = {
        "max_resolution": "4K (3840x2160)",
        "supplement_light_range": "100 ft",
        "aperture": "F1.8",
        "stream_count": "3 streams",
        "interface_items": "RJ45, Audio, Alarm",
    }

    for field_code, raw_value in test_fields.items():
        normalized, unit, issues = normalizer.normalize(field_code, raw_value)
        print(f"\n  Field: {field_code}")
        print(f"  Input: {raw_value}")
        print(f"  Output: {normalized}")
        print(f"  Unit: {unit}")
        if issues:
            print(f"  Issues: {issues}")


def demo_html_extraction():
    """Demonstrate HTML-based extraction."""
    print("\n" + "=" * 60)
    print("HTML Extraction Demo")
    print("=" * 60)

    extractor = SpecExtractor()

    # Sample HTML snippet (simplified Hikvision spec table)
    sample_html = """
    <html>
    <body>
        <table class="spec-table">
            <tr>
                <th>Image Sensor</th>
                <td>1/2.8" Progressive Scan CMOS</td>
            </tr>
            <tr>
                <th>Max. Resolution</th>
                <td>4608 × 2592</td>
            </tr>
            <tr>
                <th>Main Stream</th>
                <td>30fps (4608x2592)</td>
            </tr>
            <tr>
                <th>Supplement Light Range</th>
                <td>50 m</td>
            </tr>
            <tr>
                <th>Interface</th>
                <td>
                    <ul>
                        <li>RJ45 10/100/1000Mbps自适应</li>
                        <li>音频输入/输出</li>
                    </ul>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    results, warnings = extractor.extract_all_fields(sample_html)

    print(f"\nWarnings: {warnings}")

    # Show successful extractions
    for field_code, result in results.items():
        if result.confidence > 0:
            print(f"\n  {field_code}:")
            print(f"    Raw: {result.raw_value}")
            print(f"    Normalized: {result.normalized_value}")
            print(f"    Confidence: {result.confidence}")
            print(f"    Method: {result.extraction_method}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EXTRACTOR MODULE DEMONSTRATION")
    print("=" * 60)

    demo_field_registry()
    demo_resolution_parser()
    demo_stream_parser()
    demo_range_parser()
    demo_normalizer()
    demo_html_extraction()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
