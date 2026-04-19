"""
Hierarchy discovery task for OpenClaw DAG.

This module implements the discover_hierarchy task which discovers product
hierarchies (series and subseries) from competitor websites using brand adapters.

Task: discover_hierarchy
Dependencies: None
Output: Hierarchy nodes stored in database
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from src.storage.repo_hierarchy import HierarchyRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.crawler.hierarchy_discovery import HierarchyDiscoveryOrchestrator
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def discover_hierarchy(
    run_id: str,
    adapters: list,
    **kwargs
) -> Dict[str, Any]:
    """
    Discover product hierarchies for all configured brands.

    This task orchestrates the discovery of series and subseries hierarchies
    by delegating to brand-specific adapters. Results are stored in the
    hierarchy_snapshot table.

    Args:
        run_id: Unique run identifier (e.g., "20260418_biweekly_01")
        adapters: List of brand adapter instances (HikvisionAdapter, DahuaAdapter)
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - hierarchy_count: Number of hierarchy nodes discovered
            - brands_count: Number of brands processed
            - series_l1_count: Number of level 1 series
            - series_l2_count: Number of level 2 subseries
            - duration_seconds: Task execution time

    Raises:
        Exception: If hierarchy discovery fails for all brands
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting hierarchy discovery for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            hierarchy_repo = HierarchyRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Initialize orchestrator with adapters
            orchestrator = HierarchyDiscoveryOrchestrator(adapters)

            # Discover hierarchies
            logger.info("Discovering hierarchies for all brands")
            hierarchy_nodes = orchestrator.discover_all()

            if not hierarchy_nodes:
                raise Exception("No hierarchy nodes discovered - all brands failed")

            # Store in database
            logger.info(f"Storing {len(hierarchy_nodes)} hierarchy nodes")
            count = hierarchy_repo.batch_create_snapshots(run_id, hierarchy_nodes)

            # Calculate statistics
            brands = set(node.brand for node in hierarchy_nodes)
            l1_count = len([n for n in hierarchy_nodes if n.series_l2 is None])
            l2_count = len([n for n in hierarchy_nodes if n.series_l2 is not None])

            # Update run summary
            run_summary_repo.update_hierarchy_stats(
                run_id=run_id,
                new_series_count=l2_count
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'hierarchy_count': count,
                'brands_count': len(brands),
                'series_l1_count': l1_count,
                'series_l2_count': l2_count,
                'duration_seconds': duration,
            }

            logger.info(
                f"Hierarchy discovery completed: "
                f"{count} nodes from {len(brands)} brands "
                f"({l1_count} L1, {l2_count} L2) in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Hierarchy discovery failed after {duration:.2f}s: {e}",
            exc_info=True
        )

        # Update run summary with failure status
        try:
            db = get_database()
            with db.session() as session:
                run_summary_repo = RunSummaryRepository(session)
                run_summary_repo.update_status(
                    run_id=run_id,
                    status='failed',
                    error_message=f"discover_hierarchy failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def retry_discover_hierarchy(
    run_id: str,
    adapters: list,
    brand: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Retry hierarchy discovery for a specific brand or all brands.

    This is a helper function for manual retry of failed hierarchy discovery.

    Args:
        run_id: Unique run identifier
        adapters: List of brand adapter instances
        brand: Optional brand name to retry (if None, retry all)
        **kwargs: Additional task parameters

    Returns:
        Dictionary with retry results
    """
    logger.info(f"Retrying hierarchy discovery for run_id={run_id}, brand={brand}")

    # Filter adapters if brand specified
    if brand:
        filtered_adapters = [
            adapter for adapter in adapters
            if adapter.__class__.__name__.replace('Adapter', '').upper() == brand.upper()
        ]
        if not filtered_adapters:
            raise ValueError(f"No adapter found for brand: {brand}")
    else:
        filtered_adapters = adapters

    # Re-run discovery
    return discover_hierarchy(run_id, filtered_adapters, **kwargs)
