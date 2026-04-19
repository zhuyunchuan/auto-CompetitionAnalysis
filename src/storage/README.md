# Storage Layer Documentation

## Overview

The storage layer provides complete data access functionality for the competitor scraping system using SQLite for structured data and Parquet for batch snapshots.

## Architecture

```
src/storage/
├── db.py                    # Database connection and session management
├── schema.py                # SQLAlchemy ORM models (frozen contract)
├── repo_hierarchy.py        # Hierarchy snapshot repository
├── repo_catalog.py          # Product catalog repository
├── repo_specs.py            # Specification records repository
├── repo_issues.py           # Data quality issues repository
├── parquet_store.py         # Parquet batch storage
└── __init__.py              # Package initialization
```

## Components

### 1. Database Connection (`db.py`)

**Key Classes:**
- `Database` - Manages SQLite engine and sessions
- `get_database()` - Global database instance getter
- `init_database()` - Initialize database with schema
- `get_session()` - Context manager for sessions

**Features:**
- SQLAlchemy with SQLite backend
- Thread-safe session management
- Connection pooling with StaticPool
- Automatic transaction management (commit on success, rollback on error)
- Environment variable support via `DB_PATH`

**Usage:**
```python
from src.storage.db import get_database, get_session

# Initialize database
db = get_database()
db.init_db()

# Use session context manager
with get_session() as session:
    # All database operations
    session.commit()  # Automatic on success
```

### 2. Hierarchy Repository (`repo_hierarchy.py`)

**Key Methods:**
- `create_snapshot()` - Create single hierarchy record
- `batch_create_snapshots()` - Bulk insert with batching
- `get_by_run_id()` - Get all hierarchies for a run
- `get_by_brand()` - Filter by brand
- `get_series_l1()` - Get unique series level 1
- `get_series_l2()` - Get unique series level 2
- `compare_with_previous_run()` - Identify new/disappeared series
- `get_latest_run_id()` - Get most recent run

**Data Model:**
- Stores: `run_id`, `brand`, `series_l1`, `series_l2`, `source`, `status`
- Tracks: Hierarchy changes over time
- Supports: Brand and series filtering

### 3. Catalog Repository (`repo_catalog.py`)

**Key Methods:**
- `create_catalog_entry()` - Create single product entry
- `batch_create_catalog_entries()` - Bulk insert products
- `get_by_run_id()` - Get all products for a run
- `get_by_brand()` - Filter by brand
- `get_by_series()` - Filter by series hierarchy
- `get_by_model()` - Get specific product
- `check_duplicate_model()` - Check for duplicates
- `find_duplicates_in_run()` - Find all duplicate models
- `update_last_seen()` - Update product lifecycle timestamps
- `mark_discontinued()` - Mark old products as discontinued

**Data Model:**
- Stores: `run_id`, `brand`, `series_l1`, `series_l2`, `model`, `name`, `url`, `locale`
- Lifecycle: `first_seen_at`, `last_seen_at`, `catalog_status`
- Supports: Product lifecycle tracking

### 4. Specification Repository (`repo_specs.py`)

**Key Methods:**
- `create_spec_record()` - Create single spec record
- `batch_create_spec_records()` - Bulk insert specs
- `get_by_run_id()` - Get all specs for a run
- `get_by_product()` - Get all specs for a product
- `get_by_field()` - Get all values for a field
- `get_spec_value()` - Get specific field value for product
- `get_missing_fields()` - Identify missing required fields
- `upsert_spec_record()` - Insert or update
- `get_manual_overrides()` - Get manually overridden values
- `get_low_confidence_specs()` - Get low confidence extractions
- `get_field_statistics()` - Calculate field coverage stats

**Data Model:**
- Stores: `run_id`, `brand`, `series`, `model`, `field_code`, `raw_value`, `normalized_value`, `unit`, `value_type`, `confidence`, `is_manual_override`
- Long format: One row per field per product
- Supports: Manual overrides and confidence tracking

### 5. Issues Repository (`repo_issues.py`)

