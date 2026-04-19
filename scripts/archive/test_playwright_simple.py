#!/usr/bin/env python3
"""Simple Playwright test with different configurations."""

from playwright.sync_api import sync_playwright
import sys

def test_config(args, headless=True):
    """Test Playwright with specific browser args."""
    print(f"\nTesting with args: {args}")
    print(f"Headless: {headless}")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                args=args
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1280, 'height': 720},
                ignore_https_errors=True,
            )
            page = context.new_page()

            print("  Navigating to page...")
            page.goto(
                "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/",
                wait_until="domcontentloaded",
                timeout=30000
            )

            print("  Waiting for page load...")
            page.wait_for_timeout(3000)

            title = page.title()
            print(f"  ✓ Success! Page title: {title[:60]}")

            browser.close()
            return True

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing Playwright configurations")
    print("=" * 60)

    configs = [
        # Minimal args
        [],

        # Disable GPU
        ['--disable-gpu'],

        # No sandbox + disable GPU
        ['--no-sandbox', '--disable-gpu'],

        # More conservative settings
        [
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-web-security',
        ],

        # Very conservative
        [
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ],
    ]

    for config in configs:
        if test_config(config, headless=True):
            print(f"\n✓ Found working configuration: {config}")
            print("\nYou can use these args in hikvision_adapter.py:")
            print(f'  browser = pw.chromium.launch(headless=True, args={config})')
            return 0

    print("\n✗ All configurations failed")
    return 1

if __name__ == "__main__":
    sys.exit(main())
