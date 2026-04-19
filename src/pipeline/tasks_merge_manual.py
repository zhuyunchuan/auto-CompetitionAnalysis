"""
Manual input merge task for OpenClaw DAG.

This module implements the merge_manual_inputs task which merges human-provided
corrections and additions with extracted specification data.

Task: merge_manual_inputs
Dependencies: extract_and_normalize_specs
Output: Merged specifications with manual overrides applied
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from uuid import uuid4

from src.storage.repo_specs import SpecRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.storage.schema import ManualInput
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def merge_manual_inputs(
    run_id: str,
    manual_input_dir: str = None,
    operator: str = "system",
    **kwargs
) -> Dict[str, Any]:
    """
    Merge manual corrections and additions with extracted specifications.

    This task reads manual inputs (corrections and new products) and merges
    them with the extracted specification data. Manual values always override
    extracted values. All merges are tracked with audit trail.

    Args:
        run_id: Unique run identifier
        manual_input_dir: Directory containing manual input files (optional)
        operator: Name of the person/system performing the merge
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - manual_inputs_count: Number of manual inputs processed
            - overrides_applied: Number of specification overrides applied
            - new_products_added: Number of new products added
            - duration_seconds: Task execution time

    Raises:
        Exception: If merge fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting manual input merge for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            spec_repo = SpecRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Get manual inputs from database
            # (Manual inputs are loaded to database by a separate import process)
            manual_inputs = session.query(ManualInput).all()

            if not manual_inputs:
                logger.info("No manual inputs found to merge")
                return {
                    'status': 'success',
                    'manual_inputs_count': 0,
                    'overrides_applied': 0,
                    'new_products_added': 0,
                    'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
                }

            logger.info(f"Processing {len(manual_inputs)} manual inputs")

            # Process each manual input
            overrides_applied = 0
            new_products_added = 0
            import_errors = 0

            for manual_input in manual_inputs:
                try:
                    # Validate that manual input has complete hierarchy
                    if not manual_input.brand or not manual_input.series_l1:
                        logger.error(
                            f"Manual input {manual_input.input_id} missing required hierarchy "
                            f"(brand: {manual_input.brand}, series_l1: {manual_input.series_l1}). "
                            f"Skipping."
                        )
                        import_errors += 1
                        continue

                    # Check if this is a new product or an override
                    existing_spec = spec_repo.get_spec_value(
                        run_id=run_id,
                        model=manual_input.product_model,
                        field_code=manual_input.field_code
                    )

                    if existing_spec:
                        # Override existing specification
                        # Update the spec record with manual value
                        existing_spec.raw_value = manual_input.manual_value
                        existing_spec.normalized_value = manual_input.manual_value  # Assume manual is already normalized
                        existing_spec.is_manual_override = True
                        existing_spec.extract_confidence = 1.0  # Manual override has highest confidence

                        overrides_applied += 1
                        logger.debug(
                            f"Applied manual override for {manual_input.product_model}/{manual_input.field_code}"
                        )
                    else:
                        # This is a new product or new field for existing product
                        # Create a new spec record
                        from src.storage.schema import ProductSpecLong

                        new_spec = ProductSpecLong(
                            run_id=run_id,
                            brand=manual_input.brand,
                            series_l1=manual_input.series_l1,
                            series_l2=manual_input.series_l2,
                            product_model=manual_input.product_model or "MANUAL_INPUT",
                            field_code=manual_input.field_code,
                            field_name=manual_input.field_code,
                            raw_value=manual_input.manual_value,
                            normalized_value=manual_input.manual_value,
                            unit=None,  # Manual input should include unit in value if needed
                            value_type="string",
                            source_url="MANUAL_INPUT",
                            extract_confidence=1.0,
                            is_manual_override=True,
                            updated_at=datetime.utcnow(),
                        )

                        session.add(new_spec)
                        new_products_added += 1
                        logger.debug(
                            f"Added new manual spec for {manual_input.product_model}/{manual_input.field_code}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to process manual input {manual_input.input_id}: {e}",
                        exc_info=True
                    )
                    import_errors += 1
                    continue

            # Commit all changes
            session.commit()

            if import_errors > 0:
                logger.warning(f"Failed to import {import_errors} manual inputs")

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'manual_inputs_count': len(manual_inputs),
                'overrides_applied': overrides_applied,
                'new_products_added': new_products_added,
                'import_errors': import_errors,
                'duration_seconds': duration,
            }

            logger.info(
                f"Manual input merge completed: "
                f"{overrides_applied} overrides, {new_products_added} new specs "
                f"in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Manual input merge failed after {duration:.2f}s: {e}",
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
                    error_message=f"merge_manual_inputs failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def add_manual_override(
    run_id: str,
    brand: str,
    series_l1: str,
    series_l2: str,
    product_model: str,
    field_code: str,
    manual_value: str,
    operator: str,
    reason: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Add a single manual override to the database.

    This is a helper function for adding manual corrections programmatically.

    Args:
        run_id: Unique run identifier
        brand: Brand name
        series_l1: Series level 1
        series_l2: Series level 2
        product_model: Product model number
        field_code: Field code to override
        manual_value: Manual value to set
        operator: Name of the person making the change
        reason: Reason for the change
        **kwargs: Additional task parameters

    Returns:
        Dictionary with result
    """
    logger.info(
        f"Adding manual override for {product_model}/{field_code} "
        f"by {operator}: {reason}"
    )

    # Initialize database
    db = get_database()
    with db.session() as session:
        # Create manual input record
        manual_input = ManualInput(
            input_id=str(uuid4()),
            brand=brand,
            series_l1=series_l1,
            series_l2=series_l2,
            product_model=product_model,
            field_code=field_code,
            manual_value=manual_value,
            operator=operator,
            reason=reason,
            created_at=datetime.utcnow(),
        )

        session.add(manual_input)
        session.commit()

        logger.info(f"Created manual input {manual_input.input_id}")

        return {
            'status': 'success',
            'input_id': manual_input.input_id,
            'product_model': product_model,
            'field_code': field_code,
            'manual_value': manual_value,
        }


def batch_add_manual_overrides(
    run_id: str,
    overrides: List[Dict[str, Any]],
    operator: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Add multiple manual overrides to the database.

    This is a helper function for batch import of manual corrections.

    Args:
        run_id: Unique run identifier
        overrides: List of override dicts with keys:
            - brand, series_l1, series_l2, product_model, field_code, manual_value, reason
        operator: Name of the person making the changes
        **kwargs: Additional task parameters

    Returns:
        Dictionary with batch result
    """
    logger.info(f"Batch adding {len(overrides)} manual overrides by {operator}")

    # Initialize database
    db = get_database()
    with db.session() as session:
        input_ids = []

        for override in overrides:
            try:
                # Validate required fields
                if not all(k in override for k in ['brand', 'series_l1', 'field_code', 'manual_value', 'reason']):
                    logger.error(f"Override missing required fields: {override}")
                    continue

                # Create manual input record
                manual_input = ManualInput(
                    input_id=str(uuid4()),
                    brand=override['brand'],
                    series_l1=override['series_l1'],
                    series_l2=override.get('series_l2'),
                    product_model=override.get('product_model'),
                    field_code=override['field_code'],
                    manual_value=override['manual_value'],
                    operator=operator,
                    reason=override['reason'],
                    created_at=datetime.utcnow(),
                )

                session.add(manual_input)
                input_ids.append(manual_input.input_id)

            except Exception as e:
                logger.error(f"Failed to create override: {e}")
                continue

        session.commit()

        logger.info(f"Created {len(input_ids)} manual input records")

        return {
            'status': 'success',
            'input_count': len(input_ids),
            'input_ids': input_ids,
        }
