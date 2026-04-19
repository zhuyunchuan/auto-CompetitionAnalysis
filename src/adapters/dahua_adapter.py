"""
Dahua brand adapter - uses Playwright for JS-rendered pages.

Entry URL: https://www.dahuasecurity.com/products/network-products/network-cameras
Target series: WizSense 2, WizSense 3 (dynamically discovered)

Improvements v2:
- Reuses a single Playwright browser instance across calls
- Discovers ALL subseries by clicking filter tabs on series pages
- Collects products from every subseries tab
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.adapters.base_adapter import BrandAdapter
from src.core.types import CatalogItem
from src.crawler.http_client import HttpClient

logger = logging.getLogger(__name__)


class _Browser:
    """Lazy singleton for Playwright browser reuse."""

    def __init__(self):
        self._pw = None
        self._browser = None

    def _ensure(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)

    def new_page(self):
        self._ensure()
        return self._browser.new_page()

    def close(self):
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw:
            self._pw.stop()
            self._pw = None


_browser = _Browser()


def _playwright_get(url: str, wait_ms: int = 3000) -> str:
    """Fetch a JS-rendered page with Playwright (reuses browser)."""
    page = _browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)
        return page.content()
    finally:
        page.close()


def _playwright_get_with_filters(url: str, wait_ms: int = 2000) -> dict:
    """
    Load a series page, discover tab navigation, click each subseries tab,
    and return {subseries_name: html_content} for each tab.

    Dahua uses div.tabs-li elements as clickable category tabs on series pages.

    Returns:
        dict mapping subseries display name to page HTML after clicking that tab.
    """
    results = {}
    page = _browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)

        # Find tab elements: Dahua uses div.tabs-li for subseries navigation
        tab_els = page.query_selector_all("div.tabs-li")
        tabs = []
        for el in tab_els:
            text = el.inner_text().strip()
            if text and 2 < len(text) < 50:
                tabs.append((text, el))

        logger.info(f"Found {len(tabs)} subseries tabs: {[t[0] for t in tabs]}")

        for tab_name, el in tabs:
            try:
                el.click()
                page.wait_for_timeout(wait_ms)
                tab_html = page.content()
                results[tab_name] = tab_html
                logger.debug(f"Captured tab: {tab_name}")
            except Exception as e:
                logger.warning(f"Failed to click tab '{tab_name}': {e}")

        # If no tabs found, capture default page
        if not results:
            results["default"] = page.content()

    finally:
        page.close()

    return results


class DahuaAdapter(BrandAdapter):
    BASE_URL = "https://www.dahuasecurity.com"
    ENTRY_URL = f"{BASE_URL}/products/network-products/network-cameras"

    TARGET_SERIES = ["WizSense 3 Series", "WizSense 2 Series"]

    def __init__(self, http_client: Optional[HttpClient] = None, use_playwright: bool = True):
        self.http_client = http_client or HttpClient(timeout_sec=30, retry_times=3)
        self.use_playwright = use_playwright
        self._series_urls: dict = {}  # {name: url}
        self._subseries_data: dict = {}  # {(series_l1, subseries_name): html}

    def _fetch(self, url: str) -> str:
        if self.use_playwright:
            try:
                return _playwright_get(url)
            except Exception as e:
                logger.warning(f"Playwright failed for {url}: {e}, falling back to httpx")
        return self.http_client.get(url) or ""

    def discover_series(self) -> List[str]:
        logger.info(f"Discovering series from {self.ENTRY_URL}")
        html = self._fetch(self.ENTRY_URL)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        series_map = {}

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            match = re.match(
                r"(?:https://www\.dahuasecurity\.com)?/products/network-products/network-cameras/([\w-]+)",
                href,
            )
            if match:
                slug = match.group(1)
                for target in self.TARGET_SERIES:
                    if target.lower().replace(" ", "-") == slug.lower():
                        series_map[target] = urljoin(self.BASE_URL, href)
                        break

        self._series_urls = series_map
        result = sorted(series_map.keys())
        logger.info(f"Discovered {len(result)} series: {result}")
        return result

    def discover_subseries(self, series_l1: str) -> List[str]:
        """Discover subseries by clicking tabs on the series page."""
        logger.info(f"Discovering subseries for {series_l1}")
        series_url = self._series_urls.get(series_l1, "")
        if not series_url:
            return [series_l1]

        if self.use_playwright:
            try:
                tabs_html = _playwright_get_with_filters(series_url)
                subseries_names = []

                for tab_name, html in tabs_html.items():
                    self._subseries_data[(series_l1, tab_name)] = html
                    subseries_names.append(tab_name)

                if subseries_names:
                    logger.info(f"Subseries for {series_l1}: {subseries_names}")
                    return subseries_names
            except Exception as e:
                logger.warning(f"Tab discovery failed: {e}, falling back to link parsing")

        # Fallback: parse links from single page fetch
        html = self._fetch(series_url)
        if not html:
            return [series_l1]

        soup = BeautifulSoup(html, "lxml")
        subseries = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            match = re.search(r"/network-cameras/[\w-]+/([\w-]+)/(?:ipc|dh)", href, re.I)
            if match:
                sub = match.group(1)
                subseries.add(sub.replace("-", " ").title())

        return sorted(subseries) if subseries else [series_l1]

    def list_products(self, series_l1: str, series_l2: str) -> List[CatalogItem]:
        """List products from cached subseries HTML or re-fetch."""
        logger.info(f"Listing products for {series_l1} / {series_l2}")

        # Try cached HTML first
        html = self._subseries_data.get((series_l1, series_l2))

        if not html:
            # Fallback: fetch series page
            series_url = self._series_urls.get(series_l1, "")
            if series_url:
                html = self._fetch(series_url)

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        products = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            match = re.search(
                r"/network-cameras/[\w-]+/([\w-]+)/(ipc-[\w-]+|dh-[\w-]+)",
                href, re.I,
            )
            if not match:
                continue

            model_slug = match.group(2)
            model = model_slug.upper()

            if model in seen:
                continue
            seen.add(model)

            product_url = urljoin(self.BASE_URL, href)
            products.append(CatalogItem(
                brand="dahua",
                series_l1=series_l1,
                series_l2=series_l2,
                model=model,
                name=model,
                url=product_url,
                locale="en",
            ))

        logger.info(f"Found {len(products)} products for {series_l2}")
        return products

    def fetch_product_detail(self, url: str) -> str:
        logger.debug(f"Fetching detail: {url}")
        return self._fetch(url)

    def close(self):
        """Clean up browser resources."""
        _browser.close()
