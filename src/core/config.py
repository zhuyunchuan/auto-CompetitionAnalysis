"""Configuration settings for the competition analysis system."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import os


@dataclass
class CrawlerConfig:
    """HTTP crawler configuration."""

    # HTTP settings
    timeout: float = 30.0
    max_redirects: int = 5
    verify_ssl: bool = True

    # Retry settings
    max_retries: int = 3
    retry_delays: List[float] = field(default_factory=lambda: [2.0, 5.0, 10.0])

    # Rate limiting
    min_delay: float = 0.3  # 300ms
    max_delay: float = 1.2  # 1200ms
    concurrent_requests: int = 5

    # User agent rotation
    user_agents: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    ])

    # Cache settings
    cache_enabled: bool = True
    cache_ttl: int = 86400  # 24 hours in seconds
    cache_dir: str = 'data/cache'

    # HTML snapshot settings
    save_snapshots: bool = True
    snapshot_dir: str = 'data/snapshots'

    # Playwright settings (for dynamic pages)
    use_playwright_fallback: bool = True
    playwright_timeout: int = 30000  # 30 seconds
    playwright_headless: bool = True

    # Robots.txt
    respect_robots_txt: bool = True

    # Logging
    log_level: str = 'INFO'
    log_file: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'CrawlerConfig':
        """Create configuration from environment variables."""
        config = cls()

        timeout = os.getenv('CRAWLER_TIMEOUT')
        if timeout:
            config.timeout = float(timeout)

        max_retries = os.getenv('CRAWLER_MAX_RETRIES')
        if max_retries:
            config.max_retries = int(max_retries)

        concurrent = os.getenv('CRAWLER_CONCURRENT_REQUESTS')
        if concurrent:
            config.concurrent_requests = int(concurrent)

        cache_dir = os.getenv('CRAWLER_CACHE_DIR')
        if cache_dir:
            config.cache_dir = cache_dir

        snapshot_dir = os.getenv('CRAWLER_SNAPSHOT_DIR')
        if snapshot_dir:
            config.snapshot_dir = snapshot_dir

        return config


@dataclass
class SiteConfig:
    """Site-specific configuration for different e-commerce platforms."""

    base_url: str
    name: str
    hierarchy_selectors: Dict[str, str] = field(default_factory=dict)
    catalog_selectors: Dict[str, str] = field(default_factory=dict)
    detail_selectors: Dict[str, str] = field(default_factory=dict)
    requires_js: bool = False
    rate_limit_delay: Optional[float] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)

    # Strategy preferences
    parsing_strategy: str = 'css'  # 'css', 'xpath', or 'regex'


# Default site configurations
DEFAULT_SITE_CONFIGS: Dict[str, SiteConfig] = {}

# Global configuration instance
_config: Optional[CrawlerConfig] = None


def get_config() -> CrawlerConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = CrawlerConfig.from_env()
    return _config


def set_config(config: CrawlerConfig) -> None:
    """Set global configuration instance."""
    global _config
    _config = config
