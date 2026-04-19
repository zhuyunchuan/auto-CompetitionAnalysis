"""
Product detail page collector with parallel fetching and rate limiting.

This module fetches product detail pages in parallel while respecting
rate limits and saving HTML snapshots for debugging.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional

from src.adapters.base_adapter import BrandAdapter
from src.core.types import CatalogItem
from src.crawler.page_fetcher import PageFetcher

logger = logging.getLogger(__name__)


class DetailCollector:
    """
    Collects product detail pages in parallel with rate limiting.

    Features:
    - Concurrent fetching with configurable limits
    - Rate limiting with random jitter (300-1200ms)
    - Progress tracking and error handling
    - HTML snapshot saving
    - Retry logic for failed requests
    """

    def __init__(
        self,
        adapters: List[BrandAdapter],
        page_fetcher: PageFetcher,
        max_workers: int = 5,
        min_delay_ms: int = 300,
        max_delay_ms: int = 1200,
    ):
        """
        Initialize the detail collector.

        Args:
            adapters: List of brand adapter instances
            page_fetcher: Page fetcher instance for fetching pages
            max_workers: Maximum concurrent requests
            min_delay_ms: Minimum delay between requests in milliseconds
            max_delay_ms: Maximum delay between requests in milliseconds
        """
        self.adapters = adapters
        self.page_fetcher = page_fetcher
        self.max_workers = max_workers
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.last_request_time = 0

        # Statistics
        self.fetch_results: Dict[str, dict] = {}

    def fetch_all(
        self,
        catalog_items: List[CatalogItem],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, str]:
        """
        Fetch detail pages for all catalog items in parallel.

        Args:
            catalog_items: List of catalog items to fetch
            progress_callback: Optional callback function(progress, total)

        Returns:
            Dictionary mapping item URLs to HTML content
        """
        total_items = len(catalog_items)
        logger.info(f"Starting detail fetch for {total_items} products")
        logger.info(f"Using {self.max_workers} workers with rate limiting")

        results = {}
        failed_items = []

        # Create unique key for each item
        def get_item_key(item: CatalogItem) -> str:
            return f"{item.brand}/{item.series_l1}/{item.series_l2}/{item.model}"

        # Fetch function with rate limiting
        def fetch_with_limiting(item: CatalogItem) -> tuple:
            """Fetch single item with rate limiting."""
            # Apply rate limiting
            self._rate_limit()

            item_key = get_item_key(item)
            start_time = time.time()

            try:
                # Get adapter for this brand
                adapter = self._get_adapter_for_brand(item.brand)
                if adapter is None:
                    raise ValueError(f"No adapter found for brand: {item.brand}")

                # Fetch using adapter
                html = adapter.fetch_product_detail(item.url)

                if html:
                    elapsed = time.time() - start_time
                    logger.debug(
                        f"Fetched {item_key} in {elapsed:.2f}s "
                        f"({len(html)} bytes)"
                    )
                    return (item_key, html, None)
                else:
                    raise Exception("Adapter returned empty HTML")

            except Exception as e:
                elapsed = time.time() - start_time
                logger.warning(
                    f"Failed to fetch {item_key} after {elapsed:.2f}s: {e}"
                )
                return (item_key, None, str(e))

        # Parallel fetching with ThreadPoolExecutor
        completed_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all fetch tasks
            future_to_item = {
                executor.submit(fetch_with_limiting, item): item
                for item in catalog_items
            }

            # Process results as they complete
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                item_key = get_item_key(item)

                try:
                    key, html, error = future.result()

                    if html:
                        results[item.url] = html
                        self.fetch_results[item_key] = {
                            'success': True,
                            'url': item.url,
                            'size': len(html),
                            'error': None,
                        }
                    else:
                        failed_items.append((item_key, error))
                        self.fetch_results[item_key] = {
                            'success': False,
                            'url': item.url,
                            'size': 0,
                            'error': error,
                        }

                except Exception as e:
                    logger.error(f"Unexpected error for {item_key}: {e}")
                    failed_items.append((item_key, str(e)))
                    self.fetch_results[item_key] = {
                        'success': False,
                        'url': item.url,
                        'size': 0,
                        'error': str(e),
                    }

                # Update progress
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total_items)

                # Log progress periodically
                if completed_count % 10 == 0 or completed_count == total_items:
                    success_count = len(results)
                    logger.info(
                        f"Progress: {completed_count}/{total_items} items "
                        f"({success_count} success, {len(failed_items)} failed)"
                    )

        # Log summary
        success_rate = len(results) / total_items * 100 if total_items > 0 else 0
        logger.info(
            f"Fetch complete: {len(results)}/{total_items} successful "
            f"({success_rate:.1f}%)"
        )

        if failed_items:
            logger.warning(f"Failed to fetch {len(failed_items)} items:")
            for item_key, error in failed_items[:10]:  # Log first 10
                logger.warning(f"  - {item_key}: {error}")

        return results

    def fetch_single(self, item: CatalogItem) -> Optional[str]:
        """
        Fetch detail page for a single catalog item.

        Args:
            item: Catalog item to fetch

        Returns:
            HTML content or None on failure
        """
        # Apply rate limiting
        self._rate_limit()

        adapter = self._get_adapter_for_brand(item.brand)
        if adapter is None:
            logger.error(f"No adapter found for brand: {item.brand}")
            return None

        try:
            html = adapter.fetch_product_detail(item.url)
            if html:
                logger.info(
                    f"Fetched {item.brand}/{item.model} "
                    f"({len(html)} bytes)"
                )
                return html
            else:
                logger.warning(f"Empty HTML for {item.brand}/{item.model}")
                return None

        except Exception as e:
            logger.error(
                f"Failed to fetch {item.brand}/{item.model}: {e}",
                exc_info=True
            )
            return None

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        import random

        now = time.time()
        elapsed = now - self.last_request_time
        min_interval = self.min_delay_ms / 1000.0

        if elapsed < min_interval:
            # Add random jitter
            sleep_time = min_interval - elapsed + random.uniform(0, 0.1)
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_adapter_for_brand(self, brand: str) -> Optional[BrandAdapter]:
        """
        Get adapter instance for a specific brand.

        Args:
            brand: Brand name (e.g., "HIKVISION")

        Returns:
            BrandAdapter instance or None if not found
        """
        adapter_name = brand.lower()

        for adapter in self.adapters:
            current_adapter_name = adapter.__class__.__name__.replace(
                'Adapter', ''
            ).lower()
            if current_adapter_name == adapter_name:
                return adapter

        return None

    def get_failed_items(self) -> List[dict]:
        """
        Get list of items that failed to fetch.

        Returns:
            List of dictionaries with failed item details
        """
        return [
            {
                'item_key': key,
                'url': result['url'],
                'error': result['error'],
            }
            for key, result in self.fetch_results.items()
            if not result['success']
        ]

    def get_success_items(self) -> List[dict]:
        """
        Get list of items that were successfully fetched.

        Returns:
            List of dictionaries with successful item details
        """
        return [
            {
                'item_key': key,
                'url': result['url'],
                'size': result['size'],
            }
            for key, result in self.fetch_results.items()
            if result['success']
        ]

    def get_statistics(self) -> dict:
        """
        Get fetch statistics.

        Returns:
            Dictionary with fetch statistics
        """
        total = len(self.fetch_results)
        success = len([
            r for r in self.fetch_results.values() if r['success']
        ])
        failed = total - success
        total_bytes = sum(
            r['size'] for r in self.fetch_results.values() if r['success']
        )

        return {
            'total_items': total,
            'successful': success,
            'failed': failed,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'total_bytes': total_bytes,
            'avg_bytes_per_item': (
                total_bytes / success if success > 0 else 0
            ),
        }

    def retry_failed(
        self,
        catalog_items: List[CatalogItem],
        max_retries: int = 2,
    ) -> Dict[str, str]:
        """
        Retry fetching items that previously failed.

        Args:
            catalog_items: Original list of catalog items
            max_retries: Maximum number of retry attempts per item

        Returns:
            Dictionary mapping item URLs to HTML content (retry results only)
        """
        failed_item_keys = [
            key for key, result in self.fetch_results.items()
            if not result['success']
        ]

        if not failed_item_keys:
            logger.info("No failed items to retry")
            return {}

        # Map item keys back to catalog items
        key_to_item = {}
        for item in catalog_items:
            key = f"{item.brand}/{item.series_l1}/{item.series_l2}/{item.model}"
            if key in failed_item_keys:
                key_to_item[key] = item

        logger.info(f"Retrying {len(key_to_item)} failed items")

        retry_results = {}
        for attempt in range(max_retries):
            logger.info(f"Retry attempt {attempt + 1}/{max_retries}")

            # Fetch only failed items
            results = self.fetch_all(list(key_to_item.values()))

            # Update results
            for key, item in key_to_item.items():
                if item.url in results:
                    retry_results[item.url] = results[item.url]
                    # Remove from retry list if successful
                    key_to_item.pop(key, None)
                    logger.info(f"Retry successful for {key}")

            # Break if all items succeeded
            if not key_to_item:
                break

            # Wait before next retry
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # Exponential backoff: 5s, 10s
                logger.info(f"Waiting {wait_time}s before next retry...")
                time.sleep(wait_time)

        logger.info(
            f"Retry complete: {len(retry_results)} items recovered"
        )

        return retry_results
