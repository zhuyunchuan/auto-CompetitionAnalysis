"""
Hierarchy discovery orchestrator for brand product series.

This module orchestrates the discovery of product hierarchies (series and subseries)
by delegating to brand-specific adapters.
"""

import logging
from datetime import datetime
from typing import List

from src.adapters.base_adapter import BrandAdapter
from src.core.types import HierarchyNode

logger = logging.getLogger(__name__)


class HierarchyDiscoveryOrchestrator:
    """
    Orchestrates hierarchy discovery across multiple brands.

    This class coordinates the discovery of product hierarchies by:
    1. Iterating through configured brand adapters
    2. Discovering L1 (series) for each brand
    3. Discovering L2 (subseries) for each series
    4. Building complete hierarchy nodes
    """

    def __init__(self, adapters: List[BrandAdapter]):
        """
        Initialize the orchestrator with brand adapters.

        Args:
            adapters: List of brand adapter instances
        """
        self.adapters = adapters
        self.discovered_nodes: List[HierarchyNode] = []

    def discover_all(self) -> List[HierarchyNode]:
        """
        Discover complete hierarchies for all configured brands.

        Returns:
            List of all discovered hierarchy nodes (series and subseries)

        Raises:
            Exception: If discovery fails for any brand
        """
        all_nodes = []

        for adapter in self.adapters:
            try:
                brand_nodes = self._discover_brand_hierarchy(adapter)
                all_nodes.extend(brand_nodes)
                logger.info(
                    f"Discovered {len(brand_nodes)} hierarchy nodes "
                    f"for brand {adapter.__class__.__name__}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to discover hierarchy for "
                    f"{adapter.__class__.__name__}: {e}",
                    exc_info=True
                )
                raise

        self.discovered_nodes = all_nodes
        return all_nodes

    def _discover_brand_hierarchy(self, adapter: BrandAdapter) -> List[HierarchyNode]:
        """
        Discover hierarchy for a single brand.

        Args:
            adapter: Brand adapter instance

        Returns:
            List of hierarchy nodes for the brand
        """
        brand_name = adapter.__class__.__name__.replace('Adapter', '').upper()
        nodes = []
        discovery_time = datetime.now()

        # Discover L1 series
        try:
            series_l1_list = adapter.discover_series()
            logger.info(
                f"Discovered {len(series_l1_list)} L1 series "
                f"for {brand_name}: {series_l1_list}"
            )
        except Exception as e:
            logger.error(f"Failed to discover L1 series for {brand_name}: {e}")
            raise

        # For each L1 series, discover L2 subseries
        for series_l1 in series_l1_list:
            try:
                subseries_list = adapter.discover_subseries(series_l1)
                logger.info(
                    f"Discovered {len(subseries_list)} L2 subseries "
                    f"for {brand_name}/{series_l1}"
                )

                # Create L1 node (without subseries)
                l1_node = HierarchyNode(
                    brand=brand_name,
                    series_l1=series_l1,
                    series_l2=None,
                    source="adapter.discover_series",
                    status="active",
                    discovered_at=discovery_time,
                )
                nodes.append(l1_node)

                # Create L2 nodes (with subseries)
                for series_l2 in subseries_list:
                    l2_node = HierarchyNode(
                        brand=brand_name,
                        series_l1=series_l1,
                        series_l2=series_l2,
                        source="adapter.discover_subseries",
                        status="active",
                        discovered_at=discovery_time,
                    )
                    nodes.append(l2_node)

            except Exception as e:
                logger.warning(
                    f"Failed to discover subseries for "
                    f"{brand_name}/{series_l1}: {e}. "
                    f"Skipping this series."
                )
                # Still create L1 node even if L2 discovery failed
                continue

        return nodes

    def get_series_for_brand(self, brand: str) -> List[str]:
        """
        Get all L1 series for a specific brand.

        Args:
            brand: Brand name (e.g., "HIKVISION")

        Returns:
            List of series names
        """
        series_set = {
            node.series_l1
            for node in self.discovered_nodes
            if node.brand == brand and node.series_l2 is None
        }
        return sorted(list(series_set))

    def get_subseries_for_series(
        self, brand: str, series_l1: str
    ) -> List[str]:
        """
        Get all L2 subseries for a specific brand and series.

        Args:
            brand: Brand name (e.g., "HIKVISION")
            series_l1: L1 series name

        Returns:
            List of subseries names
        """
        subseries_set = {
            node.series_l2
            for node in self.discovered_nodes
            if node.brand == brand
            and node.series_l1 == series_l1
            and node.series_l2 is not None
        }
        return sorted(list(subseries_set))

    def get_hierarchy_path(
        self, brand: str, series_l1: str, series_l2: str = None
    ) -> HierarchyNode:
        """
        Get a specific hierarchy node by brand and series path.

        Args:
            brand: Brand name (e.g., "HIKVISION")
            series_l1: L1 series name
            series_l2: L2 subseries name (optional)

        Returns:
            HierarchyNode if found

        Raises:
            ValueError: If hierarchy node not found
        """
        for node in self.discovered_nodes:
            if (
                node.brand == brand
                and node.series_l1 == series_l1
                and node.series_l2 == series_l2
            ):
                return node

        raise ValueError(
            f"Hierarchy node not found: brand={brand}, "
            f"series_l1={series_l1}, series_l2={series_l2}"
        )

    def validate_completeness(self) -> dict:
        """
        Validate that all discovered hierarchies are complete.

        Checks that:
        - All brands have at least one L1 series
        - All L1 series have at least one L2 subseries

        Returns:
            Dictionary with validation results
        """
        issues = []

        # Group nodes by brand and series
        brand_series_map = {}
        for node in self.discovered_nodes:
            if node.brand not in brand_series_map:
                brand_series_map[node.brand] = {'l1': set(), 'l2': set()}

            if node.series_l2 is None:
                brand_series_map[node.brand]['l1'].add(node.series_l1)
            else:
                brand_series_map[node.brand]['l2'].add(
                    (node.series_l1, node.series_l2)
                )

        # Check for empty brands
        for brand, data in brand_series_map.items():
            if len(data['l1']) == 0:
                issues.append(f"Brand {brand} has no L1 series")

            # Check for series without subseries
            for series_l1 in data['l1']:
                has_subseries = any(
                    s1 == series_l1 for s1, _ in data['l2']
                )
                if not has_subseries:
                    issues.append(
                        f"Brand {brand}, Series {series_l1} has no L2 subseries"
                    )

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'total_brands': len(brand_series_map),
            'total_l1_series': sum(len(d['l1']) for d in brand_series_map.values()),
            'total_l2_subseries': sum(len(d['l2']) for d in brand_series_map.values()),
        }

    def get_summary(self) -> dict:
        """
        Get summary statistics of discovered hierarchies.

        Returns:
            Dictionary with summary statistics
        """
        brands = set(node.brand for node in self.discovered_nodes)
        l1_nodes = [n for n in self.discovered_nodes if n.series_l2 is None]
        l2_nodes = [n for n in self.discovered_nodes if n.series_l2 is not None]

        return {
            'total_nodes': len(self.discovered_nodes),
            'total_brands': len(brands),
            'total_l1_series': len(l1_nodes),
            'total_l2_subseries': len(l2_nodes),
            'brands': sorted(list(brands)),
            'discovery_time': self.discovered_nodes[0].discovered_at
            if self.discovered_nodes
            else None,
        }
