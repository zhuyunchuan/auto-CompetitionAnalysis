# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cloud-based web scraping system for competitor product parameter analysis, focused on Hikvision and Dahua network cameras. The system runs on OpenClaw (cloud scheduler) and periodically extracts product specifications from competitor websites, normalizes the data, and outputs structured Excel reports for manual analysis.

**Current Phase**: Phase 1 - Data collection and organization only (no cross-brand comparison or LLM analysis)

**Deployment**: Cloud server (OpenClaw), not local machine

**Repository**: https://github.com/zhuyunchuan/auto-CompetitionAnalysis

## Key Documentation

- **PRD**: `docs/PRD_v0.6.md` - Product requirements, data models, acceptance criteria
- **Technical Design**: `docs/技术方案_v0.1_云端竞品参数抓取系统.md` - Architecture, tech stack, implementation details

## Technology Stack

- **Language**: Python 3.11
- **Orchestration**: OpenClaw (cloud DAG scheduler)
- **Database**: PostgreSQL 14+
- **Scraping**: httpx + playwright (for dynamic pages)
- **Parsing**: lxml / beautifulsoup4
- **Data Processing**: pandas
- **Excel Export**: openpyxl
- **ORM**: sqlalchemy + psycopg2
- **Logging**: structlog or logging (JSON format)
- **Containerization**: Docker + Docker Compose (recommended)

## Planned Architecture

### DAG Pipeline (OpenClaw)

1. `discover_hierarchy` - Discover series/subseries from product pages
2. `crawl_product_catalog` - Fetch product catalog and detail URLs
3. `fetch_product_detail` - Scrape individual product pages
4. `extract_and_normalize_specs` - Extract and standardize specification fields
5. `detect_data_quality_issues` - Identify data quality problems
6. `merge_manual_inputs` - Incorporate manual corrections/appendments
7. `export_excel_report` - Generate Excel artifacts
8. `notify_run_summary` - Send execution summary

### Module Structure

```
src/
├── adapters/              # Site-specific adapters (hikvision_adapter.py, dahua_adapter.py)
├── pipeline/              # DAG task implementations
│   ├── discover_hierarchy.py
│   ├── crawl_catalog.py
│   ├── fetch_detail.py
│   ├── extract_specs.py
│   ├── normalize_specs.py
│   ├── detect_issues.py
│   ├── merge_manual.py
│   └── export_excel.py
├── core/                  # Shared utilities
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── logging.py
│   └── utils.py
└── mappings/              # Field mappings and normalization rules
    ├── field_alias.yaml
    └── unit_rules.yaml
```

### Data Model (Long Format)

All product specifications stored in long format (`product_specs_long` table):
- Key dimensions: `run_id`, `brand`, `series_l1`, `series_l2`, `product_model`, `field_code`
- Value fields: `raw_value`, `normalized_value`, `unit`, `is_manual_override`

### Hierarchy Model

Every product MUST have complete hierarchy path:
- `brand` → `series_l1` → `series_l2` → `product_model`

## Minimum Field Set (MVP)

12 core fields to extract from product pages:

1. `image_sensor`
2. `max_resolution`
3. `lens_type`
4. `aperture`
5. `supplement_light_type`
6. `supplement_light_range`
7. `main_stream_max_fps_resolution` (structured: `fps_value`, `resolution_width`, `resolution_height`)
8. `stream_count`
9. `interface_items` (multi-value)
10. `deep_learning_function_categories` (multi-value)
11. `approval_protection`
12. `approval_anti_corrosion_protection`

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (pytest)
pytest tests/

# Run single test
pytest tests/test_extract_hikvision.py::test_specific_field

# Database migrations (if using Alembic)
alembic upgrade head
alembic revision --autogenerate -m "description"

# Manual run of specific DAG task (OpenClaw CLI)
openclaw run discover_hierarchy --date 2026-04-18

# Export Excel for specific run
python -m src.pipeline.export_excel --run-id 20260418_biweekly_01
```

## Configuration

Configuration is managed through `config.yaml` at project root:

```yaml
schedule:
  mode: biweekly  # or monthly

