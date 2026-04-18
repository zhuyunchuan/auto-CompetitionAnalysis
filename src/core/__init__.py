"""Core types and configuration."""

from .types import CatalogItem, SeriesInfo, ProductDetail
from .config import CrawlerConfig, SiteConfig, get_config, set_config

__all__ = [
    'CatalogItem',
    'SeriesInfo',
    'ProductDetail',
    'CrawlerConfig',
    'SiteConfig',
    'get_config',
    'set_config',
]
