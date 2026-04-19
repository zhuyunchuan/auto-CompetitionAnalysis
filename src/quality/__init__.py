"""
Quality detection module for competitor scraping system.

This module provides data quality issue detection capabilities including:
- Issue rule definitions with severity levels
- Batch detection for spec records, catalog, and hierarchy changes
- Statistics tracking and filtering support

Main Classes:
- IssueDetector: Main detection engine for quality issues
- DetectionStatistics: Statistics tracker for detection results

Usage:
    from src.quality import IssueDetector

    detector = IssueDetector(run_id="20260418_biweekly_01")
    issues = detector.detect_spec_issues(spec_records)
    issues.extend(detector.detect_duplicate_models(spec_records))
    issues.extend(detector.detect_catalog_issues(catalog_records))

    stats = detector.get_statistics()
"""

from src.quality.issue_rules import (
    QualityRule,
    RuleRegistry,
    rule_registry,
    MISSING_FIELD_RULES,
    PARSE_FAILED_RULES,
    UNIT_ABNORMAL_RULES,
)

from src.quality.issue_detector import (
    IssueDetector,
    DetectionStatistics,
)

__all__ = [
    # Rules
    'QualityRule',
    'RuleRegistry',
    'rule_registry',
    'MISSING_FIELD_RULES',
    'PARSE_FAILED_RULES',
    'UNIT_ABNORMAL_RULES',

    # Detector
    'IssueDetector',
    'DetectionStatistics',
]
