"""
Specification extraction and normalization task for OpenClaw DAG.

This module implements the extract_and_normalize_specs task which extracts
product specification fields from HTML pages and normalizes them.

Task: extract_and_normalize_specs
Dependencies: fetch_product_detail
Output: Product specifications stored in database (long format)
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List

from src.storage.repo_catalog import CatalogRepository
from src.storage.repo_specs import SpecRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.extractor.spec_extractor import SpecExtractor
from src.extractor.normalizer import Normalizer
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def extract_and_normalize_specs(
    run_id: str,
    snapshot_dir: str = None,
    batch_size: int = 100,
    **kwargs
) -> Dict[str, Any]:
    """
    Extract and normalize product specifications from HTML pages.

    This task reads HTML snapshots, extracts specification fields using
    the SpecExtractor, normalizes values using the Normalizer, and stores
    results in the product_specs_long table.

    Args:
        run_id: Unique run identifier
        snapshot_dir: Directory containing HTML snapshots (default: /data/raw_html/{run_id})
        batch_size: Number of records to batch for database inserts
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - products_processed: Number of products processed
            - specs_extracted: Total number of spec records extracted
            - avg_specs_per_product: Average specs per product
            - extraction_failures: Number of products with extraction failures
            - duration_seconds: Task execution time

    Raises:
        Exception: If extraction fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting spec extraction for run_id={run_id}")

    try:
        # Set default snapshot directory
        if snapshot_dir is None:
            base_dir = os.getenv('RAW_SNAPSHOT_DIR', '/data/raw_html')
            snapshot_dir = f"{base_dir}/{run_id}"

        # Initialize database
        db = get_database()
        with db.session() as session:
            catalog_repo = CatalogRepository(session)
            spec_repo = SpecRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Get catalog items
            catalog_items = catalog_repo.get_by_run_id(run_id)
            if not catalog_items:
                raise Exception(f"No catalog items found for run_id={run_id}")

            logger.info(f"Processing {len(catalog_items)} products")

            # Initialize extractor and normalizer
            extractor = SpecExtractor()
            normalizer = Normalizer()

            # Process each product
            all_spec_records = []
            extraction_failures = 0
            processed_count = 0

            for catalog_item in catalog_items:
                try:
                    # Read HTML snapshot
                    filename = catalog_item.product_url.replace('/', '_').replace(':', '_')
                    filepath = os.path.join(snapshot_dir, f"{filename}.html")

                    if not os.path.exists(filepath):
                        logger.warning(
                            f"HTML snapshot not found for {catalog_item.product_model}: {filepath}"
                        )
                        extraction_failures += 1
                        continue

                    with open(filepath, 'r', encoding='utf-8') as f:
                        html_content = f.read()

                    # Extract all fields
                    extraction_results, warnings = extractor.extract_all_fields(
                        html_content,
                        source_url=catalog_item.product_url
                    )

                    # Log warnings
                    for warning in warnings:
                        logger.warning(f"Extraction warning for {catalog_item.product_model}: {warning}")

                    # Create spec records
                    from src.core.types import SpecRecord

                    for field_code, extraction_result in extraction_results.items():
                        if extraction_result.raw_value is None:
                            # Skip failed extractions
                            continue

                        # Normalize the value
                        normalized_value, unit, issues = normalizer.normalize(
                            field_code=field_code,
                            raw_value=extraction_result.raw_value
                        )

                        # Create spec record
                        spec_record = SpecRecord(
                            run_id=run_id,
                            brand=catalog_item.brand,
                            series_l1=catalog_item.series_l1 or "",
                            series_l2=catalog_item.series_l2 or "",
                            model=catalog_item.product_model,
                            field_code=field_code,
                            raw_value=extraction_result.raw_value,
                            normalized_value=normalized_value,
                            unit=unit,
                            source_url=catalog_item.product_url,
                            confidence=extraction_result.confidence
                        )

                        all_spec_records.append(spec_record)

                        # Log normalization issues
                        if issues:
                            logger.debug(
                                f"Normalization issues for {catalog_item.product_model}/{field_code}: {issues}"
                            )

                    processed_count += 1

                    # Log progress periodically
                    if processed_count % 50 == 0:
                        logger.info(
                            f"Processed {processed_count}/{len(catalog_items)} products, "
                            f"{len(all_spec_records)} specs extracted so far"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to extract specs for {catalog_item.product_model}: {e}",
                        exc_info=True
                    )
                    extraction_failures += 1
                    continue

            # Store in database in batches
            logger.info(f"Storing {len(all_spec_records)} spec records in database")
            stored_count = spec_repo.batch_create_spec_records(
                all_spec_records,
                batch_size=batch_size
            )

            # Calculate statistics
            avg_specs = stored_count / processed_count if processed_count > 0 else 0

            # Update run summary
            run_summary_repo.update_spec_stats(
                run_id=run_id,
                spec_field_count=stored_count
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'products_processed': processed_count,
                'specs_extracted': stored_count,
                'avg_specs_per_product': round(avg_specs, 2),
                'extraction_failures': extraction_failures,
                'duration_seconds': duration,
            }

            logger.info(
                f"Spec extraction completed: "
                f"{stored_count} specs from {processed_count} products "
                f"({avg_specs:.2f} avg per product) in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Spec extraction failed after {duration:.2f}s: {e}",
            exc_info=True
        )

        # Update run summary with failure status
        try:
            db = get_database()
            with db.session() as session:
                run_summary_repo = RunSummaryRepository(session)
                run_summary_repo.update_status(
                    run_id=run_id,
                    status='failed',
                    error_message=f"extract_and_normalize_specs failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def reextract_product(
    run_id: str,
    product_model: str,
    snapshot_dir: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Re-extract specifications for a single product.

    This is a helper function for manual re-extraction of a specific product.

    Args:
        run_id: Unique run identifier
        product_model: Product model to re-extract
        snapshot_dir: Directory containing HTML snapshots
        **kwargs: Additional task parameters

    Returns:
        Dictionary with re-extraction results
    """
    logger.info(f"Re-extracting specs for {product_model} in run_id={run_id}")

    # Initialize database
    db = get_database()
    with db.session() as session:
        catalog_repo = CatalogRepository(session)
        spec_repo = SpecRepository(session)

        # Get catalog item
        catalog_item = catalog_repo.get_by_model(run_id, product_model)
        if not catalog_item:
            raise ValueError(f"Product {product_model} not found in run {run_id}")

        # Set default snapshot directory
        if snapshot_dir is None:
            base_dir = os.getenv('RAW_SNAPSHOT_DIR', '/data/raw_html')
            snapshot_dir = f"{base_dir}/{run_id}"

        # Read HTML snapshot
        filename = catalog_item.product_url.replace('/', '_').replace(':', '_')
        filepath = os.path.join(snapshot_dir, f"{filename}.html")

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"HTML snapshot not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Initialize extractor and normalizer
        extractor = SpecExtractor()
        normalizer = Normalizer()

        # Extract all fields
        extraction_results, warnings = extractor.extract_all_fields(
            html_content,
            source_url=catalog_item.product_url
        )

        # Delete existing specs for this product
        from src.storage.schema import ProductSpecLong
        deleted_count = session.query(ProductSpecLong).filter(
            ProductSpecLong.run_id == run_id,
            ProductSpecLong.product_model == product_model
        ).delete()

        logger.info(f"Deleted {deleted_count} existing spec records for {product_model}")

        # Create and store new spec records
        from src.core.types import SpecRecord
        all_spec_records = []

        for field_code, extraction_result in extraction_results.items():
            if extraction_result.raw_value is None:
                continue

            normalized_value, unit, issues = normalizer.normalize(
                field_code=field_code,
                raw_value=extraction_result.raw_value
            )

            spec_record = SpecRecord(
                run_id=run_id,
                brand=catalog_item.brand,
                series_l1=catalog_item.series_l1 or "",
                series_l2=catalog_item.series_l2 or "",
                model=catalog_item.product_model,
                field_code=field_code,
                raw_value=extraction_result.raw_value,
                normalized_value=normalized_value,
                unit=unit,
                source_url=catalog_item.product_url,
                confidence=extraction_result.confidence
            )

            all_spec_records.append(spec_record)

        # Store in database
        stored_count = spec_repo.batch_create_spec_records(all_spec_records)

        logger.info(f"Re-extracted {stored_count} spec records for {product_model}")

        return {
            'status': 'success',
            'product_model': product_model,
            'specs_extracted': stored_count,
            'warnings': warnings,
        }
