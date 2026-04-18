"""
Core data types for the competitor product scraping system.

This module defines frozen data structures using dataclasses for type safety
and immutability across the system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """
    Represents a node in the product hierarchy tree.

    A hierarchy node can represent a brand, series level 1, or series level 2
    in the product catalog structure.

    Attributes:
        brand: Brand name (e.g., 'HIKVISION', 'DAHUA')
        series_l1: Series level 1 name (e.g., 'AcuSense', 'Eureka')
        series_l2: Series level 2 name (e.g., 'Bullet', 'Dome')
        source: Source where this hierarchy was discovered (e.g., 'sitemap', 'catalog')
        status: Current status of the node (e.g., 'active', 'discontinued', 'pending')
        discovered_at: Timestamp when this node was discovered
    """
    brand: str
    series_l1: Optional[str]
    series_l2: Optional[str]
    source: str
    status: str
    discovered_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """
    Represents a single product in the catalog.

    A catalog item represents a product model that needs to be scraped
    for detailed specifications.

    Attributes:
        brand: Brand name (e.g., 'HIKVISION', 'DAHUA')
        series_l1: Series level 1 name
        series_l2: Series level 2 name
        model: Product model number (e.g., 'DS-2CD3T47DWD-L')
        name: Product name/description
        url: Product page URL
        locale: Locale of the product page (e.g., 'en-US', 'zh-CN')
    """
    brand: str
    series_l1: Optional[str]
    series_l2: Optional[str]
    model: str
    name: str
    url: str
    locale: str


@dataclass(frozen=True, slots=True)
class SpecRecord:
    """
    Represents a single specification field for a product.

    A spec record stores both the raw and normalized values for a specific
    field of a product model.

    Attributes:
        run_id: Unique identifier for the scraping run
        brand: Brand name
        series_l1: Series level 1 name
        series_l2: Series level 2 name
        model: Product model number
        field_code: Field code from field dictionary (e.g., 'image_sensor', 'max_resolution')
        raw_value: Original value extracted from the page
        normalized_value: Normalized value after processing
        unit: Unit of the normalized value (e.g., 'px', 'm', 'f')
        source_url: URL where this spec was extracted from
        confidence: Confidence score of extraction (0.0 to 1.0)
    """
    run_id: str
    brand: str
    series_l1: Optional[str]
    series_l2: Optional[str]
    model: str
    field_code: str
    raw_value: Optional[str]
    normalized_value: Optional[str]
    unit: Optional[str]
    source_url: str
    confidence: float


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """
    Represents a quality issue detected during data processing.

    Quality issues are generated during scraping, parsing, or validation
    to flag data that requires human review or correction.

    Attributes:
        run_id: Unique identifier for the scraping run
        brand: Brand name
        series_l1: Series level 1 name
        series_l2: Series level 2 name
        model: Product model number
        issue_type: Type of issue (e.g., 'missing_field', 'parse_failed', 'unit_abnormal')
        field_code: Field code where the issue was detected (if applicable)
        detail: Detailed description of the issue
        severity: Severity level (P1, P2, P3)
    """
    run_id: str
    brand: str
    series_l1: Optional[str]
    series_l2: Optional[str]
    model: str
    issue_type: str
    field_code: Optional[str]
    detail: str
    severity: str
