#!/usr/bin/env python3
"""
Analyze Dahua product detail page structure in detail.
"""

import sys
import json
sys.path.insert(0, '/home/admin/code/auto-CompetitionAnalysis')

from src.crawler.http_client import HttpClient
from bs4 import BeautifulSoup

def analyze_dahua_product():
    """Analyze Dahua product detail page."""

    http_client = HttpClient()

    # Try a few different Dahua product URLs
    test_urls = [
        "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3541t1-as-led",
        "https://www.dahuasecurity.com/products/network-products/network-cameras/wizmind-5-series/ipc-hfw5442e-as-led",
    ]

    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Analyzing: {url}")
        print(f"{'='*80}\n")

        html = http_client.get(url)
        if not html:
            print("Failed to fetch")
            continue

        soup = BeautifulSoup(html, 'lxml')

        # Print page title
        title = soup.find('title')
        if title:
            print(f"Page Title: {title.get_text(strip=True)}\n")

        # Look for any script tags with JSON data
        print("--- Looking for JSON data in script tags ---")
        scripts = soup.find_all('script')
        json_scripts = []

        for script in scripts:
            if script.string:
                script_text = script.string
                # Look for common JSON patterns
                if any(keyword in script_text for keyword in ['specification', 'product', 'data', 'config']):
                    if '{' in script_text and '}' in script_text:
                        json_scripts.append(script_text[:200])
                        print(f"Found potential JSON script ({len(script_text)} chars)")
                        print(f"Preview: {script_text[:200]}...")
                        print()

        # Look for divs with data-* attributes
        print("\n--- Looking for data-* attributes ---")
        all_divs = soup.find_all('div', attrs={'data-json': True})
        print(f"Found {len(all_divs)} divs with data-json attribute")

        # Look for common specification patterns
        print("\n--- Looking for common specification patterns ---")

        # Pattern 1: Look for class names containing 'spec', 'param', 'detail'
        for class_name in ['spec', 'param', 'detail', 'feature', 'tech', 'info']:
            elems = soup.find_all(class_=lambda x: x and class_name in ' '.join(x).lower())
            if elems:
                print(f"\nFound {len(elems)} elements with '{class_name}' in class name")
                for i, elem in enumerate(elems[:3]):
                    print(f"  [{i}] Tag: {elem.name}, Class: {elem.get('class', [])}")
                    print(f"      Text preview: {elem.get_text(strip=True)[:100]}...")

        # Pattern 2: Look for elements with 'specification' in id
        spec_elems = soup.find_all(id=lambda x: x and 'spec' in x.lower())
        if spec_elems:
            print(f"\nFound {len(spec_elems)} elements with 'spec' in id")
            for elem in spec_elems[:3]:
                print(f"  Tag: {elem.name}, ID: {elem.get('id')}")
                print(f"  Text preview: {elem.get_text(strip=True)[:100]}...")

        # Pattern 3: Search for keywords in the entire page
        print("\n--- Searching for specification keywords ---")
        keywords = ["Image Sensor", "Sensor", "Resolution", "Lens", "IR Range", "Stream"]

        for keyword in keywords:
            # Find all text nodes containing this keyword
            elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())

            if elements:
                print(f"\n'{keyword}': {len(elements)} occurrences")

                # Show unique contexts
                seen_contexts = set()
                for elem in elements[:5]:
                    parent = elem.parent
                    if parent:
                        context = parent.get_text(strip=True)[:150]
                        if context not in seen_contexts:
                            seen_contexts.add(context)
                            print(f"  Parent: {parent.name if parent else 'N/A'}")
                            print(f"  Class: {parent.get('class', [])}")
                            print(f"  Context: {context}...")
                            print()

        # Check if page is React/Vue/Angular app
        print("\n--- Checking if page is a SPA ---")
        if len(scripts) > 10:
            print(f"Found {len(scripts)} script tags - likely a JavaScript-rendered page")
            print("Consider using Playwright for full content extraction")

        # Only analyze first URL for detailed analysis
        break

if __name__ == "__main__":
    analyze_dahua_product()
