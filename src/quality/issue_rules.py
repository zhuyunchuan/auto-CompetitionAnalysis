"""
Quality issue rules definition module.

This module defines all data quality issue detection rules with their severity levels,
applicability conditions, and detection logic. Rules are organized by issue type and
can be selectively applied based on configuration.

Rule Types:
- missing_field (P2): Required field is empty or not extracted
- parse_failed (P1): Field extraction failed due to parsing errors
- unit_abnormal (P3): Unit is unrecognized or conversion failed
- duplicate_model (P2): Same model appears with conflicting data
- subseries_empty (P2): Subseries has no products
- hierarchy_changed (P3): Series/subseries structure changed from previous runs
"""

from dataclasses import dataclass
from typing import Callable, Optional, Set, List, Dict, Any
from datetime import datetime

from src.core.constants import IssueType, Severity, REQUIRED_FIELDS, FIELD_UNITS


@dataclass
class QualityRule:
    """
    Represents a single quality issue detection rule.

    Attributes:
        rule_id: Unique identifier for the rule
        issue_type: Type of issue this rule detects
        severity: Severity level (P1, P2, P3)
        description: Human-readable description of the rule
        field_codes: Set of field codes this rule applies to (None = all fields)
        check_fn: Detection function that returns True if issue is present
        message_template: Template for issue detail messages
    """
    rule_id: str
    issue_type: IssueType
    severity: Severity
    description: str
    field_codes: Optional[Set[str]]
    check_fn: Callable[[Dict[str, Any]], bool]
    message_template: str

    def applies_to_field(self, field_code: str) -> bool:
        """Check if this rule applies to a specific field."""
        if self.field_codes is None:
            return True
        return field_code in self.field_codes


# ============================================================================
# Rule Detection Functions
# ============================================================================

def _check_missing_field(spec_record: Dict[str, Any]) -> bool:
    """
    Check if a required field is missing or empty.

    A field is considered missing if:
    - raw_value is None or empty string
    - normalized_value is None or empty string
    - Field is in REQUIRED_FIELDS set
    """
    raw_value = spec_record.get('raw_value', '')
    normalized_value = spec_record.get('normalized_value', '')

    # Check if both raw and normalized values are empty
    is_empty = not raw_value or raw_value.strip() == ''
    is_empty = is_empty or (normalized_value is None or normalized_value.strip() == '')

    return is_empty


def _check_parse_failed(spec_record: Dict[str, Any]) -> bool:
    """
    Check if field parsing failed.

    Parse failure indicators:
    - extract_confidence < 0.5 (low confidence indicates parsing issues)
    - raw_value exists but normalized_value is None (parsing attempted but failed)
    - field_code contains parsing errors (e.g., "ERROR:", "PARSE_FAILED:")
    """
    confidence = spec_record.get('extract_confidence', 1.0)
    raw_value = spec_record.get('raw_value', '')
    normalized_value = spec_record.get('normalized_value')

    # Low confidence indicates parsing failure
    if confidence < 0.5:
        return True

    # Raw value exists but parsing produced no result
    if raw_value and normalized_value is None:
        return True

    # Check for error markers in raw value
    if raw_value and any(marker in raw_value.upper() for marker in ['ERROR:', 'PARSE_FAILED:', 'N/A']):
        return True

    return False


def _check_unit_abnormal(spec_record: Dict[str, Any]) -> bool:
    """
    Check if unit is unrecognized or abnormal.

    Unit issues:
    - Expected unit defined but actual unit is None
    - Actual unit doesn't match expected unit
    - Unit conversion would fail

    Note: Skips check if parsing failed (low confidence) to avoid cascading issues.
    """
    field_code = spec_record.get('field_code', '')
    expected_unit = FIELD_UNITS.get(field_code)
    actual_unit = spec_record.get('unit')
    confidence = spec_record.get('extract_confidence', 1.0)

    # Skip if parsing failed (avoid cascading issues)
    if confidence < 0.5:
        return False

    # If no unit expected, skip check
    if expected_unit is None:
        return False

    # Unit expected but missing
    if actual_unit is None or actual_unit.strip() == '':
        return True

    # Unit mismatch (case-insensitive)
    if actual_unit.lower() != expected_unit.lower():
        # Special case: fps+px allows variants
        if expected_unit == 'fps+px' and actual_unit in ['fps', 'px', 'fps+px']:
            return False
        return True

    return False


def _check_duplicate_model(
    model_records: List[Dict[str, Any]],
    field_code: str
) -> List[Dict[str, Any]]:
    """
    Check for duplicate models with conflicting data.

    Returns list of records that are duplicates.
    Two records are considered conflicting duplicates if:
    - Same brand, series_l1, series_l2, model
    - Same field_code
    - Different normalized values
    """
    if len(model_records) < 2:
        return []

    # Group by unique value
    value_groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in model_records:
        norm_value = record.get('normalized_value', '') or ''
        if norm_value not in value_groups:
            value_groups[norm_value] = []
        value_groups[norm_value].append(record)

    # If all values are the same, not a conflict
    if len(value_groups) == 1:
        return []

    # Return all records as conflicting duplicates
    duplicates = []
    for records in value_groups.values():
        duplicates.extend(records)

    return duplicates


