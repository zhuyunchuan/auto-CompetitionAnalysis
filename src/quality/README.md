# Quality Detection Module

Data quality issue detection engine for the competitor scraping system.

## Overview

The quality module detects data quality issues in scraped product specifications, catalog data, and hierarchy information. It provides a rule-based detection system with configurable severity levels and comprehensive statistics tracking.

## Features

- **6 Issue Types**: missing_field, parse_failed, unit_abnormal, duplicate_model, subseries_empty, hierarchy_changed
- **3 Severity Levels**: P1 (critical), P2 (high), P3 (medium)
- **Batch Processing**: Efficient processing of large datasets
- **Filtering**: Filter by severity, brand, series, model
- **Statistics**: Track issue counts by type, severity, and brand
- **Cross-Record Analysis**: Detect duplicates and hierarchy changes

## Architecture

```
src/quality/
├── __init__.py              # Package exports
├── issue_rules.py           # Rule definitions and registry
├── issue_detector.py        # Main detection engine
└── README.md               # This file
```

## Issue Types

### 1. missing_field (P2)
A required field is empty or was not extracted.

**Detection**: `raw_value` is empty AND `normalized_value` is None

**Applicability**: All fields in `REQUIRED_FIELDS` set (12 core fields)

**Example**:
```python
{
    'field_code': 'image_sensor',
    'raw_value': '',
    'normalized_value': None
}
# → Issue: "Required field 'image_sensor' is missing or empty"
```

### 2. parse_failed (P1)
Field extraction failed due to parsing errors or low confidence.

**Detection**:
- `extract_confidence < 0.5` (low confidence)
- `raw_value` exists but `normalized_value` is None
- Error markers in raw_value (ERROR:, PARSE_FAILED:, N/A)

**Example**:
```python
{
    'field_code': 'max_resolution',
    'raw_value': '2688x1520',
    'normalized_value': '2688x1520',
    'extract_confidence': 0.3  # Low!
}
# → Issue: "Field 'max_resolution' parsing failed (confidence: 0.30)"
```

### 3. unit_abnormal (P3)
Unit is unrecognized or doesn't match expected canonical unit.

**Detection**:
- Expected unit defined in `FIELD_UNITS`
- Actual unit is None, empty, or doesn't match expected

**Note**: Skipped if confidence < 0.5 (avoids cascading issues with parse_failed)

**Example**:
```python
{
    'field_code': 'supplement_light_range',
    'unit': 'ft'  # Expected: 'm'
}
# → Issue: "Unit 'ft' is abnormal or doesn't match expected"
```

### 4. duplicate_model (P2)
Same model appears multiple times with conflicting values for the same field.

**Detection**: Same (brand, series_l1, series_l2, model, field_code) but different `normalized_value`

**Example**:
```python
# Record 1:
{
    'model': 'DS-2CD2T45D0W-I3',
    'field_code': 'max_resolution',
    'normalized_value': '2688x1520'
}
# Record 2:
{
    'model': 'DS-2CD2T45D0W-I3',  # Same model
    'field_code': 'max_resolution',
    'normalized_value': '3840x2160'  # Different!
}
# → Issue: "Model has conflicting values for field 'max_resolution'"
```

### 5. subseries_empty (P2)
A subseries (series_l2) has no products.

**Detection**: `product_count == 0` or empty products list

**Example**:
```python
{
    'series_l2': '3-Line',
    'products': [],
    'product_count': 0
}
# → Issue: "Subseries '3-Line' has no products"
```

### 6. hierarchy_changed (P3)
Series/subseries structure changed between runs (added or removed).

**Detection**: Set difference between current and previous hierarchy paths

**Example**:
```python
# Previous run had "Value|Legacy-Series"
# Current run has "Value|2-Line" and "Pro|1-Series"
# → Issues:
#   - "New hierarchy node added: HIKVISION|Pro|1-Series"
#   - "Hierarchy node disappeared: HIKVISION|Value|Legacy-Series"
```

## Usage

### Basic Detection

```python
from src.quality import IssueDetector

# Initialize detector
detector = IssueDetector(run_id='20260418_biweekly_01')

# Detect spec issues
issues = detector.detect_spec_issues(spec_records)

# Detect duplicate models
issues.extend(detector.detect_duplicate_models(spec_records))

# Detect hierarchy changes
issues.extend(detector.detect_hierarchy_changes(
    current_hierarchy,
    previous_hierarchy
))

# Get statistics
stats = detector.get_statistics()
print(f"Total issues: {stats.total()}")
print(f"By severity: {stats.get_by_severity()}")
print(f"By type: {stats.get_by_type()}")
```

