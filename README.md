# Competitor Product Scraping System

A cloud-based web scraping system for competitor product parameter analysis, focused on Hikvision and Dahua network cameras. The system runs on OpenClaw (cloud scheduler) and periodically extracts product specifications from competitor websites, normalizes the data, and outputs structured Excel reports for manual analysis.

## Current Phase

**Phase 1**: Data collection and organization only (no cross-brand comparison or LLM analysis)

## Technology Stack

- **Language**: Python 3.11
- **Orchestration**: OpenClaw (cloud DAG scheduler)
- **Database**: SQLite 3 (default) + Parquet (batch snapshots)
- **Scraping**: httpx + playwright (for dynamic pages)
- **Parsing**: lxml / beautifulsoup4
- **Data Processing**: pandas
- **Excel Export**: openpyxl
- **ORM**: sqlalchemy

## Project Structure

```
src/
├── core/                  # Shared infrastructure
│   ├── config.py
│   ├── logging.py
│   ├── constants.py
│   └── types.py           # Frozen data structures
├── storage/               # Data layer (SQLite + Parquet)
│   ├── db.py
│   ├── schema.py          # Frozen DB schema
│   ├── repo_hierarchy.py
│   ├── repo_catalog.py
│   ├── repo_specs.py
│   ├── repo_issues.py
│   └── parquet_store.py
├── adapters/              # Site-specific adapters
│   ├── base_adapter.py    # Common interface
│   ├── hikvision_adapter.py
│   └── dahua_adapter.py
├── crawler/               # HTTP & page fetching
│   ├── http_client.py
│   ├── page_fetcher.py
│   ├── hierarchy_discovery.py
│   ├── catalog_collector.py
│   └── detail_collector.py
├── extractor/             # Field extraction & normalization
│   ├── field_registry.py
│   ├── spec_extractor.py
│   ├── normalizer.py
│   └── parsers/
│       ├── resolution_parser.py
│       ├── stream_parser.py
│       └── range_parser.py
├── quality/               # Data quality rules
│   ├── issue_rules.py
│   └── issue_detector.py
├── pipeline/              # OpenClaw DAG tasks
│   ├── tasks_discover.py
│   ├── tasks_collect.py
│   ├── tasks_extract.py
│   ├── tasks_quality.py
│   ├── tasks_merge_manual.py
│   ├── tasks_export.py
│   └── dag.py
├── export/                # Excel & reporting
│   ├── excel_writer.py
│   └── run_summary_writer.py
├── manual/                # Manual input handling
│   ├── manual_importer.py
│   └── override_service.py
└── mappings/              # Field mappings and normalization rules
    ├── field_alias.yaml
    └── unit_rules.yaml
```

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for dynamic page fallback)
playwright install chromium

# Initialize database
python -c "from src.storage.db import init_database; init_database()"
```

## Configuration

Edit `config.yaml` to customize:
- Schedule settings (biweekly/monthly)
- Brand enablement and allowlists
- Crawler timeouts and rate limits
- Storage paths
- Quality detection rules
- Export settings

## Running the Pipeline

### Manual Execution

```python
from src.pipeline import run_manual_pipeline
from datetime import datetime

# Run pipeline manually
run_id = "20260418_manual_01"
result = run_manual_pipeline(
    run_id=run_id,
    brands=["hikvision", "dahua"],
    schedule_type="manual"
)
```

### OpenClaw Scheduled Execution

```python
from src.pipeline import register_dag

# Register DAG with OpenClaw
dag = create_competitor_scraping_dag()
register_dag(dag)
```

## DAG Pipeline

The system follows this linear task chain:

```
initialize_run → discover_hierarchy → crawl_product_catalog →
fetch_product_detail → extract_and_normalize_specs →
merge_manual_inputs → detect_data_quality_issues →
export_excel_report → notify_run_summary
```

## Excel Output

Each run generates `competitor_specs_<run_id>.xlsx` with sheets:

1. **hikvision_catalog** - Product inventory (brand, series, model, URL, status)
2. **hikvision_specs** - Specification details (long format)
3. **dahua_catalog** - Product inventory
4. **dahua_specs** - Specification details
5. **manual_append** - Template for manual corrections
6. **data_quality_issues** - Quality problems with severity levels
7. **run_summary** - Execution metrics (counts, success rate, duration)

## Minimum Field Set (Phase 1)

12 core fields extracted from product pages:

1. `image_sensor`
2. `max_resolution`
3. `lens_type`
4. `aperture`
5. `supplement_light_type`
6. `supplement_light_range`
7. `main_stream_max_fps_resolution`
8. `stream_count`
9. `interface_items`
10. `deep_learning_function_categories`
11. `approval_protection`
12. `approval_anti_corrosion_protection`

## Manual Corrections

1. Open exported Excel file
2. Fill in `manual_append` sheet with corrections
3. Place in configured input directory
4. Run `merge_manual_inputs` DAG task
5. New export will include merged data

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_hikvision_adapter.py

# Run with coverage
pytest --cov=src tests/
```

## Documentation

- **PRD**: `docs/PRD_v0.7_竞品参数抓取与整理.md`
- **Technical Design**: `docs/技术方案_v0.2_云端竞品参数抓取系统.md`
- **Parallel Development**: `docs/整体技术设计_v0.2_并行开发拆分.md`
- **Field Dictionary**: `docs/field_dictionary_v1.md`

## Key Design Principles

1. **Hierarchy First**: Every product must have complete `brand → series_l1 → series_l2 → product_model` path
2. **Page as Source of Truth**: Series/subseries structure follows what's visible on the website
3. **Manual Override Priority**: Manual inputs always override scraped values
4. **Long Format Storage**: Specifications stored in long format for flexibility
5. **Resilience Over Completeness**: Single product parse failure = log and continue

## Compliance

- Respects `robots.txt` and website terms of service
- Rate limiting: 3-5 concurrent requests with random jitter (300-1200ms)
- Only scrapes public product information
- No privacy data collection

## License

[Your License Here]

## Contributing

[Your Contribution Guidelines Here]
