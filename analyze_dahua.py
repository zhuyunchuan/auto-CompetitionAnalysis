#!/usr/bin/env python3
"""
Analyze Dahua website structure.
"""

import sys
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.crawler.http_client import HttpClient
from bs4 import BeautifulSoup

def analyze_dahua():
    """Analyze Dahua entry page and product detail page."""

    base_url = "https://www.dahuasecurity.com"
    http_client = HttpClient()

    # Test entry page
    entry_url = f"{base_url}/products/network-products/network-cameras"
    print(f"=== Analyzing Dahua Entry Page ===")
    print(f"URL: {entry_url}\n")

    html = http_client.get(entry_url)
    if html:
        soup = BeautifulSoup(html, 'lxml')

        print(f"Status: Fetched successfully ({len(html)} bytes)\n")

        # Look for product items
        print("--- Looking for product-item elements ---")
        product_items = soup.find_all("a", class_="product-item")
        print(f"Found {len(product_items)} product-item elements")

        for i, item in enumerate(product_items[:5]):
            title_elem = item.find("h3", class_="product-item-title")
            if title_elem:
                print(f"\n  [{i}] {title_elem.get_text(strip=True)}")
                print(f"      Link: {item.get('href', 'N/A')}")

        # Look for series links
        print("\n--- Looking for series links ---")
        all_links = soup.find_all("a", href=True)
        series_links = [
            link for link in all_links
            if "/products/network-products/network-cameras/" in link.get("href", "")
            and link.get("href", "").count("/") > 4  # Deeper than entry page
        ]

        print(f"Found {len(series_links)} potential series links")
        for i, link in enumerate(series_links[:5]):
            print(f"\n  [{i}] {link.get_text(strip=True)[:50]}")
            print(f"      Href: {link.get('href', 'N/A')}")
    else:
        print("Failed to fetch entry page")

    # Test a product detail page
    print(f"\n\n=== Analyzing Dahua Product Detail Page ===")

    # Try a known Dahua product URL
    test_product_url = f"{base_url}/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3541t1-as-led"
    print(f"URL: {test_product_url}\n")

    html = http_client.get(test_product_url)
    if html:
        soup = BeautifulSoup(html, 'lxml')

        print(f"Status: Fetched successfully ({len(html)} bytes)\n")

        # Look for specification containers
        print("--- Looking for specification containers ---")

        # Check for tables
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables")

        # Check for spec divs
        spec_divs = soup.find_all('div', class_=lambda x: x and any(
            kw in ' '.join(x).lower() for kw in ['spec', 'param', 'detail', 'feature']
        ))
        print(f"Found {len(spec_divs)} spec-related divs")

        # Check for description lists
        dls = soup.find_all('dl')
        print(f"Found {len(dls)} description lists")

        # Look for main-item like Hikvision
        main_items = soup.find_all('div', class_=lambda x: x and 'main-item' in ' '.join(x).lower())
        print(f"Found {len(main_items)} main-item-like divs")

        # Print page title
        title = soup.find('title')
        if title:
            print(f"\nPage Title: {title.get_text(strip=True)}")

        # Look for key specification fields
        print("\n--- Searching for key specification fields ---")
        keywords = ["Image Sensor", "Resolution", "Lens", "IR", "Stream", "Interface"]

        for keyword in keywords:
            elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())
            if elements:
                print(f"\n'{keyword}': {len(elements)} occurrences")
                for elem in elements[:2]:
                    parent = elem.parent
                    if parent:
                        print(f"  Parent: {parent.name if parent else 'N/A'}")
                        print(f"  Class: {parent.get('class', [])}")
                        context = parent.get_text(strip=True)[:100]
                        print(f"  Context: {context}...")
    else:
        print("Failed to fetch product page")

if __name__ == "__main__":
    analyze_dahua()
