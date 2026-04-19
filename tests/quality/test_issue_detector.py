"""
Unit tests for quality issue detection modules.

Tests cover:
- Rule registry functionality
- Spec record issue detection (missing, parse_failed, unit_abnormal)
- Duplicate model detection
- Hierarchy change detection
- Statistics tracking
- Filtering functionality
"""

from src.quality import IssueDetector, rule_registry
from src.core.constants import IssueType, Severity


class TestRuleRegistry:
    """Test rule registry functionality."""

    def test_get_all_rules(self):
        """Test getting all rules."""
        all_rules = rule_registry.get_all_rule_ids()
        assert len(all_rules) == 3
        assert 'missing_required_field' in all_rules
        assert 'parse_failed_low_confidence' in all_rules
        assert 'unit_mismatch_expected' in all_rules

    def test_filter_by_severity(self):
        """Test filtering rules by severity."""
        p1_rules = rule_registry.get_rules(severity=Severity.P1)
        assert len(p1_rules) == 1
        assert p1_rules[0].issue_type == IssueType.PARSE_FAILED

        p2_rules = rule_registry.get_rules(severity=Severity.P2)
        assert len(p2_rules) == 1
        assert p2_rules[0].issue_type == IssueType.MISSING_FIELD

        p3_rules = rule_registry.get_rules(severity=Severity.P3)
        assert len(p3_rules) == 1
        assert p3_rules[0].issue_type == IssueType.UNIT_ABNORMAL

    def test_filter_by_field(self):
        """Test filtering rules by field code."""
        image_sensor_rules = rule_registry.get_rules(field_code='image_sensor')
        assert len(image_sensor_rules) >= 1  # At least missing_field rule

        # Test field that doesn't have unit rules
        lens_type_rules = rule_registry.get_rules(field_code='lens_type')
        # Should have missing_field and parse_failed, but NOT unit_abnormal
        assert len(lens_type_rules) == 2
        rule_types = {r.issue_type for r in lens_type_rules}
        assert IssueType.UNIT_ABNORMAL not in rule_types
        assert IssueType.MISSING_FIELD in rule_types
        assert IssueType.PARSE_FAILED in rule_types

        # Test field that HAS unit rules
        max_res_rules = rule_registry.get_rules(field_code='max_resolution')
        # Should have all three: missing_field, parse_failed, unit_abnormal
        assert len(max_res_rules) == 3
        rule_types = {r.issue_type for r in max_res_rules}
        assert IssueType.UNIT_ABNORMAL in rule_types


class TestSpecIssueDetection:
    """Test spec record issue detection."""

    def test_missing_field_detection(self):
        """Test detection of missing required fields."""
        detector = IssueDetector(run_id='test_run')

        spec = {
            'brand': 'HIKVISION',
            'series_l1': 'Value',
            'series_l2': '2-Line',
            'model': 'DS-2CD2T45D0W-I3',
            'field_code': 'image_sensor',
            'raw_value': '',
            'normalized_value': None,
            'extract_confidence': 1.0
        }

        issues = detector.detect_spec_issues([spec])
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.MISSING_FIELD.value
        assert issues[0].severity == Severity.P2.value
        assert issues[0].field_code == 'image_sensor'

    def test_parse_failed_detection(self):
        """Test detection of parse failures via low confidence."""
        detector = IssueDetector(run_id='test_run')

        spec = {
            'brand': 'HIKVISION',
            'series_l1': 'Value',
            'series_l2': '2-Line',
            'model': 'DS-2CD2T45D0W-I3',
            'field_code': 'max_resolution',
            'raw_value': '2688x1520',
            'normalized_value': '2688x1520',
            'extract_confidence': 0.3  # Low confidence
        }

        issues = detector.detect_spec_issues([spec])
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.PARSE_FAILED.value
        assert issues[0].severity == Severity.P1.value

    def test_unit_abnormal_detection(self):
        """Test detection of unit mismatches."""
        detector = IssueDetector(run_id='test_run')

        spec = {
            'brand': 'DAHUA',
            'series_l1': 'WizSense',
            'series_l2': '3-Series',
            'model': 'IPC-HFW3541T-ZAS',
            'field_code': 'supplement_light_range',
            'raw_value': '50m',
            'normalized_value': '50',
            'unit': 'ft',  # Wrong unit (should be 'm')
            'extract_confidence': 1.0
        }

        issues = detector.detect_spec_issues([spec])
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.UNIT_ABNORMAL.value
        assert issues[0].severity == Severity.P3.value
        assert 'ft' in issues[0].detail

    def test_no_issues_for_valid_spec(self):
        """Test that valid specs don't trigger issues."""
        detector = IssueDetector(run_id='test_run')

        spec = {
            'brand': 'HIKVISION',
            'series_l1': 'Value',
            'series_l2': '2-Line',
            'model': 'DS-2CD2T45D0W-I3',
            'field_code': 'image_sensor',
            'raw_value': '1/2.7\" Progressive Scan CMOS',
            'normalized_value': '1/2.7\" Progressive Scan CMOS',
            'extract_confidence': 1.0
        }

        issues = detector.detect_spec_issues([spec])
        assert len(issues) == 0


