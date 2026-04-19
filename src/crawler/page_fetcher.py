"""
Page fetching module with caching and playwright fallback.

This module provides a robust page fetching system that:
- Uses httpx for static pages with disk-based caching
- Falls back to playwright for JavaScript-rendered pages
- Implements proper error handling and retry logic
- Saves HTML snapshots for debugging
"""

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

from src.core.config import CrawlerConfig
from src.crawler.http_client import HttpClient

logger = logging.getLogger(__name__)


class PageFetcher:
    """
    Fetches web pages with caching and dynamic content support.

    Features:
    - Disk-based caching with TTL (24 hours default)
    - Playwright fallback for JavaScript-rendered pages
    - HTML snapshot saving for debugging
    - Configurable timeout and retry logic
    """

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        http_client: Optional[HttpClient] = None,
    ):
        """
        Initialize the page fetcher.

        Args:
            config: Crawler configuration (uses defaults if None)
            http_client: HTTP client instance (creates new if None)
        """
        self.config = config or CrawlerConfig()
        self.http_client = http_client or HttpClient(
            timeout_sec=int(self.config.timeout),
            retry_times=self.config.max_retries,
            min_delay_ms=int(self.config.min_delay * 1000),
            max_delay_ms=int(self.config.max_delay * 1000),
        )

        # Ensure cache and snapshot directories exist
        self.cache_dir = Path(self.config.cache_dir)
        self.snapshot_dir = Path(self.config.snapshot_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str) -> str:
        """
        Generate cache key from URL.

        Args:
            url: The URL to cache

        Returns:
            SHA256 hash of the URL
        """
        return hashlib.sha256(url.encode()).hexdigest()

    def _get_cache_path(self, url: str) -> Path:
        """
        Get cache file path for a URL.

        Args:
            url: The URL to cache

        Returns:
            Path to cache file
        """
        cache_key = self._get_cache_key(url)
        return self.cache_dir / f"{cache_key}.html"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cached file is still valid based on TTL.

        Args:
            cache_path: Path to cached file

        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False

        file_mtime = cache_path.stat().st_mtime
        file_age = time.time() - file_mtime
        return file_age < self.config.cache_ttl

    def _load_from_cache(self, url: str) -> Optional[str]:
        """
        Load page content from cache if valid.

        Args:
            url: The URL to load from cache

        Returns:
            Cached HTML content or None if not found/invalid
        """
        if not self.config.cache_enabled:
            return None

        cache_path = self._get_cache_path(url)

        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.debug(f"Cache hit for {url}")
                return content
            except Exception as e:
                logger.warning(f"Failed to read cache for {url}: {e}")
                return None

        return None

    def _save_to_cache(self, url: str, content: str):
        """
        Save page content to cache.

        Args:
            url: The URL to cache
            content: HTML content to cache
        """
        if not self.config.cache_enabled:
            return

        cache_path = self._get_cache_key(url)
        cache_file = self.cache_dir / f"{cache_path}.html"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"Cached content for {url}")
        except Exception as e:
            logger.warning(f"Failed to cache content for {url}: {e}")

    def _save_snapshot(self, url: str, content: str, suffix: str = ""):
        """
        Save HTML snapshot for debugging.

        Args:
            url: The URL being fetched
            content: HTML content to save
            suffix: Optional suffix for filename (e.g., '_playwright')
        """
        if not self.config.save_snapshots:
            return

        # Create safe filename from URL
        safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_')
        safe_url = safe_url[:200]  # Limit length
        timestamp = time.strftime('%Y%m%d_%H%M%S')

        try:
            snapshot_file = self.snapshot_dir / f"{timestamp}_{safe_url}{suffix}.html"
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"Saved snapshot to {snapshot_file}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot for {url}: {e}")

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """
        Fetch page using playwright for JavaScript-rendered content.

        Args:
            url: The URL to fetch

        Returns:
            HTML content or None on failure
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright")
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.config.playwright_headless
                )
                page = browser.new_page()

                # Set user agent
                page.set_extra_http_headers({
                    "User-Agent": self.http_client._get_headers()["User-Agent"]
                })

                page.goto(
                    url,
                    timeout=self.config.playwright_timeout,
                    wait_until="networkidle"
                )

                content = page.content()
                browser.close()

                logger.info(f"Fetched {url} with playwright")
                return content

        except Exception as e:
            logger.warning(f"Playwright fetch failed for {url}: {e}")
            return None

    def fetch(
        self,
        url: str,
        force_refresh: bool = False,
        use_playwright: bool = False,
    ) -> Optional[str]:
        """
        Fetch a web page with caching and fallback support.

        Args:
            url: The URL to fetch
            force_refresh: Skip cache and fetch fresh content
            use_playwright: Force use of playwright (skip httpx)

        Returns:
            HTML content or None on failure
        """
        # Try cache first
        if not force_refresh and not use_playwright:
            cached = self._load_from_cache(url)
            if cached:
                return cached

        # Fetch with httpx
        if not use_playwright:
            content = self.http_client.get(url)
            if content:
                self._save_to_cache(url, content)
                self._save_snapshot(url, content)

                # Check if page needs JavaScript rendering
                # Simple heuristic: if page is very small or has no body
                if len(content) < 1000 or '<body' not in content.lower():
                    logger.info(f"Page {url} appears to need JavaScript rendering")

                    if self.config.use_playwright_fallback:
                        logger.info(f"Attempting playwright fallback for {url}")
                        js_content = self._fetch_with_playwright(url)
                        if js_content:
                            self._save_to_cache(url, js_content)
                            self._save_snapshot(url, js_content, suffix='_playwright')
                            return js_content

                return content

        # Fallback to playwright if httpx failed or forced
        if self.config.use_playwright_fallback or use_playwright:
            logger.info(f"Using playwright for {url}")
            content = self._fetch_with_playwright(url)
            if content:
                self._save_to_cache(url, content)
                self._save_snapshot(url, content, suffix='_playwright')
                return content

        logger.error(f"Failed to fetch {url} with all methods")
        return None

    def clear_cache(self, older_than_hours: Optional[int] = None):
        """
        Clear cached files.

        Args:
            older_than_hours: Only clear files older than this many hours.
                            If None, clear all cache.
        """
        try:
            for cache_file in self.cache_dir.glob('*.html'):
                if older_than_hours is None:
                    cache_file.unlink()
                    logger.debug(f"Cleared cache file: {cache_file}")
                else:
                    file_age = time.time() - cache_file.stat().st_mtime
                    age_hours = file_age / 3600
                    if age_hours > older_than_hours:
                        cache_file.unlink()
                        logger.debug(f"Cached old cache file: {cache_file}")

            logger.info(f"Cache cleared (older_than_hours={older_than_hours})")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
