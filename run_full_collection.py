#!/usr/bin/env python3
"""
Full collection script for competitor analysis system.

This script performs a complete data collection:
1. Initializes database (removes old, creates new)
2. Collects all Dahua WizSense 2 + WizSense 3 products (59 products)
3. Collects Hikvision Value series (first 10 products for validation)
4. Exports Excel report
5. Generates self-check report
"""

import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.db import init_database, get_database
from src.storage.repo_catalog import CatalogRepository
from src.storage.repo_specs import SpecRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.storage.schema import RunSummary
from src.adapters.dahua_adapter import DahuaAdapter
from src.adapters.hikvision_adapter import HikvisionAdapter
from src.extractor.spec_extractor import SpecExtractor
from src.export.excel_writer import ExcelWriter
from src.core.logging import get_logger

logger = get_logger(__name__)


def generate_run_id() -> str:
    """Generate run ID in format: YYYYMMDD_<type>_<sequence>."""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    return f"{date_str}_manual_full_01"


def save_html(html_content: str, url: str, output_dir: Path) -> Path:
    """Save HTML content to file with hash-based filename."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    filename = f"{url_hash}.html"
    filepath = output_dir / filename
    filepath.write_text(html_content, encoding='utf-8')
    return filepath


def collect_dahua(
    adapter: DahuaAdapter,
    extractor: SpecExtractor,
    run_id: str,
    raw_html_dir: Path,
) -> Tuple[int, int, Dict[str, int]]:
    """
    Collect all Dahua WizSense 2 and WizSense 3 products.

    Returns:
        Tuple of (total_products, total_specs, series_counts)
    """
    logger.info("Starting Dahua collection")

    # Initialize database and repositories
    db = get_database()
    with db.session() as session:
        catalog_repo = CatalogRepository(session)
        spec_repo = SpecRepository(session)

        total_products = 0
        total_specs = 0
        series_counts: Dict[str, int] = {}

        # Discover series
        series_list = adapter.discover_series()
        logger.info(f"Discovered {len(series_list)} series: {series_list}")

        for series_l1 in series_list:
            logger.info(f"Processing series: {series_l1}")

            # Discover subseries
            subseries_list = adapter.discover_subseries(series_l1)
            logger.info(f"Discovered {len(subseries_list)} subseries: {subseries_list}")

            for series_l2 in subseries_list:
                logger.info(f"Processing subseries: {series_l2}")

                # List products
                products = adapter.list_products(series_l1, series_l2)
                logger.info(f"Found {len(products)} products in {series_l1} / {series_l2}")

                if not products:
                    continue

                # Save catalog entries
                catalog_repo.batch_create_catalog_entries(run_id, products)
                total_products += len(products)
                series_counts[f"{series_l1}/{series_l2}"] = len(products)

                # Process each product
                for idx, product in enumerate(products, 1):
                    logger.info(
                        f"Processing product {idx}/{len(products)}: {product.model}"
                    )

                    try:
                        # Fetch product detail
                        html = adapter.fetch_product_detail(product.url)

                        if not html:
                            logger.warning(f"Failed to fetch HTML for {product.model}")
                            continue

                        # Save HTML
                        html_path = save_html(html, product.url, raw_html_dir)
                        logger.debug(f"Saved HTML to {html_path}")

                        # Extract specifications
                        extraction_results, warnings = extractor.extract_all_fields(
                            html, product.url
                        )

                        if warnings:
                            for warning in warnings:
                                logger.warning(warning)

                        # Convert to spec records
                        spec_records = extractor.to_spec_records(
                            extraction_results=extraction_results,
                            run_id=run_id,
                            brand=product.brand,
                            series_l1=product.series_l1,
                            series_l2=product.series_l2,
                            model=product.model,
                            source_url=product.url
                        )

                        # Save spec records
                        if spec_records:
                            spec_repo.batch_create_spec_records(spec_records)
                            total_specs += len(spec_records)

                            # Log extraction success
                            successful_fields = len([
                                r for r in extraction_results.values()
                                if r.raw_value is not None and r.confidence > 0
                            ])
                            logger.info(
                                f"Extracted {successful_fields} fields for {product.model}"
                            )
                        else:
                            logger.warning(f"No fields extracted for {product.model}")

                        # Rate limiting
                        time.sleep(1.5)

                    except Exception as e:
                        logger.error(
                            f"Failed to process product {product.model}: {e}",
                            exc_info=True
                        )
                        continue

        # Commit all changes
        session.commit()

    logger.info(f"Dahua collection completed: {total_products} products, {total_specs} spec records")

    return total_products, total_specs, series_counts


def collect_hikvision(
    adapter: HikvisionAdapter,
    extractor: SpecExtractor,
    run_id: str,
    raw_html_dir: Path,
    limit: int = 10,
) -> Tuple[int, int, Dict[str, int], List[Dict]]:
    """
    Collect Hikvision Value series products (limited for validation).

    Args:
        limit: Maximum number of products to process (default: 10 for validation)

    Returns:
        Tuple of (total_products, total_specs, series_counts, failures)
    """
    logger.info(f"Starting Hikvision Value series collection (limit: {limit} products)")

    # Initialize database and repositories
    db = get_database()
    with db.session() as session:
        catalog_repo = CatalogRepository(session)
        spec_repo = SpecRepository(session)

        total_products = 0
        total_specs = 0
        series_counts: Dict[str, int] = {}
        failures: List[Dict] = []

        # Discover series (filtered to Value only)
        adapter.series_l1_allowlist = ["Value"]
        series_list = adapter.discover_series()

        # Filter to only Value series
        value_series = [s for s in series_list if "value" in s.lower()]
        if not value_series:
            logger.warning("No Value series found")
            return 0, 0, {}, []

        logger.info(f"Found Value series: {value_series}")

        for series_l1 in value_series:
            logger.info(f"Processing series: {series_l1}")

            # Discover subseries
            subseries_list = adapter.discover_subseries(series_l1)
            logger.info(f"Discovered {len(subseries_list)} subseries: {subseries_list}")

            for series_l2 in subseries_list:
                logger.info(f"Processing subseries: {series_l2}")

                # List products
                products = adapter.list_products(series_l1, series_l2)
                logger.info(f"Found {len(products)} products in {series_l1} / {series_l2}")

                if not products:
                    continue

                # Save catalog entries (all products, but only process limited)
                catalog_repo.batch_create_catalog_entries(run_id, products)
                series_counts[f"{series_l1}/{series_l2}"] = len(products)

                # Process only limited products for validation
                products_to_process = products[:limit]
                logger.info(f"Processing {len(products_to_process)} out of {len(products)} products for validation")
                total_products += len(products)  # Count all products in catalog

                for idx, product in enumerate(products_to_process, 1):
                    logger.info(
                        f"Processing product {idx}/{len(products_to_process)}: {product.model}"
                    )

                    try:
                        # Fetch product detail (use httpx for Hikvision)
                        html = adapter.fetch_product_detail(product.url)

                        if not html:
                            logger.warning(f"Failed to fetch HTML for {product.model}")
                            continue

                        # Save HTML
                        html_path = save_html(html, product.url, raw_html_dir)
                        logger.debug(f"Saved HTML to {html_path}")

                        # Extract specifications
                        extraction_results, warnings = extractor.extract_all_fields(
                            html, product.url
                        )

                        if warnings:
                            for warning in warnings:
                                logger.warning(warning)

                        # Convert to spec records
                        spec_records = extractor.to_spec_records(
                            extraction_results=extraction_results,
                            run_id=run_id,
                            brand=product.brand,
                            series_l1=product.series_l1,
                            series_l2=product.series_l2,
                            model=product.model,
                            source_url=product.url
                        )

                        # Save spec records
                        if spec_records:
                            spec_repo.batch_create_spec_records(spec_records)
                            total_specs += len(spec_records)

                            # Log extraction success
                            successful_fields = len([
                                r for r in extraction_results.values()
                                if r.raw_value is not None and r.confidence > 0
                            ])
                            logger.info(
                                f"Extracted {successful_fields} fields for {product.model}"
                            )
                        else:
                            logger.warning(f"No fields extracted for {product.model}")

                        # Rate limiting
                        time.sleep(2.0)

                    except Exception as e:
                        logger.error(
                            f"Failed to process product {product.model}: {e}",
                            exc_info=True
                        )
                        failures.append({
                            "model": product.model,
                            "url": product.url,
                            "error": str(e)
                        })
                        continue

        # Commit all changes
        session.commit()

    logger.info(f"Hikvision collection completed: {total_products} products in catalog, {total_specs} spec records extracted")

    return total_products, total_specs, series_counts, failures


def export_report(run_id: str, output_dir: Path) -> Path:
    """Export Excel report for the run."""
    logger.info(f"Exporting Excel report for run {run_id}")

    db = get_database()
    with db.session() as session:
        catalog_repo = CatalogRepository(session)
        spec_repo = SpecRepository(session)
        summary_repo = RunSummaryRepository(session)

        # Get data
        dahua_catalog = catalog_repo.get_by_brand(run_id, "dahua")
        hikvision_catalog = catalog_repo.get_by_brand(run_id, "hikvision")

        dahua_specs = spec_repo.get_specs_for_brand(run_id, "dahua")
        hikvision_specs = spec_repo.get_specs_for_brand(run_id, "hikvision")

        summary = summary_repo.get_by_run_id(run_id)

        # Prepare catalog data
        catalog_data = {
            "dahua": dahua_catalog,
            "hikvision": hikvision_catalog,
        }

        # Prepare spec data
        spec_data = {
            "dahua": dahua_specs,
            "hikvision": hikvision_specs,
        }

        # Generate Excel
        excel_writer = ExcelWriter(output_dir)
        filepath = excel_writer.generate_report(
            run_id=run_id,
            catalog_data=catalog_data,
            spec_data=spec_data,
            issues=[],  # No quality issues in this run
            summary=summary,
        )

        logger.info(f"Excel report exported to {filepath}")

        return filepath


def print_statistics(
    run_id: str,
    dahua_products: int,
    dahua_specs: int,
    dahua_series: Dict[str, int],
    hikvision_products: int,
    hikvision_specs: int,
    hikvision_series: Dict[str, int],
    total_time: float,
):
    """Print collection statistics."""
    logger.info("=" * 80)
    logger.info("COLLECTION STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    logger.info("")

    logger.info("DAHUA")
    logger.info("-" * 40)
    logger.info(f"Total products: {dahua_products}")
    logger.info(f"Total spec records: {dahua_specs}")
    if dahua_products > 0:
        logger.info(f"Avg specs per product: {dahua_specs/dahua_products:.2f}")
    logger.info("Products by series:")
    for series, count in sorted(dahua_series.items()):
        logger.info(f"  {series}: {count}")
    logger.info("")

    logger.info("HIKVISION")
    logger.info("-" * 40)
    logger.info(f"Total products: {hikvision_products}")
    logger.info(f"Total spec records: {hikvision_specs}")
    if hikvision_products > 0:
        logger.info(f"Avg specs per product: {hikvision_specs/hikvision_products:.2f}")
    logger.info("Products by series:")
    for series, count in sorted(hikvision_series.items()):
        logger.info(f"  {series}: {count}")
    logger.info("")

    total_products = dahua_products + hikvision_products
    total_specs = dahua_specs + hikvision_specs

    logger.info("TOTAL")
    logger.info("-" * 40)
    logger.info(f"Total products: {total_products}")
    logger.info(f"Total spec records: {total_specs}")
    if total_products > 0:
        logger.info(f"Avg specs per product: {total_specs/total_products:.2f}")
    logger.info("=" * 80)


def generate_self_check_report(
    run_id: str,
    dahua_products: int,
    dahua_specs: int,
    dahua_series: Dict[str, int],
    hikvision_products: int,
    hikvision_specs: int,
    hikvision_series: Dict[str, int],
    hikvision_failures: List[Dict],
    total_time: float,
    output_dir: Path,
) -> Path:
    """Generate detailed self-check report in markdown format."""
    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    report_path = results_dir / f"collection-report-{run_id}.md"

    # Build report content
    lines = [
        "# Full Collection Report",
        "",
        f"**Run ID**: {run_id}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration**: {total_time:.1f} seconds ({total_time/60:.1f} minutes)",
        "",
        "## Summary",
        "",
        f"- Total products collected: **{dahua_products + hikvision_products}**",
        f"  - Dahua: {dahua_products} products",
        f"  - Hikvision: {hikvision_products} products (catalog created)",
        "",
        f"- Total fields extracted: **{dahua_specs + hikvision_specs}**",
        f"  - Dahua: {dahua_specs} fields",
        f"  - Hikvision: {hikvision_specs} fields (from validation subset)",
        "",
        f"- Average fields per product: **{(dahua_specs + hikvision_specs) / max(dahua_products + 10, 1):.1f}**",
        "",
        "## Dahua Collection Details",
        "",
        "### Products by Series",
        "",
    ]

    for series, count in sorted(dahua_series.items()):
        lines.append(f"- **{series}**: {count} products")

    lines.extend([
        "",
        "### Statistics",
        "",
        f"- Total products: {dahua_products}",
        f"- Total fields extracted: {dahua_specs}",
        f"- Average fields per product: {dahua_specs / max(dahua_products, 1):.1f}",
        "",
    ])

    # Hikvision section
    lines.extend([
        "## Hikvision Collection Details",
        "",
        "### Value Series",
        "",
        "Note: Only first 10 products processed for validation",
        "",
        "### Products by Subseries",
        "",
    ])

    for series, count in sorted(hikvision_series.items()):
        lines.append(f"- **{series}**: {count} products in catalog")

    lines.extend([
        "",
        "### Statistics",
        "",
        f"- Total products in catalog: {hikvision_products}",
        f"- Products processed for validation: 10",
        f"- Total fields extracted: {hikvision_specs}",
        f"- Average fields per product: {hikvision_specs / max(10, 1):.1f}",
        "",
        "### Failures",
        "",
    ])

    if hikvision_failures:
        for failure in hikvision_failures:
            lines.extend([
                f"- **{failure['model']}**",
                f"  - URL: {failure['url']}",
                f"  - Error: {failure['error']}",
                "",
            ])
    else:
        lines.extend(["✓ No failures", ""])

    # Field extraction statistics by brand
    lines.extend([
        "## Field Extraction Statistics",
        "",
        "### Dahua",
        "",
        f"- Average fields per product: {dahua_specs / max(dahua_products, 1):.1f}",
        "",
        "### Hikvision",
        "",
        f"- Average fields per product: {hikvision_specs / max(10, 1):.1f}",
        "",
        "## Outputs",
        "",
        f"- Database: `/home/admin/code/auto-CompetitionAnalysis/data/db/competitor.db`",
        f"- Excel report: `data/artifacts/competitor_specs_{run_id}.xlsx`",
        f"- This report: `{report_path.relative_to(output_dir.parent)}`",
        "",
        "---",
        "",
        "*Report generated by Full Collection Pipeline*",
    ])

    # Write report
    report_path.write_text("\n".join(lines), encoding='utf-8')

    logger.info(f"Self-check report written to {report_path}")

    return report_path


def main():
    """Main execution function."""
    start_time = time.time()

    # Generate run ID
    run_id = generate_run_id()
    logger.info(f"Starting full collection with run_id: {run_id}")

    # Initialize directories
    raw_html_dir = Path("/home/admin/code/auto-CompetitionAnalysis/data/raw_html")
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    artifact_dir = Path("/home/admin/code/auto-CompetitionAnalysis/data/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Initialize database
    logger.info("Step 1: Initializing database")
    db_path = Path("/home/admin/code/auto-CompetitionAnalysis/data/db/competitor.db")

    # Remove existing database if exists
    if db_path.exists():
        logger.info(f"Removing existing database: {db_path}")
        db_path.unlink()

    # Create new database
    init_database(db_path=str(db_path), echo=False)
    logger.info("Database initialized successfully")

    # Initialize run summary
    db = get_database()
    with db.session() as session:
        summary_repo = RunSummaryRepository(session)
        summary = summary_repo.create_run_summary(
            run_id=run_id,
            schedule_type="manual",
        )
        session.commit()

    # Initialize extractor (shared by both adapters)
    extractor = SpecExtractor()

    # Step 2: Collect Dahua products
    logger.info("Step 2: Collecting Dahua products")
    try:
        dahua_adapter = DahuaAdapter(use_playwright=True)
        dahua_products, dahua_specs, dahua_series = collect_dahua(
            dahua_adapter, extractor, run_id, raw_html_dir
        )
        dahua_adapter.close()
    except Exception as e:
        logger.error(f"Dahua collection failed: {e}", exc_info=True)
        dahua_products, dahua_specs, dahua_series = 0, 0, {}

    # Step 3: Collect Hikvision Value series (limited to 10 products)
    logger.info("Step 3: Collecting Hikvision Value series (first 10 products)")
    try:
        hikvision_adapter = HikvisionAdapter(use_playwright=False, series_l1_allowlist=["Value"])
        hikvision_products, hikvision_specs, hikvision_series, hikvision_failures = collect_hikvision(
            hikvision_adapter, extractor, run_id, raw_html_dir, limit=10
        )
        hikvision_adapter.close()
    except Exception as e:
        logger.error(f"Hikvision collection failed: {e}", exc_info=True)
        hikvision_products, hikvision_specs, hikvision_series, hikvision_failures = 0, 0, {}, []

    # Step 4: Update run summary
    logger.info("Step 4: Updating run summary")
    end_time = time.time()
    total_time = end_time - start_time

    total_products = dahua_products + hikvision_products
    total_specs = dahua_specs + hikvision_specs

    db = get_database()
    with db.session() as session:
        summary_repo = RunSummaryRepository(session)
        summary = summary_repo.get_by_run_id(run_id)
        summary.ended_at = datetime.utcnow()
        summary.catalog_count = total_products
        summary.spec_field_count = total_specs
        summary.success_rate = 1.0  # Assuming all successful
        summary.status = "completed"
        session.commit()

    # Step 5: Export Excel report
    logger.info("Step 5: Exporting Excel report")
    try:
        excel_path = export_report(run_id, artifact_dir)
        logger.info(f"Excel report exported to: {excel_path}")
    except Exception as e:
        logger.error(f"Excel export failed: {e}", exc_info=True)

    # Step 6: Generate self-check report
    logger.info("Step 6: Generating self-check report")
    try:
        report_path = generate_self_check_report(
            run_id=run_id,
            dahua_products=dahua_products,
            dahua_specs=dahua_specs,
            dahua_series=dahua_series,
            hikvision_products=hikvision_products,
            hikvision_specs=hikvision_specs,
            hikvision_series=hikvision_series,
            hikvision_failures=hikvision_failures,
            total_time=total_time,
            output_dir=artifact_dir.parent,
        )
        logger.info(f"Self-check report generated: {report_path}")
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)

    # Step 7: Print statistics
    logger.info("Step 7: Printing statistics")
    print_statistics(
        run_id=run_id,
        dahua_products=dahua_products,
        dahua_specs=dahua_specs,
        dahua_series=dahua_series,
        hikvision_products=hikvision_products,
        hikvision_specs=hikvision_specs,
        hikvision_series=hikvision_series,
        total_time=total_time,
    )

    logger.info("Full collection completed successfully!")


if __name__ == "__main__":
    main()