class TestDuplicateDetection:
    """Test duplicate model detection."""

    def test_duplicate_model_detection(self):
        """Test detection of conflicting duplicate models."""
        detector = IssueDetector(run_id='test_run')

        specs = [
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'max_resolution',
                'raw_value': '2688x1520',
                'normalized_value': '2688x1520',
                'unit': 'px',
                'extract_confidence': 1.0
            },
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',  # Same model
                'field_code': 'max_resolution',
                'raw_value': '4K',
                'normalized_value': '3840x2160',  # Different value
                'unit': 'px',
                'extract_confidence': 1.0
            }
        ]

        issues = detector.detect_duplicate_models(specs)
        assert len(issues) == 2  # Both records flagged
        assert all(i.issue_type == IssueType.DUPLICATE_MODEL.value for i in issues)
        assert all(i.severity == Severity.P2.value for i in issues)

    def test_no_duplicate_for_same_values(self):
        """Test that same values don't trigger duplicate detection."""
        detector = IssueDetector(run_id='test_run')

        specs = [
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'max_resolution',
                'raw_value': '2688x1520',
                'normalized_value': '2688x1520',
                'unit': 'px',
                'extract_confidence': 1.0
            },
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'max_resolution',
                'raw_value': '2688x1520',  # Same value
                'normalized_value': '2688x1520',
                'unit': 'px',
                'extract_confidence': 1.0
            }
        ]

        issues = detector.detect_duplicate_models(specs)
        assert len(issues) == 0


class TestHierarchyChangeDetection:
    """Test hierarchy change detection."""

    def test_added_hierarchy_detection(self):
        """Test detection of newly added hierarchy nodes."""
        detector = IssueDetector(run_id='test_run')

        current = [
            {'brand': 'HIKVISION', 'series_l1': 'Value', 'series_l2': '2-Line'},
            {'brand': 'HIKVISION', 'series_l1': 'Pro', 'series_l2': '1-Series'},  # New
        ]

        previous = [
            {'brand': 'HIKVISION', 'series_l1': 'Value', 'series_l2': '2-Line'},
        ]

        issues = detector.detect_hierarchy_changes(current, previous)
        assert len(issues) == 2  # Pro series and Pro|1-Series
        assert all(i.issue_type == IssueType.HIERARCHY_CHANGED.value for i in issues)
        assert all('New hierarchy node added' in i.detail for i in issues)

    def test_removed_hierarchy_detection(self):
        """Test detection of removed hierarchy nodes."""
        detector = IssueDetector(run_id='test_run')

        current = [
            {'brand': 'HIKVISION', 'series_l1': 'Value', 'series_l2': '2-Line'},
        ]

        previous = [
            {'brand': 'HIKVISION', 'series_l1': 'Value', 'series_l2': '2-Line'},
            {'brand': 'HIKVISION', 'series_l1': 'Legacy', 'series_l2': 'Old-Series'},  # Removed
        ]

        issues = detector.detect_hierarchy_changes(current, previous)
        assert len(issues) == 2  # Legacy series and Legacy|Old-Series
        assert all('disappeared' in i.detail for i in issues)


