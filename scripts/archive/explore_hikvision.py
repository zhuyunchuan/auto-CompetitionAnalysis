#!/usr/bin/env python3
"""
Explore Hikvision page structure with Playwright.
Goal: Understand how series filtering works on the website.
"""

from playwright.sync_api import sync_playwright
import time

def main():
    print("=" * 80)
    print("Exploring Hikvision Network Cameras Page")
    print("=" * 80)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print("\n1. Navigating to entry page...")
        try:
            page.goto("https://www.hikvision.com/en/products/IP-Products/Network-Cameras/",
                      wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"   Error loading page: {e}")
            browser.close()
            return
        print("   Page loaded")

        # Try to find filter elements
        print("\n2. Looking for filter elements...")

        # Try various selectors
        selectors_to_try = [
            ("button.filter-item", "Filter buttons"),
            ("a.tag-item", "Tag items"),
            ("div.series-filter button", "Series filter buttons"),
            ("div.filter-tab", "Filter tabs"),
            ("button[role='tab']", "Tab buttons"),
            ("a[role='tab']", "Tab links"),
            ("div.tabs-li", "Tab list items"),
            ("button[class*='filter']", "Buttons with 'filter' in class"),
            ("div[class*='filter'] button", "Buttons inside filter div"),
            ("ul[class*='nav'] li", "Nav list items"),
        ]

        found_elements = []
        for selector, desc in selectors_to_try:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n   ✓ Found {len(elements)} '{desc}' elements:")
                for i, el in enumerate(elements[:10]):  # Show first 10
                    text = el.inner_text().strip()
                    print(f"      [{i}] {text[:80]}")
                found_elements.append((selector, desc, elements))

        if not found_elements:
            print("   ✗ No filter elements found!")
            print("\n3. Trying to get all clickable elements...")

            # Get all buttons and links
            all_buttons = page.query_selector_all("button")
            print(f"   Found {len(all_buttons)} button elements")

            all_links = page.query_selector_all("a")
            print(f"   Found {len(all_links)} link elements")

            # Show button texts
            print("\n   Button texts:")
            for i, btn in enumerate(all_buttons[:20]):
                text = btn.inner_text().strip()
                if text:
                    print(f"      [{i}] {text[:60]}")

        print("\n4. Looking for product cards...")

        # Try to find product cards
        product_selectors = [
            "div.product-item",
            "div[class*='product']",
            "div.item",
            "a[href*='/products/IP-Products/Network-Cameras/']",
        ]

        for selector in product_selectors:
            products = page.query_selector_all(selector)
            if products:
                print(f"   ✓ Found {len(products)} products with selector '{selector}'")

                # Show first few products
                print("\n   First 5 products on default page:")
                for i, prod in enumerate(products[:5]):
                    text = prod.inner_text().strip()[:100]
                    print(f"      [{i}] {text}")
                break

        # If we found filter elements, try clicking them
        if found_elements:
            print("\n5. Trying to click filter tabs...")

            selector, desc, elements = found_elements[0]
            print(f"   Using selector: {selector}")

            for i, el in enumerate(elements[:5]):  # Try first 5 tabs
                try:
                    text = el.inner_text().strip()
                    print(f"\n   Clicking tab [{i}]: {text}")

                    el.click()
                    page.wait_for_timeout(2000)

                    # Get product count after click
                    for prod_selector in product_selectors:
                        products = page.query_selector_all(prod_selector)
                        if products:
                            print(f"      → Found {len(products)} products")
                            # Show first 3 products
                            for j, prod in enumerate(products[:3]):
                                prod_text = prod.inner_text().strip()[:80]
                                print(f"         [{j}] {prod_text}")
                            break

                except Exception as e:
                    print(f"      ✗ Error: {e}")

        print("\n6. Checking page title and URL...")
        print(f"   Title: {page.title()}")
        print(f"   URL: {page.url}")

        print("\n" + "=" * 80)
        browser.close()

if __name__ == "__main__":
    main()
