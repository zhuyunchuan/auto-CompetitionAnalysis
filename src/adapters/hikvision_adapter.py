"""
Hikvision brand adapter for product hierarchy discovery and detail fetching.

This adapter handles:
- Series L1 discovery from entry page (Value, Pro, PT, etc.)
- Subseries L2 discovery from series pages
- Product listing from series/subseries pages
- Product detail fetching

Entry URL: https://www.hikvision.com/en/products/IP-Products/Network-Cameras/
Target series: Value, Pro, PT, etc. (dynamically discovered with allowlist filtering)

Improvements v2:
- Uses Playwright for JS-rendered pages (Hikvision uses JS to load filtered product lists)
- Reuses a single Playwright browser instance across calls
- Clicks filter tabs to discover series and subseries
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
    Load a series page, discover filter tabs, click each series tab,
    and return {series_name: html_content} for each tab.

    Hikvision uses filter buttons/tabs for series navigation (Value, Pro, etc.).

    Returns:
        dict mapping series display name to page HTML after clicking that tab.
    """
    results = {}
    page = _browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)

        # Find filter tab elements - Hikvision uses various selectors for tabs
        # Common patterns: button, a.tag, div.filter-item, etc.
        tab_selectors = [
            "button.filter-item",
            "a.tag-item",
            "div.series-filter button",
            "div.filter-tab",
            "button[role='tab']",
            "a[role='tab']",
        ]

        tabs = []
        for selector in tab_selectors:
            tab_els = page.query_selector_all(selector)
            if tab_els:
                for el in tab_els:
                    text = el.inner_text().strip()
                    if text and 2 < len(text) < 50:
                        tabs.append((text, el))
                if tabs:
                    break

        logger.info(f"Found {len(tabs)} filter tabs: {[t[0] for t in tabs]}")

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


