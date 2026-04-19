"""
Data quality issue detector module.

This module provides the main IssueDetector class that scans specification data,
catalog data, and hierarchy information to identify data quality issues according
to defined rules. Supports batch processing, filtering, and statistics tracking.

Key Features:
- Batch processing of spec records for efficiency
- Cross-record analysis (duplicates, hierarchy changes)
- Filter by severity, brand, series
- Statistics tracking (counts by type/severity)
- Export issues to QualityIssue objects for database storage
"""

import logging
from typing import List, Dict, Set, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict

from src.core.types import QualityIssue, SpecRecord
from src.core.constants import IssueType, Severity, REQUIRED_FIELDS
from src.quality.issue_rules import (
    rule_registry,
    QualityRule,
    _check_missing_field,
    _check_parse_failed,
    _check_unit_abnormal,
    _check_duplicate_model,
    _check_subseries_empty,
    _check_hierarchy_changed
)

logger = logging.getLogger(__name__)


class DetectionStatistics:
    """
    Statistics tracker for quality issue detection.

    Tracks counts by issue type, severity, and overall totals.
    """

    def __init__(self):
        self._by_type: Dict[str, int] = defaultdict(int)
        self._by_severity: Dict[str, int] = defaultdict(int)
        self._by_brand: Dict[str, int] = defaultdict(int)
        self._total_issues = 0

    def increment(self, issue_type: str, severity: str, brand: str) -> None:
        """Increment counters for a detected issue."""
        self._by_type[issue_type] += 1
        self._by_severity[severity] += 1
        self._by_brand[brand] += 1
        self._total_issues += 1

    def get_by_type(self) -> Dict[str, int]:
        """Get issue counts by type."""
        return dict(self._by_type)

    def get_by_severity(self) -> Dict[str, int]:
        """Get issue counts by severity."""
        return dict(self._by_severity)

    def get_by_brand(self) -> Dict[str, int]:
        """Get issue counts by brand."""
        return dict(self._by_brand)

    def total(self) -> int:
        """Get total issue count."""
        return self._total_issues

    def reset(self) -> None:
        """Reset all counters."""
        self._by_type.clear()
        self._by_severity.clear()
        self._by_brand.clear()
        self._total_issues = 0


