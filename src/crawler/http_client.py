"""HTTP client with resilience features for web crawling.

Features:
- Async HTTP requests using httpx
- Retry logic with exponential backoff
- Rate limiting with random jitter
- User-Agent rotation
- Session management and connection pooling
- Timeout configuration
"""

import asyncio
import random
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import httpx
from httpx import AsyncClient, Response, HTTPError

from ..core.config import get_config

logger = logging.getLogger(__name__)


class HTTPClient:
    """Resilient HTTP client for web crawling with retry, rate limiting, and rotation."""

    def __init__(self, config=None):
        """Initialize HTTP client.

        Args:
            config: CrawlerConfig instance. If None, uses global config.
        """
        self.config = config or get_config()
        self._client: Optional[AsyncClient] = None
        self._last_request_time = 0.0
        self._request_count = 0
        self._current_user_agent_index = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Initialize the HTTP client session."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )

            self._client = AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=limits,
                follow_redirects=True,
                max_redirects=self.config.max_redirects,
                verify=self.config.verify_ssl,
            )
            logger.info("HTTP client session started")

    async def close(self):
        """Close the HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("HTTP client session closed")

    def _get_user_agent(self) -> str:
        """Get next user agent in rotation."""
        if not self.config.user_agents:
            return 'Mozilla/5.0 (compatible; auto-CompetitionAnalysis/1.0)'

        ua = self.config.user_agents[self._current_user_agent_index]
        self._current_user_agent_index = (
            (self._current_user_agent_index + 1) % len(self.config.user_agents)
        )
        return ua

    async def _rate_limit(self):
        """Apply rate limiting with random jitter."""
        async with self._lock:
            # Calculate delay
            delay = random.uniform(self.config.min_delay, self.config.max_delay)

            # Wait if needed
            current_time = asyncio.get_event_loop().time()
            time_since_last_request = current_time - self._last_request_time

            if time_since_last_request < delay:
                wait_time = delay - time_since_last_request
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()
            self._request_count += 1

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Response:
        """Make a single HTTP request with rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx

        Returns:
            httpx.Response object

        Raises:
            HTTPError: If request fails after retries
        """
        await self._rate_limit()

        # Set headers
        headers = kwargs.pop('headers', {})
        headers['User-Agent'] = self._get_user_agent()

        # Add default headers
        headers.setdefault('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        headers.setdefault('Accept-Language', 'en-US,en;q=0.9')
        headers.setdefault('Accept-Encoding', 'gzip, deflate')
        headers.setdefault('DNT', '1')

        logger.debug(f"{method} {url}")

        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except HTTPError as e:
            logger.warning(f"HTTP error on {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error on {url}: {e}")
            raise

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make GET request with retry logic.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            httpx.Response object

        Raises:
            HTTPError: If request fails after all retries
        """
        last_exception = None

        for attempt, delay in enumerate(self.config.retry_delays[:self.config.max_retries]):
            try:
                response = await self._make_request(
                    'GET',
                    url,
                    params=params,
                    headers=headers,
                    **kwargs
                )
                if attempt > 0:
                    logger.info(f"Request succeeded on attempt {attempt + 1}: {url}")
                return response

            except HTTPError as e:
                last_exception = e
                if attempt < len(self.config.retry_delays[:self.config.max_retries]) - 1:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.config.max_retries}), "
                        f"retrying in {delay}s: {url}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {attempt + 1} attempts: {url}")

        raise last_exception

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make POST request with retry logic.

        Args:
            url: Request URL
            data: Form data
            json: JSON data
            headers: Additional headers
            **kwargs: Additional arguments

        Returns:
            httpx.Response object

        Raises:
            HTTPError: If request fails after all retries
        """
        last_exception = None

        for attempt, delay in enumerate(self.config.retry_delays[:self.config.max_retries]):
            try:
                response = await self._make_request(
                    'POST',
                    url,
                    data=data,
                    json=json,
                    headers=headers,
                    **kwargs
                )
                if attempt > 0:
                    logger.info(f"Request succeeded on attempt {attempt + 1}: {url}")
                return response

            except HTTPError as e:
                last_exception = e
                if attempt < len(self.config.retry_delays[:self.config.max_retries]) - 1:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.config.max_retries}), "
                        f"retrying in {delay}s: {url}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {attempt + 1} attempts: {url}")

        raise last_exception

    async def fetch_html(self, url: str, **kwargs) -> str:
        """Fetch HTML content from URL.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for get()

        Returns:
            HTML content as string

        Raises:
            HTTPError: If request fails
        """
        response = await self.get(url, **kwargs)
        return response.text

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            'request_count': self._request_count,
            'user_agent_index': self._current_user_agent_index,
            'is_active': self._client is not None and not self._client.is_closed,
        }


async def fetch_multiple(
    urls: List[str],
    client: HTTPClient,
    concurrency: int = 5,
    **kwargs
) -> Dict[str, str]:
    """Fetch multiple URLs concurrently.

    Args:
        urls: List of URLs to fetch
        client: HTTPClient instance
        concurrency: Maximum concurrent requests
        **kwargs: Additional arguments for fetch_html()

    Returns:
        Dictionary mapping URL to HTML content
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(url: str) -> tuple[str, str]:
        async with semaphore:
            try:
                html = await client.fetch_html(url, **kwargs)
                return (url, html)
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return (url, "")

    tasks = [fetch_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)

    return {url: html for url, html in results}
