#!/usr/bin/env python3
"""
Analyze Hikvision product detail page DOM structure.
This script helps identify the actual HTML structure for spec extraction.
"""

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def analyze_page(url: str):
    """Fetch and analyze the DOM structure of a Hikvision product page."""

    print(f"Fetching: {url}")

    # Fetch the page
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch: {e}")
        return

    html = response.text
    soup = BeautifulSoup(html, 'lxml')

    print(f"\n=== Page Title ===")
    title = soup.find('title')
    if title:
        print(f"Title: {title.get_text(strip=True)}")

    print(f"\n=== Looking for specification containers ===")

    # Strategy 1: Look for Hikvision-specific structures
    print("\n--- Hikvision main-item structure ---")
    main_items = soup.find_all('div', class_='main-item')
    print(f"Found {len(main_items)} div.main-item elements")

    for i, item in enumerate(main_items[:10]):  # Show first 10
        title_div = item.find('div', class_='item-title')
        desc_div = item.find('div', class_='item-description')

        title_text = title_div.get_text(strip=True) if title_div else "N/A"
        desc_text = desc_div.get_text(strip=True)[:100] if desc_div else "N/A"

        print(f"\n  [{i}] Title: {title_text}")
        print(f"      Description: {desc_text}...")
        print(f"      HTML: {str(item)[:200]}...")

    # Strategy 2: Look for tech-specs-items-description-list
    print("\n--- Hikvision tech-specs-items-description-list structure ---")
    spec_items = soup.find_all('li', class_='tech-specs-items-description-list')
    print(f"Found {len(spec_items)} li.tech-specs-items-description-list elements")

    for i, item in enumerate(spec_items[:10]):
        title_span = item.find('span', class_='tech-specs-items-description__title')
        desc_span = item.find('span', class_='tech-specs-items-description__description')

        title_text = title_span.get_text(strip=True) if title_span else "N/A"
        desc_text = desc_span.get_text(strip=True)[:100] if desc_span else "N/A"

        print(f"\n  [{i}] Title: {title_text}")
        print(f"      Description: {desc_text}...")

    # Strategy 3: Look for tables
    print("\n--- Table structures ---")
    tables = soup.find_all('table')
    print(f"Found {len(tables)} table elements")

    for i, table in enumerate(tables[:5]):
        print(f"\n  Table {i}:")
        print(f"    Class: {table.get('class', [])}")
        print(f"    ID: {table.get('id', 'N/A')}")
        rows = table.find_all('tr')
        print(f"    Rows: {len(rows)}")

        # Show first 3 rows
        for j, row in enumerate(rows[:3]):
            cells = row.find_all(['td', 'th'])
            cell_texts = [cell.get_text(strip=True)[:50] for cell in cells]
            print(f"      Row {j}: {cell_texts}")

    # Strategy 4: Look for divs with spec/param/detail in class
    print("\n--- Div structures with 'spec', 'param', or 'detail' in class ---")
    spec_divs = soup.find_all('div', class_=lambda x: x and any(
        keyword in ' '.join(x).lower() for keyword in ['spec', 'param', 'detail', 'feature']
    ))
    print(f"Found {len(spec_divs)} matching div elements")

    for i, div in enumerate(spec_divs[:5]):
        print(f"\n  Div {i}:")
        print(f"    Class: {div.get('class', [])}")
        print(f"    ID: {div.get('id', 'N/A')}")
        print(f"    Text preview: {div.get_text(strip=True)[:150]}...")

    # Strategy 5: Look for description lists (dl/dt/dd)
    print("\n--- Description list structures ---")
    dls = soup.find_all('dl')
    print(f"Found {len(dls)} dl elements")

    for i, dl in enumerate(dls[:3]):
        print(f"\n  DL {i}:")
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        print(f"    Terms (dt): {len(dts)}")
        print(f"    Definitions (dd): {len(dds)}")

        # Show first 3 dt/dd pairs
        for j, (dt, dd) in enumerate(zip(dts[:3], dds[:3])):
            dt_text = dt.get_text(strip=True)[:50]
            dd_text = dd.get_text(strip=True)[:100]
            print(f"      [{j}] {dt_text} -> {dd_text}...")

    # Search for specific field keywords
    print("\n=== Searching for specific field keywords ===")

    keywords = [
        "Image Sensor",
        "Max Resolution",
        "Lens",
        "Aperture",
        "IR Range",
        "Supplement",
        "Stream",
        "Interface",
        "Deep Learning",
        "Protection",
    ]

    for keyword in keywords:
        # Find elements containing this keyword
        elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())
        if elements:
            print(f"\n--- '{keyword}' found in {len(elements)} elements ---")
            for elem in elements[:3]:
                parent = elem.parent
                print(f"  Parent tag: {parent.name if parent else 'N/A'}")
                print(f"  Parent class: {parent.get('class', []) if parent else 'N/A'}")
                print(f"  Text: {elem.strip()[:100]}...")

                # Try to find the associated value
                if parent:
                    # Check if it's in a table
                    row = parent.find_parent('tr')
                    if row:
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [cell.get_text(strip=True)[:80] for cell in cells]
                        print(f"  Table row: {cell_texts}")

                    # Check for Hikvision main-item structure
                    main_item = parent.find_parent('div', class_='main-item')
                    if main_item:
                        desc_div = main_item.find('div', class_='item-description')
                        if desc_div:
                            print(f"  Value: {desc_div.get_text(strip=True)[:100]}...")

    # Look for specific patterns for main stream info
    print("\n=== Searching for stream information ===")
    stream_keywords = ["Main Stream", "Sub Stream", "Third Stream", "Video Stream"]
    for keyword in stream_keywords:
        elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())
        if elements:
            print(f"\n'{keyword}': {len(elements)} occurrences")
            for elem in elements[:2]:
                context = elem.parent.get_text(strip=True)[:200]
                print(f"  Context: {context}...")

if __name__ == "__main__":
    # Test URL from user request
    test_url = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/DS-2CD2085G1-I/"

    analyze_page(test_url)