class IssueDetector:
    """
    Main quality issue detection engine.

    Scans specification data, catalog data, and hierarchy information
    to identify data quality issues according to defined rules.

    Usage:
        detector = IssueDetector(run_id="20260418_biweekly_01")
        issues = detector.detect_spec_issues(spec_records)
        issues.extend(detector.detect_catalog_issues(catalog_records))
        issues.extend(detector.detect_hierarchy_changes(current_hierarchy, previous_hierarchy))

        stats = detector.get_statistics()
    """

    def __init__(self, run_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the issue detector.

        Args:
            run_id: Current run identifier for issue tracking
            config: Optional configuration dict with detection parameters
        """
        self.run_id = run_id
        self.config = config or {}
        self.statistics = DetectionStatistics()
        self._detected_issues: List[QualityIssue] = []

        # Configuration defaults
        self._enable_duplicate_detection = self.config.get('enable_duplicate_detection', True)
        self._enable_hierarchy_change_detection = self.config.get('enable_hierarchy_change_detection', True)
        self._severity_filter = self.config.get('severity_filter')  # None = all severities

    # ========================================================================
    # Spec Record Detection
    # ========================================================================

    def detect_spec_issues(
        self,
        spec_records: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QualityIssue]:
        """
        Detect issues in specification records.

        Args:
            spec_records: List of spec record dicts (from DB or raw data)
            filters: Optional filters (brand, series_l1, series_l2)

        Returns:
            List of QualityIssue objects
        """
        issues = []
        filtered_records = self._apply_filters(spec_records, filters)

        logger.info(f"Detecting spec issues for {len(filtered_records)} records")

        # Process in batches for efficiency
        batch_size = 1000
        for i in range(0, len(filtered_records), batch_size):
            batch = filtered_records[i:i + batch_size]
            batch_issues = self._detect_spec_batch(batch)
            issues.extend(batch_issues)

        # Store and track statistics
        self._detected_issues.extend(issues)
        for issue in issues:
            self.statistics.increment(issue.issue_type, issue.severity, issue.brand)

        logger.info(f"Detected {len(issues)} spec issues")
        return issues

    def _detect_spec_batch(self, batch: List[Dict[str, Any]]) -> List[QualityIssue]:
        """Detect issues in a batch of spec records."""
        issues = []

        for record in batch:
            # Check each rule type
            issues.extend(self._check_missing_field_rules(record))
            issues.extend(self._check_parse_failed_rules(record))
            issues.extend(self._check_unit_abnormal_rules(record))

        return issues

    def _check_missing_field_rules(self, record: Dict[str, Any]) -> List[QualityIssue]:
        """Check missing field rules on a single record."""
        issues = []

        field_code = record.get('field_code', '')
        if field_code not in REQUIRED_FIELDS:
            return []

        if _check_missing_field(record):
            issues.append(QualityIssue(
                run_id=self.run_id,
                brand=record.get('brand', ''),
                series_l1=record.get('series_l1', ''),
                series_l2=record.get('series_l2', ''),
                model=record.get('model', ''),
                issue_type=IssueType.MISSING_FIELD.value,
                field_code=field_code,
                detail=f"Required field '{field_code}' is missing or empty",
                severity=Severity.P2.value
            ))

        return issues

    def _check_parse_failed_rules(self, record: Dict[str, Any]) -> List[QualityIssue]:
        """Check parse failed rules on a single record."""
        issues = []

        if _check_parse_failed(record):
            confidence = record.get('extract_confidence', 0.0)
            field_code = record.get('field_code', '')

            issues.append(QualityIssue(
                run_id=self.run_id,
                brand=record.get('brand', ''),
                series_l1=record.get('series_l1', ''),
                series_l2=record.get('series_l2', ''),
                model=record.get('model', ''),
                issue_type=IssueType.PARSE_FAILED.value,
                field_code=field_code,
                detail=f"Field '{field_code}' parsing failed (confidence: {confidence:.2f})",
                severity=Severity.P1.value
            ))

        return issues

    def _check_unit_abnormal_rules(self, record: Dict[str, Any]) -> List[QualityIssue]:
        """Check unit abnormal rules on a single record."""
        issues = []

        if _check_unit_abnormal(record):
            field_code = record.get('field_code', '')
            unit = record.get('unit', '')

            issues.append(QualityIssue(
                run_id=self.run_id,
                brand=record.get('brand', ''),
                series_l1=record.get('series_l1', ''),
                series_l2=record.get('series_l2', ''),
                model=record.get('model', ''),
                issue_type=IssueType.UNIT_ABNORMAL.value,
                field_code=field_code,
                detail=f"Unit '{unit}' is abnormal or doesn't match expected for field '{field_code}'",
                severity=Severity.P3.value
            ))

        return issues

    # ========================================================================
    # Duplicate Detection (Cross-Record Analysis)
    # ========================================================================

    def detect_duplicate_models(
        self,
        spec_records: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QualityIssue]:
        """
        Detect duplicate models with conflicting data.

        Args:
            spec_records: List of spec record dicts
            filters: Optional filters

        Returns:
            List of QualityIssue objects for duplicates
        """
        if not self._enable_duplicate_detection:
            return []

        issues = []
        filtered_records = self._apply_filters(spec_records, filters)

        # Group records by model
        model_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for record in filtered_records:
            model_key = self._make_model_key(record)
            model_groups[model_key].append(record)

        # Check each model group for duplicates
        for model_key, records in model_groups.items():
            if len(records) < 2:
                continue

            # Group by field_code within the model
            field_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for record in records:
                field_code = record.get('field_code', '')
                if field_code:
                    field_groups[field_code].append(record)

            # Check for conflicting values per field
            for field_code, field_records in field_groups.items():
                if len(field_records) < 2:
                    continue

                duplicates = _check_duplicate_model(field_records, field_code)
                if duplicates:
                    # Create issue for each duplicate record
                    for dup_record in duplicates:
                        issues.append(QualityIssue(
                            run_id=self.run_id,
                            brand=dup_record.get('brand', ''),
                            series_l1=dup_record.get('series_l1', ''),
                            series_l2=dup_record.get('series_l2', ''),
                            model=dup_record.get('model', ''),
                            issue_type=IssueType.DUPLICATE_MODEL.value,
                            field_code=field_code,
                            detail=f"Model has conflicting values for field '{field_code}'",
                            severity=Severity.P2.value
                        ))

        # Track statistics
        for issue in issues:
            self.statistics.increment(issue.issue_type, issue.severity, issue.brand)

        logger.info(f"Detected {len(issues)} duplicate model issues")
        return issues

    def _make_model_key(self, record: Dict[str, Any]) -> str:
        """Create a unique key for a model."""
        brand = record.get('brand', '')
        series_l1 = record.get('series_l1', '')
        series_l2 = record.get('series_l2', '')
        model = record.get('model', '')
        return f"{brand}|{series_l1}|{series_l2}|{model}"

    # ========================================================================
    # Catalog Detection
    # ========================================================================

    def detect_catalog_issues(
        self,
        catalog_records: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QualityIssue]:
        """
        Detect issues in catalog data (e.g., empty subseries).

        Args:
            catalog_records: List of catalog item dicts
            filters: Optional filters

        Returns:
            List of QualityIssue objects
        """
        issues = []
        filtered_records = self._apply_filters(catalog_records, filters)

        # Group by subseries
        subseries_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for record in filtered_records:
            subseries_key = self._make_subseries_key(record)
            subseries_groups[subseries_key].append(record)

        # Check for empty subseries
        for subseries_key, products in subseries_groups.items():
            if _check_subseries_empty({'products': products, 'product_count': len(products)}):
                # Parse subseries key
                parts = subseries_key.split('|')
                if len(parts) >= 3:
                    brand = parts[0]
                    series_l1 = parts[1]
                    series_l2 = parts[2]

                    issues.append(QualityIssue(
                        run_id=self.run_id,
                        brand=brand,
                        series_l1=series_l1,
                        series_l2=series_l2,
                        model='',  # Subseries-level issue, not specific to model
                        issue_type=IssueType.SUBSERIES_EMPTY.value,
                        field_code=None,
                        detail=f"Subseries '{series_l2}' has no products",
                        severity=Severity.P2.value
                    ))

        # Track statistics
        for issue in issues:
            self.statistics.increment(issue.issue_type, issue.severity, issue.brand)

        logger.info(f"Detected {len(issues)} catalog issues")
        return issues

    def _make_subseries_key(self, record: Dict[str, Any]) -> str:
        """Create a unique key for a subseries."""
        brand = record.get('brand', '')
        series_l1 = record.get('series_l1', '')
        series_l2 = record.get('series_l2', '')
        return f"{brand}|{series_l1}|{series_l2}"

    # ========================================================================
    # Hierarchy Change Detection
    # ========================================================================

    def detect_hierarchy_changes(
        self,
        current_hierarchy: List[Dict[str, Any]],
        previous_hierarchy: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QualityIssue]:
        """
        Detect hierarchy structure changes between runs.

        Args:
            current_hierarchy: List of current hierarchy node dicts
            previous_hierarchy: List of previous hierarchy node dicts
            filters: Optional filters

        Returns:
            List of QualityIssue objects for hierarchy changes
        """
        if not self._enable_hierarchy_change_detection:
            return []

        issues = []

        # Build hierarchy path sets
        current_set = self._build_hierarchy_set(current_hierarchy, filters)
        previous_set = self._build_hierarchy_set(previous_hierarchy, filters)

        # Detect changes
        changes = _check_hierarchy_changed(current_set, previous_set)

        # Create issues for added nodes
        for path in changes['added']:
            parts = path.split('|')
            if len(parts) >= 2:
                brand = parts[0]
                series_l1 = parts[1] if len(parts) > 1 else ''
                series_l2 = parts[2] if len(parts) > 2 else ''

                issues.append(QualityIssue(
                    run_id=self.run_id,
                    brand=brand,
                    series_l1=series_l1,
                    series_l2=series_l2,
                    model='',
                    issue_type=IssueType.HIERARCHY_CHANGED.value,
                    field_code=None,
                    detail=f"New hierarchy node added: {path}",
                    severity=Severity.P3.value
                ))

        # Create issues for removed nodes
        for path in changes['removed']:
            parts = path.split('|')
            if len(parts) >= 2:
                brand = parts[0]
                series_l1 = parts[1] if len(parts) > 1 else ''
                series_l2 = parts[2] if len(parts) > 2 else ''

                issues.append(QualityIssue(
                    run_id=self.run_id,
                    brand=brand,
                    series_l1=series_l1,
                    series_l2=series_l2,
                    model='',
                    issue_type=IssueType.HIERARCHY_CHANGED.value,
                    field_code=None,
                    detail=f"Hierarchy node disappeared: {path}",
                    severity=Severity.P3.value
                ))

        # Track statistics
        for issue in issues:
            self.statistics.increment(issue.issue_type, issue.severity, issue.brand)

        logger.info(f"Detected {len(issues)} hierarchy change issues")
        return issues

    def _build_hierarchy_set(
        self,
        hierarchy_list: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> Set[str]:
        """Build a set of hierarchy paths from hierarchy node list."""
        paths = set()

        for node in hierarchy_list:
            # Apply filters
            if filters:
                brand_filter = filters.get('brand')
                series_l1_filter = filters.get('series_l1')

                if brand_filter and node.get('brand') != brand_filter:
                    continue
                if series_l1_filter and node.get('series_l1') != series_l1_filter:
                    continue

            # Build path
            brand = node.get('brand', '')
            series_l1 = node.get('series_l1', '')
            series_l2 = node.get('series_l2', '')

            # Add path at series_l1 level
            if series_l1:
                paths.add(f"{brand}|{series_l1}|")

            # Add path at series_l2 level
            if series_l2:
                paths.add(f"{brand}|{series_l1}|{series_l2}")

        return paths

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _apply_filters(
        self,
        records: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply filters to a list of records."""
        if not filters:
            return records

        filtered = []
        for record in records:
            match = True

            if 'brand' in filters:
                if record.get('brand') != filters['brand']:
                    match = False

            if 'series_l1' in filters:
                if record.get('series_l1') != filters['series_l1']:
                    match = False

            if 'series_l2' in filters:
                if record.get('series_l2') != filters['series_l2']:
                    match = False

            if 'model' in filters:
                if record.get('model') != filters['model']:
                    match = False

            if match:
                filtered.append(record)

        return filtered

    def get_statistics(self) -> DetectionStatistics:
        """Get detection statistics."""
        return self.statistics

    def get_detected_issues(self) -> List[QualityIssue]:
        """Get all detected issues from this detector instance."""
        return self._detected_issues.copy()

    def reset(self) -> None:
        """Reset detector state."""
        self._detected_issues.clear()
        self.statistics.reset()

    def export_issues_to_dicts(self, issues: List[QualityIssue]) -> List[Dict[str, Any]]:
        """
        Convert QualityIssue objects to dicts for database export.

        Args:
            issues: List of QualityIssue objects

        Returns:
            List of dicts suitable for database insertion
        """
        return [
            {
                'run_id': issue.run_id,
                'brand': issue.brand,
                'series_l1': issue.series_l1,
                'series_l2': issue.series_l2,
                'product_model': issue.model,
                'issue_type': issue.issue_type,
                'field_code': issue.field_code,
                'issue_detail': issue.detail,
                'severity': issue.severity,
                'status': 'open',
                'created_at': datetime.utcnow()
            }
            for issue in issues
        ]
