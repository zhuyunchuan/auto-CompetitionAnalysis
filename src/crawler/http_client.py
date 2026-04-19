"""
HTTP client with retry, rate limiting, and error handling.

This module provides a robust HTTP client for web scraping with:
- Exponential backoff retry
- Rate limiting with jitter
- User agent rotation
- Comprehensive error handling
"""

import logging
import random
import time
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


# User agent list for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class HttpClient:
    """
    HTTP client with retry logic and rate limiting.
    """

    def __init__(
        self,
        timeout_sec: int = 30,
        retry_times: int = 3,
        min_delay_ms: int = 300,
        max_delay_ms: int = 1200,
    ):
        """
        Initialize HTTP client.

        Args:
            timeout_sec: Request timeout in seconds
            retry_times: Number of retry attempts
            min_delay_ms: Minimum delay between requests in milliseconds
            max_delay_ms: Maximum delay between requests in milliseconds
        """
        self.timeout_sec = timeout_sec
        self.retry_times = retry_times
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self._last_request_time = 0

    def _get_random_delay(self) -> float:
        """Get random delay in seconds with jitter."""
        return random.uniform(self.min_delay_ms, self.max_delay_ms) / 1000.0

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = self.min_delay_ms / 1000.0

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed + random.uniform(0, 0.1)
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _get_headers(self, url: str = "") -> dict:
        """Get request headers with random user agent and additional headers."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if url else "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Add Referer if URL is provided (not first request)
        if url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

        return headers

    def get(self, url: str, allow_redirects: bool = True) -> Optional[str]:
        """
        Perform HTTP GET request with retry logic.

        Args:
            url: Target URL
            allow_redirects: Whether to follow redirects

        Returns:
            Response text on success, None on failure
        """
        self._rate_limit()

        for attempt in range(self.retry_times):
            try:
                # Use headers with Referer for subsequent requests
                headers = self._get_headers(url)

                with httpx.Client(
                    timeout=self.timeout_sec,
                    follow_redirects=allow_redirects,
                    headers=headers,
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    return response.text

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt == self.retry_times - 1:
                    logger.error(f"Failed to fetch {url} after {self.retry_times} attempts")
                    return None

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt == self.retry_times - 1:
                    logger.error(f"Timeout fetching {url} after {self.retry_times} attempts")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt == self.retry_times - 1:
                    return None

            # Exponential backoff before retry
            backoff_time = (2**attempt) + random.uniform(0, 1)
            logger.debug(f"Retrying in {backoff_time:.2f} seconds...")
            time.sleep(backoff_time)

        return None
