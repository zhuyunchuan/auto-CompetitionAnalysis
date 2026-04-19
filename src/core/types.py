"""
Core data types for the competition analysis system.

This module defines the fundamental data structures used across the system,
following the frozen contract from field_dictionary_v1.md.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class HierarchyNode:
    """Represents a discovered hierarchy node (series or subseries)."""
    brand: str
    series_l1: str
    series_l2: Optional[str] = None
    source: str = ""
    status: str = "active"  # active, disappeared
    discovered_at: datetime = field(default_factory=datetime.now)

@dataclass(frozen=True)
class CatalogItem:
    """Represents a product catalog entry."""
    brand: str
    series_l1: str
    series_l2: str
    model: str
    name: str
    url: str
    locale: str = "en"

@dataclass(frozen=True)
class SpecRecord:
    """Represents a single specification record (long format)."""
    run_id: str
    brand: str
    series_l1: str
    series_l2: str
    model: str
    field_code: str
    raw_value: str
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    source_url: str = ""
    confidence: float = 1.0
    is_manual_override: bool = False

@dataclass(frozen=True)
class QualityIssue:
    """Represents a data quality issue."""
    run_id: str
    brand: str
    series_l1: str
    series_l2: str
    model: str
    issue_type: str  # parse_failed, missing_field, unit_abnormal, hierarchy_changed
    field_code: Optional[str] = None
    detail: str = ""
    severity: str = "P3"  # P1, P2, P3
