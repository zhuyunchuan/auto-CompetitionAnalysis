"""
Product catalog collector for discovered hierarchies.

This module collects product catalogs (list of products with metadata)
by iterating through discovered hierarchies and using brand adapters.
"""

import logging
from typing import List

from src.adapters.base_adapter import BrandAdapter
from src.core.types import CatalogItem, HierarchyNode

logger = logging.getLogger(__name__)


class CatalogCollector:
    """
    Collects product catalogs from discovered hierarchies.

    This class iterates through hierarchy nodes (brand/series/subseries)
    and collects product lists using brand adapters.
    """

    def __init__(self, adapters: List[BrandAdapter]):
        """
        Initialize the catalog collector.

        Args:
            adapters: List of brand adapter instances
        """
        self.adapters = adapters
        self.collected_items: List[CatalogItem] = []

    def collect_all(
        self, hierarchy_nodes: List[HierarchyNode]
    ) -> List[CatalogItem]:
        """
        Collect product catalogs for all hierarchy nodes.

        Args:
            hierarchy_nodes: List of discovered hierarchy nodes

        Returns:
            List of all catalog items (products)

        Raises:
            Exception: If collection fails for any hierarchy
        """
        all_items = []
        total_nodes = len(hierarchy_nodes)

        for idx, node in enumerate(hierarchy_nodes, 1):
            try:
                node_items = self._collect_for_node(node)
                all_items.extend(node_items)

                logger.info(
                    f"[{idx}/{total_nodes}] Collected {len(node_items)} products "
                    f"for {node.brand}/{node.series_l1}"
                    f"{f'/{node.series_l2}' if node.series_l2 else ''}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to collect catalog for "
                    f"{node.brand}/{node.series_l1}/"
                    f"{node.series_l2 if node.series_l2 else ''}: {e}",
                    exc_info=True
                )
                # Continue with other nodes even if one fails
                continue

        self.collected_items = all_items
        logger.info(f"Total catalog items collected: {len(all_items)}")
        return all_items

    def _collect_for_node(self, node: HierarchyNode) -> List[CatalogItem]:
        """
        Collect catalog items for a single hierarchy node.

        Args:
            node: Hierarchy node (brand/series/subseries)

        Returns:
            List of catalog items for this node

        Raises:
            ValueError: If no adapter found for brand
            Exception: If adapter fails to list products
        """
        # Find adapter for this brand
        adapter = self._get_adapter_for_brand(node.brand)
        if adapter is None:
            raise ValueError(f"No adapter found for brand: {node.brand}")

        # If node is L1 (no subseries), collect all products
        # If node is L2 (has subseries), collect products for that subseries
        series_l1 = node.series_l1
        series_l2 = node.series_l2 or ""  # Empty string for L1 nodes

        try:
            items = adapter.list_products(series_l1, series_l2)

            # Validate that all items have correct hierarchy
            for item in items:
                if item.brand != node.brand:
                    logger.warning(
                        f"Item brand mismatch: expected {node.brand}, "
                        f"got {item.brand}. Overwriting."
                    )
                    # Create new item with correct brand (items are frozen)
                    item = CatalogItem(
                        brand=node.brand,
                        series_l1=item.series_l1,
                        series_l2=item.series_l2,
                        model=item.model,
                        name=item.name,
                        url=item.url,
                        locale=item.locale,
                    )

                if item.series_l1 != series_l1:
                    logger.warning(
                        f"Item series_l1 mismatch: expected {series_l1}, "
                        f"got {item.series_l1}. Overwriting."
                    )
                    item = CatalogItem(
                        brand=item.brand,
                        series_l1=series_l1,
                        series_l2=item.series_l2,
                        model=item.model,
                        name=item.name,
                        url=item.url,
                        locale=item.locale,
                    )

                if item.series_l2 != series_l2:
                    logger.warning(
                        f"Item series_l2 mismatch: expected {series_l2}, "
                        f"got {item.series_l2}. Overwriting."
                    )
                    item = CatalogItem(
                        brand=item.brand,
                        series_l1=item.series_l1,
                        series_l2=series_l2,
                        model=item.model,
                        name=item.name,
                        url=item.url,
                        locale=item.locale,
                    )

            return items

        except Exception as e:
            logger.error(
                f"Adapter failed to list products for "
                f"{node.brand}/{series_l1}/{series_l2}: {e}"
            )
            raise

    def _get_adapter_for_brand(self, brand: str) -> BrandAdapter:
        """
        Get adapter instance for a specific brand.

        Args:
            brand: Brand name (e.g., "HIKVISION")

        Returns:
            BrandAdapter instance or None if not found
        """
        adapter_name = brand.lower()

        for adapter in self.adapters:
            current_adapter_name = adapter.__class__.__name__.replace('Adapter', '').lower()
            if current_adapter_name == adapter_name:
                return adapter

        return None

    def get_items_by_brand(self, brand: str) -> List[CatalogItem]:
        """
        Get all catalog items for a specific brand.

        Args:
            brand: Brand name (e.g., "HIKVISION")

        Returns:
            List of catalog items for the brand
        """
        return [
            item for item in self.collected_items if item.brand == brand
        ]

    def get_items_by_series(
        self, brand: str, series_l1: str, series_l2: str = None
    ) -> List[CatalogItem]:
        """
        Get all catalog items for a specific series.

        Args:
            brand: Brand name (e.g., "HIKVISION")
            series_l1: L1 series name
            series_l2: L2 subseries name (optional)

        Returns:
            List of catalog items for the series
        """
        items = [
            item for item in self.collected_items
            if item.brand == brand and item.series_l1 == series_l1
        ]

        if series_l2 is not None:
            items = [item for item in items if item.series_l2 == series_l2]

        return items

    def detect_duplicates(self) -> dict:
        """
        Detect duplicate products in the catalog.

        Duplicates are identified by (brand, series_l1, series_l2, model) tuple.

        Returns:
            Dictionary with duplicate statistics
        """
        # Group by (brand, series_l1, series_l2, model)
        key_to_items = {}
        for item in self.collected_items:
            key = (item.brand, item.series_l1, item.series_l2, item.model)
            if key not in key_to_items:
                key_to_items[key] = []
            key_to_items[key].append(item)

        # Find duplicates
        duplicates = {
            key: items
            for key, items in key_to_items.items()
            if len(items) > 1
        }

        return {
            'has_duplicates': len(duplicates) > 0,
            'duplicate_count': len(duplicates),
            'duplicates': {
                f"{k[0]}/{k[1]}/{k[2]}/{k[3]}": [
                    {'url': i.url, 'name': i.name}
                    for i in items
                ]
                for k, items in duplicates.items()
            },
        }

    def validate_completeness(self) -> dict:
        """
        Validate that all catalog items have required fields.

        Returns:
            Dictionary with validation results
        """
        issues = []

        for idx, item in enumerate(self.collected_items):
            # Check required fields
            if not item.brand:
                issues.append(f"Item {idx}: Missing brand")
            if not item.series_l1:
                issues.append(f"Item {idx}: Missing series_l1")
            if not item.series_l2:
                issues.append(f"Item {idx}: Missing series_l2")
            if not item.model:
                issues.append(f"Item {idx}: Missing model")
            if not item.url:
                issues.append(f"Item {idx}: Missing URL")
            if not item.name:
                issues.append(f"Item {idx}: Missing name")

            # Check URL format
            if item.url and not item.url.startswith(('http://', 'https://')):
                issues.append(f"Item {idx} ({item.model}): Invalid URL format")

        return {
            'valid': len(issues) == 0,
            'total_items': len(self.collected_items),
            'issues_count': len(issues),
            'issues': issues[:20],  # Limit to first 20 issues
        }

    def get_summary(self) -> dict:
        """
        Get summary statistics of collected catalog.

        Returns:
            Dictionary with summary statistics
        """
        brands = set(item.brand for item in self.collected_items)
        series_l1 = set(item.series_l1 for item in self.collected_items)
        series_l2 = set(item.series_l2 for item in self.collected_items)
        models = set(item.model for item in self.collected_items)

        # Count items per brand
        items_per_brand = {}
        for brand in brands:
            items_per_brand[brand] = len([
                item for item in self.collected_items if item.brand == brand
            ])

        return {
            'total_items': len(self.collected_items),
            'total_brands': len(brands),
            'total_unique_series_l1': len(series_l1),
            'total_unique_series_l2': len(series_l2),
            'total_unique_models': len(models),
            'items_per_brand': items_per_brand,
            'brands': sorted(list(brands)),
        }