**Key Methods:**
- `create_issue()` - Create single quality issue
- `batch_create_issues()` - Bulk insert issues
- `get_by_run_id()` - Get all issues for a run
- `get_by_severity()` - Filter by severity (P1, P2, P3)
- `get_by_status()` - Filter by status
- `get_by_issue_type()` - Filter by issue type
- `get_by_product()` - Get issues for a product
- `get_by_owner()` - Get issues assigned to owner
- `get_open_issues()` - Get open issues with optional severity filter
- `update_status()` - Update issue status
- `batch_update_status()` - Bulk update status
- `assign_owner()` - Assign issue to owner
- `get_issue_summary()` - Get statistics by severity/type/status
- `get_critical_issues()` - Get all P1 issues

**Data Model:**
- Stores: `run_id`, `brand`, `series`, `model`, `issue_type`, `field_code`, `detail`, `severity`, `status`, `owner`
- Supports: Issue tracking and workflow management

### 6. Parquet Store (`parquet_store.py`)

**Key Methods:**
- `write_catalog()` - Write catalog data to Parquet
- `write_specs()` - Write spec data to Parquet
- `write_hierarchy()` - Write hierarchy data to Parquet
- `write_issues()` - Write issues to Parquet
- `read_catalog()` - Read catalog from Parquet
- `read_specs()` - Read specs from Parquet
- `read_hierarchy()` - Read hierarchy from Parquet
- `read_issues()` - Read issues from Parquet
- `list_runs()` - List all available run IDs
- `read_multiple_runs()` - Concatenate multiple runs
- `delete_run()` - Delete all data for a run
- `get_storage_stats()` - Get storage statistics

**Features:**
- Columnar storage with PyArrow
- Partitioned by `year=` and `month=` for efficient querying
- Snappy compression for space efficiency
- Optimized for analytical workloads
- Supports historical comparisons

**Storage Layout:**
```
/data/parquet/
├── catalog/
│   └── year=2026/
│       └── month=04/
│           └── 20260418_biweekly_01.parquet
├── specs/
│   └── year=2026/
│       └── month=04/
│           └── 20260418_biweekly_01.parquet
├── hierarchy/
│   └── year=2026/
│       └── month=04/
│           └── 20260418_biweekly_01.parquet
└── issues/
    └── year=2026/
        └── month=04/
            └── 20260418_biweekly_01.parquet
```

## Design Patterns

### Repository Pattern
Each repository class encapsulates data access logic for a specific table:
- Single responsibility principle
- Easy to test and mock
- Consistent interface

### Context Managers
All database operations use context managers:
- Automatic transaction management
- Proper resource cleanup
- Error handling with rollback

### Batch Operations
All repositories support batch operations:
- `batch_create_*()` methods with configurable batch_size
- Efficient bulk inserts
- Reduced database round-trips

### Global Instances
Singleton pattern for database and Parquet store:
- `get_database()` - Global database instance
- `get_parquet_store()` - Global Parquet store instance
- Environment variable configuration

## Type Safety

All repositories use frozen data types from `src/core/types.py`:
- `HierarchyNode` - For hierarchy operations
- `CatalogItem` - For catalog operations
- `SpecRecord` - For specification operations
- `QualityIssue` - For quality issues

This ensures data consistency across the system.

## Error Handling

All repositories include:
- Proper logging with structured context
- Exception handling in context managers
- Automatic rollback on errors
- Debug-level logging for operations

## Performance Considerations

### SQLite Optimizations
- StaticPool for connection management
- `check_same_thread=False` for multi-threaded access
- 30-second timeout for locks
- Indexes on commonly queried columns

### Batch Operations
- Default batch size of 100 records
- Configurable per operation
- Reduces transaction overhead

### Parquet Optimizations
- Columnar storage for analytical queries
- Partitioning by date for efficient filtering
- Snappy compression for reduced I/O
- Pandas integration for easy data manipulation

## Configuration

### Environment Variables
- `DB_PATH` - Path to SQLite database (default: `/data/db/competitor.db`)
- `PARQUET_DIR` - Path to Parquet storage (default: `/data/parquet`)

### Database Initialization
```python
from src.storage.db import init_database

# Initialize with defaults
db = init_database()

# Initialize with custom path
db = init_database(db_path="/custom/path/competitor.db")

# Initialize with SQL echo (for debugging)
db = init_database(echo=True)
```

## Usage Examples