### Filtering

```python
# Filter by brand
hikvision_issues = detector.detect_spec_issues(
    spec_records,
    filters={'brand': 'HIKVISION'}
)

# Filter by series
value_series_issues = detector.detect_spec_issues(
    spec_records,
    filters={'brand': 'HIKVISION', 'series_l1': 'Value'}
)

# Filter by severity
p1_issues = [i for i in issues if i.severity == 'P1']
```

### Export to Database

```python
# Convert QualityIssue objects to dicts
issue_dicts = detector.export_issues_to_dicts(issues)

# Insert into database (using SQLAlchemy)
from src.storage.schema import DataQualityIssue

for issue_dict in issue_dicts:
    db_issue = DataQualityIssue(**issue_dict)
    session.add(db_issue)

session.commit()
```

## Rule Registry

```python
from src.quality import rule_registry
from src.core.constants import Severity, IssueType

# Get all rules
all_rules = rule_registry.get_all_rule_ids()

# Get rules by severity
p1_rules = rule_registry.get_rules(severity=Severity.P1)

# Get rules by issue type
missing_rules = rule_registry.get_rules(issue_type=IssueType.MISSING_FIELD)

# Get rules for specific field
field_rules = rule_registry.get_rules(field_code='max_resolution')

# Combine filters
high_priority_unit_rules = rule_registry.get_rules(
    severity=Severity.P1,
    issue_type=IssueType.UNIT_ABNORMAL
)
```

## Configuration

```python
detector = IssueDetector(
    run_id='20260418_biweekly_01',
    config={
        'enable_duplicate_detection': True,
        'enable_hierarchy_change_detection': True,
        'severity_filter': None  # None = all severities
    }
)
```

## Statistics

```python
stats = detector.get_statistics()

# Total issue count
total = stats.total()

# Breakdown by type
by_type = stats.get_by_type()
# {'missing_field': 15, 'parse_failed': 3, 'unit_abnormal': 7}

# Breakdown by severity
by_severity = stats.get_by_severity()
# {'P1': 3, 'P2': 15, 'P3': 7}

# Breakdown by brand
by_brand = stats.get_by_brand()
# {'HIKVISION': 12, 'DAHUA': 13}
```

## Testing

Run unit tests:

```bash
PYTHONPATH=/path/to/project python tests/quality/test_issue_detector.py
```

Test coverage:
- Rule registry functionality
- Spec issue detection (missing, parse_failed, unit_abnormal)
- Duplicate model detection
- Hierarchy change detection
- Statistics tracking
- Filtering

## Integration with Pipeline

The quality detector is integrated into the DAG pipeline:

```python
# In src/pipeline/tasks_quality.py

def task_detect_data_quality_issues(context):
    """Detect data quality issues in extracted specs."""
    run_id = context['run_id']

    # Get data from previous tasks
    spec_records = fetch_spec_records(run_id)
    catalog_records = fetch_catalog_records(run_id)
    current_hierarchy = fetch_current_hierarchy(run_id)
    previous_hierarchy = fetch_previous_hierarchy(run_id)

    # Initialize detector
    detector = IssueDetector(run_id=run_id)

    # Detect all issues
    issues = detector.detect_spec_issues(spec_records)
    issues.extend(detector.detect_duplicate_models(spec_records))
    issues.extend(detector.detect_catalog_issues(catalog_records))
    issues.extend(detector.detect_hierarchy_changes(
        current_hierarchy,
        previous_hierarchy
    ))

    # Export to database
    export_issues_to_db(issues)

    # Log summary
    stats = detector.get_statistics()
    context['quality_stats'] = {
        'total_issues': stats.total(),
        'p1_count': stats.get_by_severity().get('P1', 0),
        'p2_count': stats.get_by_severity().get('P2', 0),
        'p3_count': stats.get_by_severity().get('P3', 0),
    }

    return context
```

## Performance Considerations

- **Batch Processing**: Spec issues are processed in batches of 1000 records
- **Indexing**: Ensure database indexes on (brand, series_l1, series_l2, model, field_code) for duplicate detection
- **Memory**: For large datasets, process in chunks and export incrementally
- **Hierarchy Comparison**: Uses set operations for O(n) complexity

## Future Enhancements

- Custom rule registration via YAML config
- Machine learning-based anomaly detection
- Automatic issue resolution suggestions
- Historical trend analysis
- Issue clustering and pattern recognition
