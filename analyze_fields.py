#!/usr/bin/env python3
"""
Extract specific fields from Hikvision product page.
Test extraction for the 12 core fields.
"""

import httpx
from bs4 import BeautifulSoup

def extract_fields(url: str):
    """Extract the 12 core fields from Hikvision product page."""

    print(f"Fetching: {url}")

    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, 'lxml')

    # Define the 12 core fields we need
    core_fields = {
        "image_sensor": ["Image Sensor", "Sensor"],
        "max_resolution": ["Max Resolution", "Resolution", "Max. Resolution"],
        "lens_type": ["Lens Type", "Lens"],
        "aperture": ["Aperture", "Aperture Type"],
        "supplement_light_type": ["IR Type", "Supplement Light", "Supplement"],
        "supplement_light_range": ["IR Range", "IR Distance", "Supplement Light Range"],
        "main_stream_max_fps_resolution": ["Main Stream", "Main Stream Resolution"],
        "stream_count": ["Stream", "Video Stream"],
        "interface_items": ["Interface", "Communication Interface"],
        "deep_learning_function_categories": ["Deep Learning", "Smart Features", "Intelligence"],
        "approval_protection": ["Protection", "IP67"],
        "approval_anti_corrosion_protection": ["Anti-corrosion", "IK10"],
    }

    print("\n=== Extracting from main-item structure ===")

    # Method 1: div.main-item > div.item-title + div.item-title-detail
    main_items = soup.find_all('div', class_='main-item')

    for field_code, search_terms in core_fields.items():
        found = False
        for item in main_items:
            title_div = item.find('div', class_='item-title')
            if not title_div:
                continue

            title_text = title_div.get_text(strip=True)

            # Check if any search term matches
            for term in search_terms:
                if term.lower() in title_text.lower():
                    detail_div = item.find('div', class_='item-title-detail')
                    if detail_div:
                        value = detail_div.get_text(strip=True)
                        print(f"\n{field_code}:")
                        print(f"  Title: {title_text}")
                        print(f"  Value: {value[:200]}")
                        found = True
                        break
            if found:
                break

        if not found:
            print(f"\n{field_code}: NOT FOUND in main-item")

    print("\n\n=== Extracting from tech-specs-items-description-list structure ===")

    # Method 2: li.tech-specs-items-description-list
    spec_items = soup.find_all('li', class_='tech-specs-items-description-list')

    for field_code, search_terms in core_fields.items():
        found = False
        for item in spec_items:
            title_span = item.find('span', class_='tech-specs-items-description__title')
            if not title_span:
                continue

            title_text = title_span.get_text(strip=True)

            # Check if any search term matches
            for term in search_terms:
                if term.lower() in title_text.lower():
                    # Try to find the description span
                    desc_span = item.find('span', class_='tech-specs-items-description__description')
                    if desc_span:
                        value = desc_span.get_text(strip=True)
                        print(f"\n{field_code}:")
                        print(f"  Title: {title_text}")
                        print(f"  Value: {value[:200]}")
                        found = True
                        break
                    else:
                        # Value might be in a sibling span or other element
                        # Get all text from the item except the title
                        all_spans = item.find_all('span')
                        values = []
                        for span in all_spans:
                            if 'title' not in ' '.join(span.get('class', [])):
                                val = span.get_text(strip=True)
                                if val:
                                    values.append(val)

                        if values:
                            value = ' '.join(values)
                            print(f"\n{field_code}:")
                            print(f"  Title: {title_text}")
                            print(f"  Value: {value[:200]}")
                            found = True
                            break
            if found:
                break

    # Special check for stream count (look for Main Stream, Sub Stream, Third Stream)
    print("\n\n=== Checking for stream information ===")
    page_text = soup.get_text()

    if 'third stream' in page_text.lower():
        print("Stream Count: 3 (found 'Third Stream')")
    elif 'sub stream' in page_text.lower():
        print("Stream Count: 2 (found 'Sub Stream')")
    elif 'main stream' in page_text.lower():
        print("Stream Count: 1 or more (found 'Main Stream')")

    # Look for actual stream specifications
    print("\n--- Looking for stream specifications ---")
    for item in main_items:
        title_div = item.find('div', class_='item-title')
        if title_div:
            title_text = title_div.get_text(strip=True)
            if 'stream' in title_text.lower():
                detail_div = item.find('div', class_='item-title-detail')
                if detail_div:
                    value = detail_div.get_text(strip=True)
                    print(f"\n{title_text}:")
                    print(f"  {value[:300]}")

if __name__ == "__main__":
    test_url = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/DS-2CD2085G1-I/"
    extract_fields(test_url)
