"""
Constants for the competitor product scraping system.

This module defines all constant values used across the system including
field codes, severity levels, issue types, brands, and schedule types.
"""

from enum import Enum
from typing import List


# Field codes from field_dictionary_v1.md
# These are the 19 fields defined in Phase 1
FIELD_CODES = {
    "image_sensor": "Image Sensor",
    "max_resolution": "Max. Resolution",
    "lens_type": "Lens Type",
    "aperture": "Aperture",
    "supplement_light_type": "Supplement Light Type",
    "supplement_light_range": "Supplement Light Range",
    "main_stream_max_fps_resolution": "Main Stream Max FPS@Resolution",
    "stream_count": "Stream Count",
    "interface_items": "Interface",
    "deep_learning_function_categories": "Deep Learning Function Categories",
    "approval_protection": "Approval.Protection",
    "approval_anti_corrosion_protection": "Approval.Anti-Corrosion Protection",
}

# Field aliases for multi-language support
FIELD_ALIASES = {
    "image_sensor": ["Image Sensor", "图像传感器"],
    "max_resolution": ["Max. Resolution", "最大分辨率"],
    "lens_type": ["Lens Type", "镜头类型"],
    "aperture": ["Aperture", "光圈"],
    "supplement_light_type": ["Supplement Light Type", "补光灯类型"],
    "supplement_light_range": ["Supplement Light Range", "补光距离"],
    "main_stream_max_fps_resolution": ["Main Stream", "主码流", "Main Stream Max FPS@Resolution"],
    "stream_count": ["Stream Count", "码流数量", "Third Stream"],
    "interface_items": ["Interface", "接口"],
    "deep_learning_function_categories": ["Deep Learning Function", "深度学习功能"],
    "approval_protection": ["Protection", "防护"],
    "approval_anti_corrosion_protection": ["Anti-Corrosion Protection", "防腐等级"],
}

# Canonical units for each field
FIELD_UNITS = {
    "image_sensor": None,  # text field, no unit
    "max_resolution": "px",
    "lens_type": None,  # text field, no unit
    "aperture": "f",
    "supplement_light_type": None,  # text field, no unit
    "supplement_light_range": "m",
    "main_stream_max_fps_resolution": "fps+px",
    "stream_count": "count",
    "interface_items": None,  # list field, no unit
    "deep_learning_function_categories": None,  # list field, no unit
    "approval_protection": "grade",
    "approval_anti_corrosion_protection": "grade",
}

# Required fields (required=yes in field dictionary)
REQUIRED_FIELDS = {
    "image_sensor",
    "max_resolution",
    "lens_type",
    "aperture",
    "supplement_light_type",
    "supplement_light_range",
    "main_stream_max_fps_resolution",
    "stream_count",
    "interface_items",
    "deep_learning_function_categories",
    "approval_protection",
    "approval_anti_corrosion_protection",
}


class Severity(str, Enum):
    """
    Severity levels for quality issues.

    P1: Critical - Blocks downstream processing or makes data unusable
    P2: High - Significant data quality issue requiring immediate attention
    P3: Medium - Minor issue that should be reviewed but doesn't block processing
    """
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IssueType(str, Enum):
    """
    Types of quality issues that can be detected.

    missing_field: A required field is empty or not extracted
    parse_failed: Field was found but parsing failed (regex/structural failure)
    unit_abnormal: Unit is unrecognized or conversion failed
    duplicate_model: Same model appears multiple times with conflicting data
    subseries_empty: Series level 2 (subseries) is empty or missing
    hierarchy_changed: Product hierarchy structure has changed from previous runs
    """
    MISSING_FIELD = "missing_field"
    PARSE_FAILED = "parse_failed"
    UNIT_ABNORMAL = "unit_abnormal"
    DUPLICATE_MODEL = "duplicate_model"
    SUBSERIES_EMPTY = "subseries_empty"
    HIERARCHY_CHANGED = "hierarchy_changed"


class Brand(str, Enum):
    """
    Supported competitor brands.

    HIKVISION: Hikvision products
    DAHUA: Dahua Technology products
    """
    HIKVISION = "HIKVISION"
    DAHUA = "DAHUA"


class ScheduleType(str, Enum):
    """
    Schedule types for automated scraping runs.

    BIWEEKLY: Run every two weeks
    MONTHLY: Run once per month
    """
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"


class HierarchyStatus(str, Enum):
    """
    Status of hierarchy nodes.

    active: Currently active and in production
    discontinued: No longer manufactured/sold
    pending: Newly discovered, awaiting validation
    """
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    PENDING = "pending"


class ComparisonRule(str, Enum):
    """
    Comparison rules for field values.

    exact_or_alias: Exact match or known alias
    normalized_resolution: Resolution normalized to WIDTHxHEIGHT format
    normalized_aperture: Aperture normalized to f/number format
    normalized_distance: Distance normalized to meters
    normalized_fps_resolution: FPS and resolution normalized to fps (widthxheight)
    numeric_compare: Numeric comparison
    set_compare: Set comparison for lists (order-independent)
    """
    EXACT_OR_ALIAS = "exact_or_alias"
    NORMALIZED_RESOLUTION = "normalized_resolution"
    NORMALIZED_APERTURE = "normalized_aperture"
    NORMALIZED_DISTANCE = "normalized_distance"
    NORMALIZED_FPS_RESOLUTION = "normalized_fps_resolution"
    NUMERIC_COMPARE = "numeric_compare"
    SET_COMPARE = "set_compare"


# Default crawling configuration
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 2  # seconds
DEFAULT_CONCURRENT_REQUESTS = 5

# Storage paths
DEFAULT_HIERARCHY_PATH = "data/hierarchy.json"
DEFAULT_CATALOG_PATH = "data/catalog.json"
DEFAULT_SPECS_PATH = "data/specs.json"
DEFAULT_ISSUES_PATH = "data/issues.json"
