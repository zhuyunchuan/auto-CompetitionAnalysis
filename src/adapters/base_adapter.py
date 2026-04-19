"""
Base adapter interface for brand-specific adapters.

This module defines the Protocol that all brand adapters must implement,
ensuring consistent integration with the pipeline.
"""

from abc import ABC, abstractmethod
from typing import List

from src.core.types import CatalogItem


class BrandAdapter(ABC):
    """
    Abstract base class for brand-specific adapters.

    Each brand adapter must implement methods to:
    1. Discover product series (L1 hierarchy)
    2. Discover subseries (L2 hierarchy)
    3. List products in a given series/subseries
    4. Fetch product detail page HTML
    """

    @abstractmethod
    def discover_series(self) -> List[str]:
        """
        Discover all L1 product series from the entry page.

        Returns:
            List of series names (e.g., ["WizSense 2 Series", "WizSense 3 Series"])
        """
        pass

    @abstractmethod
    def discover_subseries(self, series_l1: str) -> List[str]:
        """
        Discover all L2 subseries for a given series.

        Args:
            series_l1: The L1 series name

        Returns:
            List of subseries names (e.g., ["WizColor", "Active Deterrence"])
        """
        pass

    @abstractmethod
    def list_products(self, series_l1: str, series_l2: str) -> List[CatalogItem]:
        """
        List all products in a given series/subseries combination.

        Args:
            series_l1: The L1 series name
            series_l2: The L2 subseries name

        Returns:
            List of catalog items with product metadata
        """
        pass

    @abstractmethod
    def fetch_product_detail(self, url: str) -> str:
        """
        Fetch the HTML content of a product detail page.

        Args:
            url: The product detail page URL

        Returns:
            Raw HTML content as string
        """
        pass
