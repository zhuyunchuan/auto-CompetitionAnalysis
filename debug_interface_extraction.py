#!/usr/bin/env python3
"""Debug interface_items extraction issue."""

import sys
import json
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from src.extractor.spec_extractor import SpecExtractor

MOCK_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="product-detail">
        <div class="specification-table">
            <table>
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
            </table>
        </div>
    </div>
</body>
</html>
"""

def main():
    print("="*80)
    print("Debugging interface_items extraction")
    print("="*80)

    soup = BeautifulSoup(MOCK_HTML, 'lxml')

    # Check what the extractor finds
    extractor = SpecExtractor()

    # Get field definition
    field_def = extractor.field_registry.get_field("interface_items")
    print(f"\nField definition:")
    print(f"  Field code: {field_def.field_code}")
    print(f"  Field name: {field_def.field_name}")
    print(f"  Value type: {field_def.value_type}")
    print(f"  Search terms: {field_def.get_all_search_terms()}")

    # Test extraction
    print(f"\nTesting extraction...")
    results, warnings = extractor.extract_all_fields(MOCK_HTML)

    # Get interface_items result
    interface_result = results.get("interface_items")
    print(f"\nExtraction result:")
    print(f"  Raw value: {interface_result.raw_value}")
    print(f"  Normalized value: {interface_result.normalized_value}")
    print(f"  Confidence: {interface_result.confidence}")
    print(f"  Method: {interface_result.extraction_method}")

    # Debug table structure
    print(f"\n--- Debugging table structure ---")
    rows = soup.find_all('tr')
    print(f"Found {len(rows)} table rows")

    for i, row in enumerate(rows):
        cells = row.find_all(['td', 'th'])
        print(f"\nRow {i}: {len(cells)} cells")
        for j, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            print(f"  Cell {j}: '{cell_text[:50]}'")
            # Check for ul/li elements
            uls = cell.find_all('ul')
            lis = cell.find_all('li')
            if uls:
                print(f"    -> Found {len(uls)} <ul> elements")
            if lis:
                print(f"    -> Found {len(lis)} <li> elements:")
                for k, li in enumerate(lis):
                    print(f"       {k}: '{li.get_text(strip=True)}'")

    # Debug list structure
    print(f"\n--- Debugging list structure ---")
    all_lis = soup.find_all('li')
    print(f"Found {len(all_lis)} <li> elements in total:")
    for i, li in enumerate(all_lis):
        print(f"  {i}: '{li.get_text(strip=True)}'")

    # Try manual extraction
    print(f"\n--- Manual extraction attempt ---")
    rows = soup.find_all('tr')
    for row in rows:
        cells = row.find_all(['td', 'th'])
        for i, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True).lower()
            if 'interface' in cell_text:
                print(f"Found 'Interface' in cell {i}")
                if i + 1 < len(cells):
                    value_cell = cells[i + 1]
                    print(f"Value cell content (raw):")
                    print(f"  {value_cell.prettify()[:200]}")
                    print(f"\nValue cell text: '{value_cell.get_text(strip=True)}'")
                    lis = value_cell.find_all('li')
                    print(f"Found {len(lis)} <li> elements in value cell:")
                    for li in lis:
                        print(f"  - '{li.get_text(strip=True)}'")


if __name__ == "__main__":
    main()
