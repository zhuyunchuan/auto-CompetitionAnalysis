#!/usr/bin/env python3
"""
Check for missing fields on Hikvision page.
"""

import httpx
from bs4 import BeautifulSoup

def check_missing_fields(url: str):
    """Check for fields that weren't found."""

    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, 'lxml')

    page_text = soup.get_text().lower()
    main_items = soup.find_all('div', class_='main-item')

    print("=== Checking for supplement_light_type ===")

    # Check for IR-related keywords
    ir_keywords = ['infrared', 'ir led', 'ir range', 'supplement light', 'white light', 'laser']
    for keyword in ir_keywords:
        if keyword in page_text:
            print(f"Found keyword: '{keyword}'")

    # Look for "IR Range" to infer IR type
    for item in main_items:
        title_div = item.find('div', class_='item-title')
        if title_div and 'ir range' in title_div.get_text().lower():
            detail_div = item.find('div', class_='item-title-detail')
            if detail_div:
                print(f"\nIR Range found: {detail_div.get_text(strip=True)}")
                print(f"-> Inferred supplement_light_type: IR")
                break

    print("\n=== Checking for deep_learning_function_categories ===")

    dl_keywords = ['deep learning', 'smart', 'intelligen', 'analytics', 'detection']
    for keyword in dl_keywords:
        if keyword in page_text:
            print(f"Found keyword: '{keyword}'")

    # Look for smart features sections
    for item in main_items:
        title_div = item.find('div', class_='item-title')
        if title_div:
            title_text = title_div.get_text(strip=True).lower()
            if any(kw in title_text for kw in ['smart', 'intelligence', 'deep learning', 'analytics']):
                detail_div = item.find('div', class_='item-title-detail')
                if detail_div:
                    print(f"\nFound: {title_div.get_text(strip=True)}")
                    print(f"Value: {detail_div.get_text(strip=True)[:200]}")

    # Also check for headings with these keywords
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    for heading in headings:
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in ['smart', 'intelligence', 'deep learning', 'analytics']):
            print(f"\nFound heading: {heading.get_text(strip=True)}")
            # Get next few elements
            next_elem = heading.find_next_sibling()
            if next_elem:
                print(f"Next element: {next_elem.get_text(strip=True)[:200]}")

    print("\n=== Checking for approval_anti_corrosion_protection ===")

    # Look for IK ratings or anti-corrosion mentions
    anti_corrosion_keywords = ['ik10', 'ik rating', 'anti-corrosion', 'vandal proof', 'vandal-proof']
    for keyword in anti_corrosion_keywords:
        if keyword in page_text:
            print(f"Found keyword: '{keyword}'")

    # Check in main items
    for item in main_items:
        title_div = item.find('div', class_='item-title')
        if title_div:
            title_text = title_div.get_text(strip=True).lower()
            if any(kw in title_text for kw in ['ik', 'vandal', 'anti-corrosion']):
                detail_div = item.find('div', class_='item-title-detail')
                if detail_div:
                    print(f"\nFound: {title_div.get_text(strip=True)}")
                    print(f"Value: {detail_div.get_text(strip=True)}")

    print("\n=== Looking at all main-item titles to see available fields ===")
    for i, item in enumerate(main_items[:30]):
        title_div = item.find('div', class_='item-title')
        if title_div:
            print(f"{i+1}. {title_div.get_text(strip=True)}")

if __name__ == "__main__":
    test_url = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/DS-2CD2085G1-I/"
    check_missing_fields(test_url)