### Creating Hierarchy Snapshots
```python
from src.storage.db import get_session
from src.storage.repo_hierarchy import HierarchyRepository
from src.core.types import HierarchyNode

with get_session() as session:
    repo = HierarchyRepository(session)

    # Single record
    node = HierarchyNode(
        brand="HIKVISION",
        series_l1="Value Series",
        series_l2="Bullet Cameras",
        source="catalog",
        status="active"
    )
    repo.create_snapshot(run_id="20260418_biweekly_01", node=node)

    # Batch insert
    nodes = [node1, node2, node3, ...]
    repo.batch_create_snapshots(
        run_id="20260418_biweekly_01",
        nodes=nodes,
        batch_size=100
    )
```

### Creating Product Catalog
```python
from src.storage.db import get_session
from src.storage.repo_catalog import CatalogRepository
from src.core.types import CatalogItem

with get_session() as session:
    repo = CatalogRepository(session)

    # Batch insert products
    items = [
        CatalogItem(
            brand="HIKVISION",
            series_l1="Value Series",
            series_l2="Bullet Cameras",
            model="DS-2CD2x47G2-L",
            name="4MP Outdoor Bullet Camera",
            url="https://...",
            locale="en"
        ),
        # ... more items
    ]

    repo.batch_create_catalog_entries(
        run_id="20260418_biweekly_01",
        items=items,
        batch_size=100
    )
```

### Creating Specification Records
```python
from src.storage.db import get_session
from src.storage.repo_specs import SpecRepository
from src.core.types import SpecRecord

with get_session() as session:
    repo = SpecRepository(session)

    # Batch insert specs
    records = [
        SpecRecord(
            run_id="20260418_biweekly_01",
            brand="HIKVISION",
            series_l1="Value Series",
            series_l2="Bullet Cameras",
            model="DS-2CD2x47G2-L",
            field_code="max_resolution",
            raw_value="2688×1520",
            normalized_value="2688x1520",
            unit="px",
            source_url="https://...",
            confidence=0.95
        ),
        # ... more records
    ]

    repo.batch_create_spec_records(
        records=records,
        batch_size=100
    )
```

### Creating Quality Issues
```python
from src.storage.db import get_session
from src.storage.repo_issues import IssueRepository
from src.core.types import QualityIssue

with get_session() as session:
    repo = IssueRepository(session)

    # Create issue
    issue = QualityIssue(
        run_id="20260418_biweekly_01",
        brand="HIKVISION",
        series_l1="Value Series",
        series_l2="Bullet Cameras",
        model="DS-2CD2x47G2-L",
        issue_type="missing_field",
        field_code="image_sensor",
        detail="Required field not extracted",
        severity="P2"
    )

    repo.create_issue(issue, owner="data-team")
```

### Using Parquet Store
```python
from src.storage.parquet_store import get_parquet_store

store = get_parquet_store()

# Write catalog data
catalog_data = [
    {
        "run_id": "20260418_biweekly_01",
        "brand": "HIKVISION",
        "series_l1": "Value Series",
        "series_l2": "Bullet Cameras",
        "product_model": "DS-2CD2x47G2-L",
        # ... more fields
    },
    # ... more records
]

store.write_catalog(
    run_id="20260418_biweekly_01",
    data=catalog_data
)

# Read catalog data
df = store.read_catalog(run_id="20260418_biweekly_01")

# List all runs
runs = store.list_runs(table_name="catalog")

# Read multiple runs
df = store.read_multiple_runs(
    table_name="catalog",
    run_ids=["20260418_biweekly_01", "20260404_biweekly_01"]
)

# Get storage stats
stats = store.get_storage_stats()
print(f"Total storage: {stats['total_size_bytes']} bytes")
```

## Testing

All repositories should be tested with:
1. Unit tests for individual methods
2. Integration tests with real database
3. Performance tests for batch operations
4. Transaction rollback tests

## Dependencies

Required Python packages:
- `sqlalchemy` - ORM and database toolkit
- `pyarrow` - Parquet file support
- `pandas` - Data manipulation for Parquet operations

## Migration Path

When upgrading from SQLite to PostgreSQL:
1. Update connection string in `db.py`
2. Replace StaticPool with appropriate PostgreSQL pool
3. Update column types if needed (e.g., Text -> VARCHAR)
4. Repository interfaces remain unchanged
5. Parquet storage layer is database-agnostic

## Statistics

- **Total Files:** 7 Python files
- **Total Lines of Code:** ~3,000 lines
- **Repository Classes:** 5
- **Key Methods:** 80+
- **Database Tables:** 5
- **Storage Formats:** SQLite + Parquet
