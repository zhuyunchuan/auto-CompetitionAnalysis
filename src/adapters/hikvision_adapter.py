"""
Hikvision brand adapter for product hierarchy discovery and detail fetching.

This adapter handles:
- Series L1 discovery from entry page (Value, Pro, PT, etc.)
- Subseries L2 discovery from series pages
- Product listing from series/subseries pages
- Product detail fetching

Entry URL: https://www.hikvision.com/en/products/IP-Products/Network-Cameras/
Target series: Value, Pro, PT, etc. (dynamically discovered with allowlist filtering)
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
    ):
        """
        Initialize Hikvision adapter.

        Args:
            http_client: Optional HTTP client (creates default if not provided)
            series_l1_allowlist: Optional list of allowed L1 series names (None = all allowed)
        """
        self.http_client = http_client or HttpClient(
            timeout_sec=30, retry_times=3, min_delay_ms=300, max_delay_ms=1200
        )
        self.series_l1_allowlist = series_l1_allowlist or self.DEFAULT_SERIES_ALLOWLIST
        logger.info(f"HikvisionAdapter initialized with allowlist: {self.series_l1_allowlist}")

    def discover_series(self) -> List[str]:
        """
        Discover L1 series from entry page.

        Strategy: Find series-level links on the page (depth-5 URLs under Network-Cameras/).
        Also extract series from product URLs.

        Returns:
            List of series names (e.g., ["Pro", "Value", "Ultra"])
        """
        logger.info(f"Discovering series from {self.ENTRY_URL}")

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

        # Use the entry page to find products grouped by series slug
        slug = getattr(self, '_series_slugs', {}).get(series_l1, '')
        if not slug:
            logger.warning(f"No slug found for {series_l1}")
            return [series_l1]

        # The entry page already contains products with their series slugs
        # Subseries are just the series slug itself for now
        # (Hikvision doesn't have a clear L2 subseries structure on the page)
        html = self.http_client.get(self.ENTRY_URL)
        if not html:
            return [series_l1]

        soup = BeautifulSoup(html, "lxml")
        
        # Find product links matching this series slug
        subseries_set = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            # Match: /en/products/IP-Products/Network-Cameras/{slug}/{model}/
            match = re.match(
                r"/[^/]+/products/IP-Products/Network-Cameras/" + re.escape(slug) + r"/([^/]+)/",
                href
            )
            if match:
                sub_slug = match.group(1)
                if sub_slug and sub_slug != slug:
                    subseries_set.add(sub_slug)

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

        Uses the entry page and filters by series slug from product URLs.

        Args:
            series_l1: L1 series name (e.g., "Pro")
            series_l2: L2 subseries name

        Returns:
            List of catalog items
        """
        logger.info(f"Listing products for {series_l1} / {series_l2}")

        slug = getattr(self, '_series_slugs', {}).get(series_l1, '')
        if not slug:
            slug = self._series_name_to_slug(series_l1)

        html = self.http_client.get(self.ENTRY_URL)
        if not html:
            logger.error(f"Failed to fetch product list page")
            return []

        soup = BeautifulSoup(html, "lxml")
        products = []
        seen_models = set()

        # Find product links matching: /en/products/IP-Products/Network-Cameras/{slug}/{model}/
        pattern = re.compile(
            r"/[^/]+/products/IP-Products/Network-Cameras/" + re.escape(slug) + r"/([^/]+)/?$"
        )
        for a in soup.find_all("a", href=pattern):
            href = a.get("href", "")
            match = pattern.search(href)
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

            if model in seen_models:
                continue
            seen_models.add(model)

            product_url = urljoin(self.BASE_URL, href)

            # Get product name from nearby text
            name_parts = a.get_text(separator=" ", strip=True).split()
            name = " ".join(name_parts[:10]) if name_parts else model

            product = CatalogItem(
                brand="hikvision",
                series_l1=series_l1,
                series_l2=series_l2,
                model=model,
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

        html = self.http_client.get(url)
        if not html:
            logger.error(f"Failed to fetch product detail: {url}")
            return ""

        return html

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
