"""
Static Dahua adapter that uses known product list instead of dynamic discovery.

This is a workaround for when Playwright is not working properly.
"""

import logging
import sys
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.adapters.base_adapter import BrandAdapter
from src.core.types import CatalogItem
from src.crawler.http_client import HttpClient

logger = logging.getLogger(__name__)


class DahuaAdapter(BrandAdapter):
    """
    Dahua adapter that uses a static list of known products.

    This adapter bypasses the dynamic discovery issues and directly
    uses a hardcoded list of known products for testing.
    """

    BASE_URL = "https://www.dahuasecurity.com"
    TARGET_SERIES = ["WizSense 2 Series", "WizSense 3 Series"]

    def __init__(self, http_client: HttpClient = None, use_playwright: bool = False):
        # use_playwright parameter is ignored but kept for compatibility
        self.http_client = http_client or HttpClient(timeout_sec=30, retry_times=3)
        self._products = {}

        # Import known products
        try:
            from known_dahua_products import KNOWN_PRODUCTS
            self._products = KNOWN_PRODUCTS
        except ImportError:
            logger.warning("Could not import known_dahua_products, using empty list")
            self._products = {}

    def discover_series(self) -> List[str]:
        """Return the target series."""
        logger.info(f"Using static series discovery: {self.TARGET_SERIES}")
        return self.TARGET_SERIES

    def discover_subseries(self, series_l1: str) -> List[str]:
        """Return the series itself as subseries."""
        logger.info(f"Using static subseries for {series_l1}")
        # Each series is its own subseries
        if series_l1 in self._products:
            return [series_l1]
        return [series_l1]

    def list_products(self, series_l1: str, series_l2: str) -> List[CatalogItem]:
        """List products from the static list."""
        logger.info(f"Listing static products for {series_l1}")

        products = []
        if series_l1 not in self._products:
            logger.warning(f"No products found for {series_l1}")
            return products

        for model, url in self._products[series_l1]:
            products.append(CatalogItem(
                brand="dahua",
                series_l1=series_l1,
                series_l2=series_l2 or series_l1,
                model=model,
                name=model,
                url=url,
                locale="en",
            ))

        logger.info(f"Found {len(products)} static products for {series_l1}")
        return products

    def fetch_product_detail(self, url: str) -> str:
        """Fetch product detail page."""
        logger.debug(f"Fetching detail: {url}")
        return self.http_client.get(url) or ""

    def close(self):
        """Clean up resources."""
        pass