class HikvisionAdapter(BrandAdapter):
    """
    Adapter for Hikvision website.

    Implements dynamic hierarchy discovery following the "page as source of truth" principle.
    Hikvision's site structure:
    - Entry page lists L1 series (Value, Pro, PT, etc.)
    - Series pages show subseries filters/tabs (L2)
    - Product cards contain model, name, and detail URL
    """

    # Base URL for Hikvision
    BASE_URL = "https://www.hikvision.com"
    ENTRY_URL = f"{BASE_URL}/en/products/IP-Products/Network-Cameras/"

    # Default series allowlist (can be overridden via config)
    DEFAULT_SERIES_ALLOWLIST = [
        "Pro",
        "Value",
        "Ultra",
        "PT",
        "Special",
        "Wi-Fi",
        "Panoramic",
    ]

    # CSS selectors based on actual page analysis
    SERIES_SELECTORS = [
        # Navigation menu (if series are listed there)
        "nav.series-nav a",
        "div.series-filter a",
        # Fallback: extract from product URLs
    ]

    PRODUCT_CARD_SELECTOR = "div.product-item"
    PRODUCT_MODEL_SELECTOR = "h3.h3-seo"
    PRODUCT_LINK_SELECTOR = "a[href*='/en/products/']"

    def __init__(
        self,
        http_client: Optional[HttpClient] = None,
        series_l1_allowlist: Optional[List[str]] = None,
        use_playwright: bool = True,
    ):
        """
        Initialize Hikvision adapter.

        Args:
            http_client: Optional HTTP client (creates default if not provided)
            series_l1_allowlist: Optional list of allowed L1 series names (None = all allowed)
            use_playwright: Whether to use Playwright for JS-rendered pages (default: True)
        """
        self.http_client = http_client or HttpClient(
            timeout_sec=30, retry_times=3, min_delay_ms=300, max_delay_ms=1200
        )
        self.series_l1_allowlist = series_l1_allowlist or self.DEFAULT_SERIES_ALLOWLIST
        self.use_playwright = use_playwright
        self._series_data: dict = {}  # {series_name: html}
        logger.info(f"HikvisionAdapter initialized with allowlist: {self.series_l1_allowlist}, use_playwright={use_playwright}")

    def _fetch(self, url: str) -> str:
        """Fetch URL with Playwright or httpx based on configuration."""
        if self.use_playwright:
            try:
                return _playwright_get(url)
            except Exception as e:
                logger.warning(f"Playwright failed for {url}: {e}, falling back to httpx")
        return self.http_client.get(url) or ""

    def discover_series(self) -> List[str]:
        """
        Discover L1 series from entry page.

        Uses Playwright to click filter tabs and capture HTML for each series.
        Falls back to parsing links if Playwright fails or is disabled.

        Returns:
            List of series names (e.g., ["Pro", "Value", "Ultra"])
        """
        logger.info(f"Discovering series from {self.ENTRY_URL}")

        if self.use_playwright:
            try:
                # Use Playwright to click filter tabs and get HTML for each series
                tabs_html = _playwright_get_with_filters(self.ENTRY_URL)
                series_names = []

                for series_name, html in tabs_html.items():
                    self._series_data[series_name] = html
                    series_names.append(series_name)

                if series_names:
                    # Filter by allowlist if configured
                    if self.series_l1_allowlist:
                        filtered = [s for s in series_names if any(kw.lower() in s.lower() for kw in self.series_l1_allowlist)]
                        if filtered:
                            logger.info(f"Discovered {len(filtered)} series (filtered): {filtered}")
                            return filtered

                    logger.info(f"Discovered {len(series_names)} series: {series_names}")
                    return series_names
            except Exception as e:
                logger.warning(f"Playwright series discovery failed: {e}, falling back to link parsing")

        # Fallback: Use httpx and parse links
        html = self.http_client.get(self.ENTRY_URL)
        if not html:
            logger.error("Failed to fetch entry page")
            return []

        soup = BeautifulSoup(html, "lxml")

        # Store discovered series: {display_name: slug}
        series_map = {}

        # Strategy 1: Find series-level links (not product detail links)
        # Series links have pattern: /hk/products/IP-Products/Network-Cameras/{slug}/ (depth=5)
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            match = re.match(r"/[^/]+/products/IP-Products/Network-Cameras/([^/]+)/?$", href)
            if match:
                slug = match.group(1)  # Keep trailing dash (e.g., "Pro-Series-EasyIP-")
                series_name = self._slug_to_series_name(slug)
                if series_name:
                    series_map[series_name] = slug
                    logger.debug(f"Found series link: {series_name} (slug: {slug})")

        # Strategy 2: Extract from product URLs
        for a in soup.find_all("a", href=re.compile(r"/Network-Cameras/([^/]+)")):
            href = a.get("href", "")
            match = re.search(r"/Network-Cameras/([^/]+)", href)
            if match:
                slug = match.group(1)
                series_name = self._slug_to_series_name(slug)
                if series_name and self._is_series_allowed(series_name):
                    if series_name not in series_map:
                        series_map[series_name] = slug
                        logger.debug(f"Found series from product URL: {series_name} (slug: {slug})")

        # Cache the slug map for URL building
        self._series_slugs = series_map

        if not series_map:
            logger.warning("No series discovered from page, using allowlist as fallback")
            return list(self.series_l1_allowlist)

        result = sorted(series_map.keys())
        logger.info(f"Discovered {len(result)} series: {result}")
        return result

    def discover_subseries(self, series_l1: str) -> List[str]:
        """
        Discover L2 subseries for a given series.

        Args:
            series_l1: The L1 series name (e.g., "Pro")

        Returns:
            List of subseries names
        """
        logger.info(f"Discovering subseries for {series_l1}")

        # Try cached HTML from discover_series first (when using Playwright with tabs)
        html = self._series_data.get(series_l1)

        if not html:
            # Fallback: fetch the entry page
            html = self._fetch(self.ENTRY_URL)

        if not html:
            return [series_l1]

        soup = BeautifulSoup(html, "lxml")

        # Try to find subseries tabs/filters in the series HTML
        subseries_set = set()

        # Look for filter items or sub-categories
        subseries_selectors = [
            "button.filter-item",
            "a.tag-item",
            "div.subcategory-item a",
            "div.filter-subitem",
        ]

        for selector in subseries_selectors:
            items = soup.select(selector)
            if items:
                for item in items:
                    text = item.get_text(strip=True)
                    if text and 2 < len(text) < 50:
                        subseries_set.add(text)
                if subseries_set:
                    break

        if subseries_set:
            result = sorted(list(subseries_set))
            logger.info(f"Discovered {len(result)} subseries: {result}")
            return result

        # No subseries found - series acts as its own subseries
        logger.info(f"No subseries found for {series_l1}, using series as default")
        return [series_l1]

    def list_products(self, series_l1: str, series_l2: str) -> List[CatalogItem]:
        """
        List products in a given series/subseries combination.

        Uses cached HTML from discover_series (when using Playwright) or fetches fresh.

        Args:
            series_l1: L1 series name (e.g., "Pro")
            series_l2: L2 subseries name

        Returns:
            List of catalog items
        """
        logger.info(f"Listing products for {series_l1} / {series_l2}")

        # Try cached HTML first (from Playwright tab clicking)
        html = self._series_data.get(series_l1)

        if not html:
            # Fallback: fetch the entry page
            html = self._fetch(self.ENTRY_URL)

        if not html:
            logger.error(f"Failed to fetch product list page")
            return []

        soup = BeautifulSoup(html, "lxml")
        products = []
        seen_models = set()

        # Find product links - Hikvision uses various patterns
        # Pattern 1: /en/products/IP-Products/Network-Cameras/{series}/{model}/
        # Pattern 2: Product cards with h3.h3-seo containing model
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            # Match product URLs
            match = re.search(r"/products/IP-Products/Network-Cameras/[^/]+/([^/]+)/?$", href)
            if not match:
                continue

            model_slug = match.group(1)
            # Extract model text from the link
            # Hikvision product links contain model in h3.h3-seo or text
            model_elem = a.select_one("h3.h3-seo")
            if model_elem:
                model = model_elem.get_text(strip=True)
            else:
                # Convert slug to model (replace dashes)
                model = model_slug.replace("-", " ")

            if not self._is_valid_model(model) and not self._is_valid_model(model_slug):
                continue

            # Use the model from h3.h3-seo if available, otherwise use slug
            final_model = model if self._is_valid_model(model) else model_slug.upper()

            if final_model in seen_models:
                continue
            seen_models.add(final_model)

            product_url = urljoin(self.BASE_URL, href)

            # Get product name from nearby text
            name_parts = a.get_text(separator=" ", strip=True).split()
            name = " ".join(name_parts[:10]) if name_parts else final_model

            product = CatalogItem(
                brand="hikvision",
                series_l1=series_l1,
                series_l2=series_l2,
                model=final_model,
                name=name,
                url=product_url,
                locale="en",
            )
            products.append(product)

        logger.info(f"Found {len(products)} products for {series_l1} / {series_l2}")
        return products

    def fetch_product_detail(self, url: str) -> str:
        """
        Fetch product detail page HTML.

        Args:
            url: Product detail page URL

        Returns:
            Raw HTML content, empty string on failure
        """
        logger.debug(f"Fetching product detail: {url}")

        html = self._fetch(url)
        if not html:
            logger.error(f"Failed to fetch product detail: {url}")
            return ""

        return html

    def close(self):
        """Clean up browser resources."""
        if self.use_playwright:
            _browser.close()
            logger.info("Browser resources cleaned up")

    def _is_series_allowed(self, series_name: str) -> bool:
        """
        Check if series matches allowlist keywords.

        Args:
            series_name: Series name to check

        Returns:
            True if series is allowed
        """
        if not self.series_l1_allowlist:
            return True

        for keyword in self.series_l1_allowlist:
            if keyword.lower() in series_name.lower():
                return True
        return False

    def _build_series_url(self, series_l1: str) -> str:
        """
        Build series page URL from series name.

        Examples:
            "Pro" -> "/en/products/IP-Products/Network-Cameras/Pro-Series/"
            "Value" -> "/en/products/IP-Products/Network-Cameras/Value-Series/"

        Args:
            series_l1: Series display name

        Returns:
            Full URL to series page
        """
        # Convert series name to URL-friendly format
        # Common patterns: "Pro" -> "Pro-Series", "Value" -> "Value-Series"
        url_suffix = series_l1.replace(" ", "-").replace("/", "-")

        # Try common URL patterns for Hikvision
        possible_patterns = [
            f"{self.BASE_URL}/en/products/IP-Products/Network-Cameras/{url_suffix}-Series/",
            f"{self.BASE_URL}/en/products/IP-Products/Network-Cameras/{url_suffix}/",
            f"{self.BASE_URL}/en/products/IP-Products/Network-Cameras/?category={url_suffix}",
        ]

        # Return the first pattern (most common)
        # If it fails, the caller will log the error
        return possible_patterns[0]

    def _slug_to_series_name(self, slug: str) -> Optional[str]:
        """
        Convert URL slug to series name.
        "Pro-Series-EasyIP-" -> "Pro"
        "Special-Series/" -> "Special"
        "value-series/" -> "Value"
        "pt-cameras/" -> "PT"
        """
        slug_clean = slug.rstrip("-").lower()
        
        # Map known slugs to series names
        slug_to_name = {
            "pro-series-easyip": "Pro",
            "special-series": "Special",
            "value-series": "Value",
            "ultra-series-smartip": "Ultra",
            "pt-cameras": "PT",
            "wi-fi-series": "Wi-Fi",
            "panoramic-series": "Panoramic",
            "colorvu-products": "ColorVu",
            "solar-powered-security-camera-setup": "Solar",
            "deepinview-series1/deepinview-series": "DeepinView",
        }
        
        if slug_clean in slug_to_name:
            return slug_to_name[slug_clean]
        
        # Try matching with allowlist
        for series in self.series_l1_allowlist:
            if series.lower() in slug_clean:
                return series
        
        return None

    def _series_name_to_slug(self, series_name: str) -> str:
        """
        Convert series name to URL slug pattern.

        Examples:
            "Pro" -> "Pro-Series" or "pro-series"
            "Value" -> "Value-Series" or "value-series"

        Args:
            series_name: Series display name

        Returns:
            URL slug pattern
        """
        # Convert to common slug format
        slug = series_name.replace(" ", "-").replace("/", "-")
        # Add common suffix
        return f"{slug}-Series"

    def _is_valid_model(self, model: str) -> bool:
        """
        Validate if a string looks like a valid Hikvision model number.

        Hikvision models typically follow patterns like:
        - DS-2CD2xxx5G0-IS
        - DS-2CD3Txxx5G2-I
        - DS-2CD4xxx5G1-IZS

        Key characteristics:
        - Starts with "DS-2CD" (most network cameras)
        - Contains letters and numbers
        - Reasonable length (10-50 characters)
        - May contain hyphens

        Args:
            model: Model string to validate

        Returns:
            True if appears to be a valid model
        """
        if not model:
            return False

        # Clean up the model string
        model = model.strip()

        # Basic length check
        if len(model) < 5 or len(model) > 50:
            return False

        # Hikvision network cameras typically start with DS-2CD
        # Be flexible with case and spacing
        if re.match(r"^DS-?2CD", model, re.IGNORECASE):
            return True

        # Some older or special series might have different prefixes
        # Allow models that contain at least one letter and one digit
        has_letter = any(c.isalpha() for c in model)
        has_digit = any(c.isdigit() for c in model)

        return has_letter and has_digit
