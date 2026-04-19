#!/usr/bin/env python3
"""Inspect Dahua HTML structure to debug extraction."""

import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from src.crawler.http_client import HttpClient


def inspect_dahua_page(url: str):
    """Inspect a Dahua product page structure."""
    print(f"Fetching: {url}")
    client = HttpClient(timeout_sec=30, retry_times=3)
    html = client.get(url)

    if not html:
        print("Failed to fetch")
        return

    print(f"Fetched {len(html)} characters\n")

    soup = BeautifulSoup(html, 'lxml')

    # Check for various spec containers
    print("=== Checking for spec containers ===\n")

    # Check for tables
    tables = soup.find_all('table')
    print(f"Tables found: {len(tables)}")
    for i, table in enumerate(tables[:3]):
        classes = table.get('class', [])
        print(f"  Table {i}: class={classes}")

    # Check for div with spec-related classes
    spec_divs = soup.find_all('div', class_=lambda x: x and 'spec' in str(x).lower())
    print(f"\nDivs with 'spec' in class: {len(spec_divs)}")
    for i, div in enumerate(spec_divs[:3]):
        classes = div.get('class', [])
        print(f"  Div {i}: class={classes}")

    # Check for detail/param classes
    detail_divs = soup.find_all('div', class_=lambda x: x and any(kw in str(x).lower() for kw in ['detail', 'param', 'info']))
    print(f"\nDivs with 'detail'/'param'/'info' in class: {len(detail_divs)}")

    # Look for tables inside specific containers
    print("\n=== Checking specific Dahua selectors ===\n")

    # Try to find the actual spec table
    # Dahua often uses specific class names
    potential_containers = [
        ('div.parameter-list', soup.find_all('div', class_='parameter-list')),
        ('div.specification', soup.find_all('div', class_='specification')),
        ('div.specs', soup.find_all('div', class_='specs')),
        ('div.detail-params', soup.find_all('div', class_='detail-params')),
        ('table.params-table', soup.find_all('table', class_='params-table')),
        ('div.spec-table', soup.find_all('div', class_='spec-table')),
    ]

    for selector, elements in potential_containers:
        if elements:
            print(f"Found {len(elements)} elements for '{selector}'")
            for el in elements[:2]:
                print(f"  Classes: {el.get('class', [])}")

    # Look for any table and inspect its structure
    print("\n=== Inspecting first table structure ===\n")
    if tables:
        first_table = tables[0]
        rows = first_table.find_all('tr')
        print(f"First table has {len(rows)} rows")

        # Print first few rows
        for i, row in enumerate(rows[:5]):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)[:50]
                value = cells[1].get_text(strip=True)[:50]
                print(f"  Row {i}: [{label}] => [{value}]")
            else:
                print(f"  Row {i}: {len(cells)} cells")

    # Save a sample of the HTML for manual inspection
    print("\n=== Saving HTML sample ===\n")
    output_file = Path("dahua_html_sample.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        # Save first 50000 chars
        f.write(html[:50000])
    print(f"Saved first 50000 chars to {output_file}")


def main():
    """Inspect Dahua pages."""
    test_urls = [
        "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-2-series/ipc-hfw3541e-sp-ased.html",
        "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3541t1-asp-sed.html"
    ]

    for url in test_urls:
        print("\n" + "="*80)
        inspect_dahua_page(url)
        print("\n")


if __name__ == "__main__":
    main()
