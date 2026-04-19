"""
Product catalog and detail collection tasks for OpenClaw DAG.

This module implements two tasks:
1. crawl_product_catalog - Collect product lists from discovered hierarchies
2. fetch_product_detail - Fetch detail pages for all products

Task: crawl_product_catalog
Dependencies: discover_hierarchy
Output: Product catalog stored in database

Task: fetch_product_detail
Dependencies: crawl_product_catalog
Output: HTML snapshots stored in filesystem
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.storage.repo_hierarchy import HierarchyRepository
from src.storage.repo_catalog import CatalogRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.crawler.catalog_collector import CatalogCollector
from src.crawler.detail_collector import DetailCollector
from src.crawler.page_fetcher import PageFetcher
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def crawl_product_catalog(
    run_id: str,
    adapters: list,
    **kwargs
) -> Dict[str, Any]:
    """
    Crawl product catalogs for all discovered hierarchies.

    This task iterates through discovered hierarchy nodes and collects
    product lists using brand adapters. Results are stored in the
    product_catalog table.

    Args:
        run_id: Unique run identifier
        adapters: List of brand adapter instances
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - catalog_count: Number of products discovered
            - brands_count: Number of brands processed
            - duration_seconds: Task execution time

    Raises:
        Exception: If catalog collection fails
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting catalog crawl for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            hierarchy_repo = HierarchyRepository(session)
            catalog_repo = CatalogRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Get discovered hierarchies
            hierarchy_nodes = hierarchy_repo.get_by_run_id(run_id)
            if not hierarchy_nodes:
                raise Exception(f"No hierarchy nodes found for run_id={run_id}")

            logger.info(f"Found {len(hierarchy_nodes)} hierarchy nodes")

            # Convert to HierarchyNode objects
            from src.core.types import HierarchyNode
            hierarchy_node_objects = [
                HierarchyNode(
                    brand=node.brand,
                    series_l1=node.series_l1,
                    series_l2=node.series_l2,
                    source=node.series_source,
                    status=node.series_status,
                    discovered_at=node.discovered_at
                )
                for node in hierarchy_nodes
            ]

            # Initialize catalog collector
            collector = CatalogCollector(adapters)

            # Collect catalogs
            logger.info("Collecting product catalogs")
            catalog_items = collector.collect_all(hierarchy_node_objects)

            if not catalog_items:
                logger.warning("No catalog items collected")
                # Don't fail - continue with empty catalog
                catalog_items = []

            # Store in database
            logger.info(f"Storing {len(catalog_items)} catalog entries")
            count = catalog_repo.batch_create_catalog_entries(run_id, catalog_items)

            # Check for duplicates
            duplicates = collector.detect_duplicates()
            if duplicates['has_duplicates']:
                logger.warning(
                    f"Found {duplicates['duplicate_count']} duplicate models"
                )

            # Calculate statistics
            brands = set(item.brand for item in catalog_items)

            # Update run summary
            run_summary_repo.update_catalog_stats(
                run_id=run_id,
                catalog_count=count
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'catalog_count': count,
                'brands_count': len(brands),
                'duplicate_count': duplicates.get('duplicate_count', 0),
                'duration_seconds': duration,
            }

            logger.info(
                f"Catalog crawl completed: "
                f"{count} products from {len(brands)} brands "
                f"in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Catalog crawl failed after {duration:.2f}s: {e}",
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
                    error_message=f"crawl_product_catalog failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def fetch_product_detail(
    run_id: str,
    adapters: list,
    max_workers: int = 5,
    min_delay_ms: int = 300,
    max_delay_ms: int = 1200,
    **kwargs
) -> Dict[str, Any]:
    """
    Fetch product detail pages for all catalog items.

    This task fetches HTML content for all product detail pages in parallel
    while respecting rate limits. HTML snapshots are saved to the filesystem.

    Args:
        run_id: Unique run identifier
        adapters: List of brand adapter instances
        max_workers: Maximum concurrent requests (default: 5)
        min_delay_ms: Minimum delay between requests in ms (default: 300)
        max_delay_ms: Maximum delay between requests in ms (default: 1200)
        **kwargs: Additional task parameters

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - total_count: Total number of products
            - fetched_count: Number of successfully fetched pages
            - failed_count: Number of failed fetches
            - success_rate: Success rate percentage
            - duration_seconds: Task execution time

    Raises:
        Exception: If detail fetching fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting detail fetch for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            catalog_repo = CatalogRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Get catalog items
            catalog_items = catalog_repo.get_by_run_id(run_id)
            if not catalog_items:
                raise Exception(f"No catalog items found for run_id={run_id}")

            logger.info(f"Found {len(catalog_items)} catalog items")

            # Convert to CatalogItem objects
            from src.core.types import CatalogItem
            catalog_item_objects = [
                CatalogItem(
                    brand=item.brand,
                    series_l1=item.series_l1,
                    series_l2=item.series_l2,
                    model=item.product_model,
                    name=item.product_name,
                    url=item.product_url,
                    locale=item.locale
                )
                for item in catalog_items
            ]

            # Initialize page fetcher and detail collector
            page_fetcher = PageFetcher()
            detail_collector = DetailCollector(
                adapters=adapters,
                page_fetcher=page_fetcher,
                max_workers=max_workers,
                min_delay_ms=min_delay_ms,
                max_delay_ms=max_delay_ms
            )

            # Fetch all detail pages
            logger.info(
                f"Fetching {len(catalog_item_objects)} detail pages "
                f"with {max_workers} workers"
            )

            html_results = detail_collector.fetch_all(catalog_item_objects)

            # Save HTML snapshots to filesystem
            import os
            snapshot_dir = os.getenv('RAW_SNAPSHOT_DIR', '/data/raw_html')
            snapshot_dir = f"{snapshot_dir}/{run_id}"
            os.makedirs(snapshot_dir, exist_ok=True)

            saved_count = 0
            for url, html in html_results.items():
                # Create filename from URL
                filename = url.replace('/', '_').replace(':', '_')
                filepath = f"{snapshot_dir}/{filename}.html"

                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html)
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Failed to save snapshot for {url}: {e}")

            logger.info(f"Saved {saved_count} HTML snapshots to {snapshot_dir}")

            # Get statistics
            stats = detail_collector.get_statistics()
            failed_items = detail_collector.get_failed_items()

            if failed_items:
                logger.warning(
                    f"Failed to fetch {len(failed_items)} products. "
                    f"First 10: {failed_items[:10]}"
                )

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'total_count': stats['total_items'],
                'fetched_count': stats['successful'],
                'failed_count': stats['failed'],
                'success_rate': stats['success_rate'],
                'snapshot_dir': snapshot_dir,
                'duration_seconds': duration,
            }

            logger.info(
                f"Detail fetch completed: "
                f"{stats['successful']}/{stats['total_items']} successful "
                f"({stats['success_rate']:.1f}%) in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Detail fetch failed after {duration:.2f}s: {e}",
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
                    error_message=f"fetch_product_detail failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def retry_failed_fetches(
    run_id: str,
    adapters: list,
    max_workers: int = 5,
    max_retries: int = 2,
    **kwargs
) -> Dict[str, Any]:
    """
    Retry fetching failed product detail pages.

    This is a helper function for manual retry of failed detail fetches.

    Args:
        run_id: Unique run identifier
        adapters: List of brand adapter instances
        max_workers: Maximum concurrent requests
        max_retries: Maximum number of retry attempts per item
        **kwargs: Additional task parameters

    Returns:
        Dictionary with retry results
    """
    logger.info(f"Retrying failed detail fetches for run_id={run_id}")

    # Initialize database
    db = get_database()
    with db.session() as session:
        catalog_repo = CatalogRepository(session)

        # Get catalog items
        catalog_items = catalog_repo.get_by_run_id(run_id)

        # Convert to CatalogItem objects
        from src.core.types import CatalogItem
        catalog_item_objects = [
            CatalogItem(
                brand=item.brand,
                series_l1=item.series_l1,
                series_l2=item.series_l2,
                model=item.product_model,
                name=item.product_name,
                url=item.product_url,
                locale=item.locale
            )
            for item in catalog_items
        ]

        # Initialize detail collector
        page_fetcher = PageFetcher()
        detail_collector = DetailCollector(
            adapters=adapters,
            page_fetcher=page_fetcher,
            max_workers=max_workers
        )

        # Retry failed fetches
        retry_results = detail_collector.retry_failed(
            catalog_item_objects,
            max_retries=max_retries
        )

        # Save snapshots
        snapshot_dir = f"/data/raw_html/{run_id}/retry"
        import os
        os.makedirs(snapshot_dir, exist_ok=True)

        for url, html in retry_results.items():
            filename = url.replace('/', '_').replace(':', '_')
            filepath = f"{snapshot_dir}/{filename}.html"

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html)
            except Exception as e:
                logger.warning(f"Failed to save retry snapshot for {url}: {e}")

        logger.info(f"Retry completed: {len(retry_results)} items recovered")

        return {
            'status': 'success',
            'recovered_count': len(retry_results),
            'snapshot_dir': snapshot_dir,
        }