class TestStatistics:
    """Test statistics tracking."""

    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        detector = IssueDetector(run_id='test_run')

        specs = [
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'image_sensor',
                'raw_value': '',
                'normalized_value': None,
                'extract_confidence': 1.0
            },
            {
                'brand': 'DAHUA',
                'series_l1': 'WizSense',
                'series_l2': '3-Series',
                'model': 'IPC-HFW3541T-ZAS',
                'field_code': 'max_resolution',
                'raw_value': '4K',
                'normalized_value': '3840x2160',
                'extract_confidence': 0.3
            }
        ]

        detector.detect_spec_issues(specs)

        stats = detector.get_statistics()
        assert stats.total() == 2
        assert stats.get_by_type().get('missing_field') == 1
        assert stats.get_by_type().get('parse_failed') == 1
        assert stats.get_by_severity().get('P1') == 1
        assert stats.get_by_severity().get('P2') == 1
        assert stats.get_by_brand().get('HIKVISION') == 1
        assert stats.get_by_brand().get('DAHUA') == 1

    def test_statistics_reset(self):
        """Test that statistics can be reset."""
        detector = IssueDetector(run_id='test_run')

        spec = {
            'brand': 'HIKVISION',
            'series_l1': 'Value',
            'series_l2': '2-Line',
            'model': 'DS-2CD2T45D0W-I3',
            'field_code': 'image_sensor',
            'raw_value': '',
            'normalized_value': None,
            'extract_confidence': 1.0
        }

        detector.detect_spec_issues([spec])
        assert detector.get_statistics().total() > 0

        detector.reset()
        assert detector.get_statistics().total() == 0


class TestFiltering:
    """Test filtering functionality."""

    def test_brand_filter(self):
        """Test filtering by brand."""
        detector = IssueDetector(run_id='test_run')

        specs = [
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'image_sensor',
                'raw_value': '',
                'normalized_value': None,
                'extract_confidence': 1.0
            },
            {
                'brand': 'DAHUA',
                'series_l1': 'WizSense',
                'series_l2': '3-Series',
                'model': 'IPC-HFW3541T-ZAS',
                'field_code': 'image_sensor',
                'raw_value': '',
                'normalized_value': None,
                'extract_confidence': 1.0
            }
        ]

        hikvision_issues = detector.detect_spec_issues(specs, filters={'brand': 'HIKVISION'})
        assert len(hikvision_issues) == 1
        assert hikvision_issues[0].brand == 'HIKVISION'

    def test_series_filter(self):
        """Test filtering by series."""
        detector = IssueDetector(run_id='test_run')

        specs = [
            {
                'brand': 'HIKVISION',
                'series_l1': 'Value',
                'series_l2': '2-Line',
                'model': 'DS-2CD2T45D0W-I3',
                'field_code': 'image_sensor',
                'raw_value': '',
                'normalized_value': None,
                'extract_confidence': 1.0
            },
            {
                'brand': 'HIKVISION',
                'series_l1': 'Pro',
                'series_l2': '1-Series',
                'model': 'DS-2CD3T45D0W-I3',
                'field_code': 'image_sensor',
                'raw_value': '',
                'normalized_value': None,
                'extract_confidence': 1.0
            }
        ]

        value_issues = detector.detect_spec_issues(specs, filters={'series_l1': 'Value'})
        assert len(value_issues) == 1
        assert value_issues[0].series_l1 == 'Value'


if __name__ == '__main__':
    import sys

    test_classes = [
        TestRuleRegistry,
        TestSpecIssueDetection,
        TestDuplicateDetection,
        TestHierarchyChangeDetection,
        TestStatistics,
        TestFiltering,
    ]

    failed = 0
    for test_class in test_classes:
        print(f'\n{test_class.__name__}:')
        obj = test_class()
        for method_name in dir(obj):
            if method_name.startswith('test_'):
                method = getattr(obj, method_name)
                try:
                    method()
                    print(f'  ✓ {method_name}')
                except AssertionError as e:
                    print(f'  ✗ {method_name}: {e}')
                    failed += 1
                except Exception as e:
                    print(f'  ✗ {method_name}: {type(e).__name__}: {e}')
                    failed += 1

    if failed == 0:
        print(f'\n✅ All {sum(len([m for m in dir(obj) if m.startswith("test_")]) for obj in [tc() for tc in test_classes])} tests passed!')
        sys.exit(0)
    else:
        print(f'\n❌ {failed} test(s) failed')
        sys.exit(1)
