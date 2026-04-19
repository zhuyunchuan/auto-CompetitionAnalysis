"""Core types and configuration."""

from .types import HierarchyNode, CatalogItem, SpecRecord, QualityIssue
from .config import CrawlerConfig, SiteConfig, get_config, set_config

__all__ = [
    # Types
    'HierarchyNode',
    'CatalogItem',
    'SpecRecord',
    'QualityIssue',
    # Config
    'CrawlerConfig',
    'SiteConfig',
    'get_config',
    'set_config',
]