def _check_subseries_empty(subseries_data: Dict[str, Any]) -> bool:
    """
    Check if a subseries has no products.

    A subseries is empty if:
    - product_count is 0
    - products list is empty
    """
    product_count = subseries_data.get('product_count', 0)
    products = subseries_data.get('products', [])

    return product_count == 0 or len(products) == 0


def _check_hierarchy_changed(
    current_hierarchy: Set[str],
    previous_hierarchy: Set[str]
) -> Dict[str, Set[str]]:
    """
    Check for hierarchy changes between runs.

    Returns dict with 'added' and 'removed' sets of hierarchy paths.
    """
    added = current_hierarchy - previous_hierarchy
    removed = previous_hierarchy - current_hierarchy

    return {
        'added': added,
        'removed': removed
    }


# ============================================================================
# Rule Definitions
# ============================================================================

# Initialize all rules
MISSING_FIELD_RULES: List[QualityRule] = [
    QualityRule(
        rule_id="missing_required_field",
        issue_type=IssueType.MISSING_FIELD,
        severity=Severity.P2,
        description="Required field is empty or not extracted",
        field_codes=REQUIRED_FIELDS,
        check_fn=_check_missing_field,
        message_template="Required field '{field_code}' is missing or empty for model {model}"
    )
]

PARSE_FAILED_RULES: List[QualityRule] = [
    QualityRule(
        rule_id="parse_failed_low_confidence",
        issue_type=IssueType.PARSE_FAILED,
        severity=Severity.P1,
        description="Field parsing failed with low confidence",
        field_codes=None,  # Applies to all fields
        check_fn=_check_parse_failed,
        message_template="Field '{field_code}' parsing failed for model {model} (confidence: {confidence})"
    )
]

UNIT_ABNORMAL_RULES: List[QualityRule] = [
    QualityRule(
        rule_id="unit_mismatch_expected",
        issue_type=IssueType.UNIT_ABNORMAL,
        severity=Severity.P3,
        description="Unit doesn't match expected canonical unit",
        field_codes={fc for fc, unit in FIELD_UNITS.items() if unit is not None},  # Only fields with units
        check_fn=_check_unit_abnormal,
        message_template="Unit '{unit}' doesn't match expected '{expected_unit}' for field '{field_code}' on model {model}"
    )
]

# Note: duplicate_model, subseries_empty, and hierarchy_changed rules
# are handled separately in issue_detector.py as they require
# cross-record or cross-run analysis


# ============================================================================
# Rule Registry
# ============================================================================

class RuleRegistry:
    """
    Central registry for all quality rules.

    Provides methods to query rules by type, severity, or field applicability.
    """

    def __init__(self):
        self._rules = {
            IssueType.MISSING_FIELD: MISSING_FIELD_RULES,
            IssueType.PARSE_FAILED: PARSE_FAILED_RULES,
            IssueType.UNIT_ABNORMAL: UNIT_ABNORMAL_RULES,
        }

    def get_rules(
        self,
        issue_type: Optional[IssueType] = None,
        severity: Optional[Severity] = None,
        field_code: Optional[str] = None
    ) -> List[QualityRule]:
        """
        Get rules filtered by issue type, severity, and/or field code.

        Args:
            issue_type: Filter by issue type (None = all types)
            severity: Filter by severity level (None = all severities)
            field_code: Filter by field applicability (None = all fields)

        Returns:
            List of matching rules
        """
        rules = []

        if issue_type:
            rules = self._rules.get(issue_type, [])
        else:
            # Flatten all rules
            for rule_list in self._rules.values():
                rules.extend(rule_list)

        # Filter by severity
        if severity:
            rules = [r for r in rules if r.severity == severity]

        # Filter by field code
        if field_code:
            rules = [r for r in rules if r.applies_to_field(field_code)]

        return rules

    def get_rule_by_id(self, rule_id: str) -> Optional[QualityRule]:
        """Get a specific rule by its ID."""
        for rule_list in self._rules.values():
            for rule in rule_list:
                if rule.rule_id == rule_id:
                    return rule
        return None

    def get_all_rule_ids(self) -> Set[str]:
        """Get all rule IDs."""
        rule_ids = set()
        for rule_list in self._rules.values():
            for rule in rule_list:
                rule_ids.add(rule.rule_id)
        return rule_ids

    def get_severity_levels(self) -> List[Severity]:
        """Get all defined severity levels."""
        return [Severity.P1, Severity.P2, Severity.P3]

    def get_issue_types(self) -> List[IssueType]:
        """Get all defined issue types."""
        return list(IssueType)


# Global rule registry instance
rule_registry = RuleRegistry()