brands:
  hikvision:
    enabled: true
    entry_url: "https://www.hikvision.com/en/products/..."
    series_l1_allowlist: ["Value", "Pro", "PT"]
  dahua:
    enabled: true
    entry_url: "https://www.dahuasecurity.com/products/..."
    series_keywords_allowlist: ["WizSense 2", "WizSense 3"]

crawler:
  concurrency: 4
  timeout_sec: 30
  retry_times: 3

storage:
  postgres_dsn: "postgresql://user:pass@host:5432/competitor"
  artifact_dir: "/data/artifacts"
  raw_snapshot_dir: "/data/raw_html"
```

## Key Design Principles

### 1. Hierarchy First
- Every product record must have complete `brand → series_l1 → series_l2 → product_model` path
- Series/subseries are **discovered dynamically** from pages, not hardcoded
- Hierarchy changes are tracked (`active` vs `disappeared` status)

### 2. Page as Source of Truth
- Series/subseries structure follows what's visible on the website
- No static dictionaries - always discover from live pages
- Missing hierarchy on page = issue to flag, not work around with defaults

### 3. Manual Override Priority
- Manual inputs always override scraped values (`is_manual_override = true`)
- All manual changes require audit trail (operator, reason, timestamp)
- Missing hierarchy info in manual input = reject with error

### 4. Long Format Storage
- Specifications stored in long format, not wide format
- Enables flexible field addition without schema changes
- Supports historical comparison and field-level statistics

### 5. Resilience Over Completeness
- Single product parse failure = log and continue, don't fail entire job
- Page structure change = alert and fall back to last known hierarchy
- Retry with exponential backoff (2s → 5s → 10s)

## Excel Output Structure

Each run generates `competitor_specs_<run_id>.xlsx` with sheets:

1. `hikvision_catalog` - Product inventory (brand, series, model, URL, status)
2. `hikvision_specs` - Specification details (long format)
3. `dahua_catalog` - Product inventory
4. `dahua_specs` - Specification details
5. `manual_append` - Template for manual corrections/additions
6. `data_quality_issues` - Quality problems with severity levels
7. `run_summary` - Execution metrics (counts, success rate, duration)

## Data Quality Issue Types

- **P1**: `parse_failed` - Critical field extraction failed
- **P2**: `missing_field`, `duplicate_model` - Missing data or duplicates
- **P3**: `unit_abnormal`, `hierarchy_changed` - Format or structure changes

## Compliance and Ethics

- Respect `robots.txt` and website terms of service
- Rate limiting: 3-5 concurrent requests, random jitter (300-1200ms)
- Only scrape public product information
- No privacy data collection
- Session management and UA rotation to avoid triggering anti-scraping

## Scheduling

- **Biweekly** - Default for regular monitoring
- **Monthly** - For management reporting
- **Manual** - For troubleshooting or re-runs after fixes

## Testing Strategy

1. **Unit tests** - Field extractors with fixed HTML samples
2. **Integration tests** - Small sample runs (2 series × 3 products per brand)
3. **Regression tests** - Re-run historical samples after parser updates to verify no degradation

## Important Constraints

### Out of Scope (Phase 1)
- ❌ Cross-brand product mapping (Hikvision ↔ Dahua)
- ❌ Automated competitive analysis conclusions
- ❌ LLM strategy summaries
- ❌ Frontend UI system (Excel + database only)

### Database Deduplication Key
Unique constraint on: `(brand, series_l1, series_l2, product_model, locale)`

## Run ID Format

Follows pattern: `YYYYMMDD_<schedule_type>_<sequence>`
Example: `20260418_biweekly_01`

## Common Workflows

### Adding a New Field to Extract

1. Add field mapping to `mappings/field_alias.yaml`
2. Update extraction logic in adapter
3. Add normalization rule if needed
4. Update tests with HTML sample
5. Verify in integration run

### Fixing Broken Page Selectors

1. Update selector in appropriate adapter (`src/adapters/*_adapter.py`)
2. Add version tag or comment with date
3. Run integration test on small sample
4. Monitor next scheduled run for anomalies

### Processing Manual Corrections

1. Fill `manual_append` sheet in exported Excel
2. Place in configured input directory
3. Run `merge_manual_inputs` DAG task
4. New export will include merged data
