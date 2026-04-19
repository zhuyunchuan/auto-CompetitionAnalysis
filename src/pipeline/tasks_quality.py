"""
Data quality detection task for OpenClaw DAG.

This module implements the detect_data_quality_issues task which scans
specification data and identifies quality problems according to defined rules.

Task: detect_data_quality_issues
Dependencies: extract_and_normalize_specs
Output: Quality issues stored in database
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.storage.repo_specs import SpecRepository
from src.storage.repo_catalog import CatalogRepository
from src.storage.repo_hierarchy import HierarchyRepository
from src.storage.repo_issues import IssueRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.quality.issue_detector import IssueDetector
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def detect_data_quality_issues(
    run_id: str,
    config: dict = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Detect data quality issues in specifications and catalog data.

    This task runs quality checks on extracted specifications and catalog data,
    identifying problems like missing fields, parse failures, duplicates, and
    hierarchy changes. Results are stored in the data_quality_issues table.

    Args:
        run_id: Unique run identifier
        config: Optional configuration dict for detection parameters
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - total_issues: Total number of issues detected
            - p1_issues: Number of P1 (critical) issues
            - p2_issues: Number of P2 (high) issues
            - p3_issues: Number of P3 (medium) issues
            - by_type: Issue counts by type
            - duration_seconds: Task execution time

    Raises:
        Exception: If quality detection fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting quality issue detection for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            spec_repo = SpecRepository(session)
            catalog_repo = CatalogRepository(session)
            hierarchy_repo = HierarchyRepository(session)
            issue_repo = IssueRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Initialize detector
            detector = IssueDetector(run_id=run_id, config=config)

            all_issues = []

            # 1. Detect spec issues
            logger.info("Detecting specification issues")
            spec_records = spec_repo.get_by_run_id(run_id)

            # Convert to dict format for detector
            spec_dicts = [
                {
                    'brand': spec.brand,
                    'series_l1': spec.series_l1,
                    'series_l2': spec.series_l2,
                    'model': spec.product_model,
                    'field_code': spec.field_code,
                    'raw_value': spec.raw_value,
                    'normalized_value': spec.normalized_value,
                    'unit': spec.unit,
                    'extract_confidence': spec.extract_confidence,
                }
                for spec in spec_records
            ]

            spec_issues = detector.detect_spec_issues(spec_dicts)
            all_issues.extend(spec_issues)
            logger.info(f"Detected {len(spec_issues)} specification issues")

            # 2. Detect duplicate models
            logger.info("Detecting duplicate models")
            duplicate_issues = detector.detect_duplicate_models(spec_dicts)
            all_issues.extend(duplicate_issues)
            logger.info(f"Detected {len(duplicate_issues)} duplicate model issues")

            # 3. Detect catalog issues
            logger.info("Detecting catalog issues")
            catalog_records = catalog_repo.get_by_run_id(run_id)

            # Convert to dict format for detector
            catalog_dicts = [
                {
                    'brand': item.brand,
                    'series_l1': item.series_l1,
                    'series_l2': item.series_l2,
                    'model': item.product_model,
                    'url': item.product_url,
                }
                for item in catalog_records
            ]

            catalog_issues = detector.detect_catalog_issues(catalog_dicts)
            all_issues.extend(catalog_issues)
            logger.info(f"Detected {len(catalog_issues)} catalog issues")

            # 4. Detect hierarchy changes (compare with previous run)
            logger.info("Detecting hierarchy changes")
            current_hierarchy = hierarchy_repo.get_by_run_id(run_id)

            # Get previous run_id for this brand
            previous_run_id = hierarchy_repo.get_latest_run_id()
            if previous_run_id and previous_run_id != run_id:
                previous_hierarchy = hierarchy_repo.get_by_run_id(previous_run_id)

                # Convert to dict format
                current_hierarchy_dicts = [
                    {
                        'brand': node.brand,
                        'series_l1': node.series_l1,
                        'series_l2': node.series_l2,
                    }
                    for node in current_hierarchy
                ]

                previous_hierarchy_dicts = [
                    {
                        'brand': node.brand,
                        'series_l1': node.series_l1,
                        'series_l2': node.series_l2,
                    }
                    for node in previous_hierarchy
                ]

                hierarchy_issues = detector.detect_hierarchy_changes(
                    current_hierarchy_dicts,
                    previous_hierarchy_dicts
                )
                all_issues.extend(hierarchy_issues)
                logger.info(f"Detected {len(hierarchy_issues)} hierarchy change issues")
            else:
                logger.info("No previous run found, skipping hierarchy change detection")

            # 5. Store issues in database
            if all_issues:
                logger.info(f"Storing {len(all_issues)} quality issues in database")
                stored_count = issue_repo.batch_create_issues(all_issues)
            else:
                logger.info("No quality issues detected")
                stored_count = 0

            # 6. Get statistics
            stats = detector.get_statistics()
            issue_summary = issue_repo.get_issue_summary(run_id)

            # 7. Update run summary
            run_summary_repo.update_quality_stats(
                run_id=run_id,
                issue_count=stored_count
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'total_issues': stored_count,
                'p1_issues': issue_summary['by_severity'].get('P1', 0),
                'p2_issues': issue_summary['by_severity'].get('P2', 0),
                'p3_issues': issue_summary['by_severity'].get('P3', 0),
                'by_type': issue_summary['by_type'],
                'by_severity': issue_summary['by_severity'],
                'duration_seconds': duration,
            }

            logger.info(
                f"Quality detection completed: "
                f"{stored_count} issues "
                f"(P1: {result['p1_issues']}, "
                f"P2: {result['p2_issues']}, "
                f"P3: {result['p3_issues']}) "
                f"in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Quality detection failed after {duration:.2f}s: {e}",
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
                    error_message=f"detect_data_quality_issues failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def get_quality_report(
    run_id: str,
    severity: Optional[str] = None,
    issue_type: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate a quality report for a specific run.

    This is a helper function for generating quality reports with filtering.

    Args:
        run_id: Unique run identifier
        severity: Optional severity filter (P1, P2, P3)
        issue_type: Optional issue type filter
        **kwargs: Additional task parameters

    Returns:
        Dictionary with quality report
    """
    logger.info(f"Generating quality report for run_id={run_id}")

    # Initialize database
    db = get_database()
    with db.session() as session:
        issue_repo = IssueRepository(session)

        # Get issues
        if severity:
            issues = issue_repo.get_by_severity(run_id, severity)
        elif issue_type:
            issues = issue_repo.get_by_issue_type(run_id, issue_type)
        else:
            issues = issue_repo.get_by_run_id(run_id)

        # Get summary
        summary = issue_repo.get_issue_summary(run_id)

        # Convert issues to dicts
        issue_dicts = [
            {
                'id': issue.id,
                'brand': issue.brand,
                'series_l1': issue.series_l1,
                'series_l2': issue.series_l2,
                'product_model': issue.product_model,
                'issue_type': issue.issue_type,
                'field_code': issue.field_code,
                'detail': issue.issue_detail,
                'severity': issue.severity,
                'status': issue.status,
                'owner': issue.owner,
                'created_at': issue.created_at.isoformat() if issue.created_at else None,
            }
            for issue in issues
        ]

        logger.info(f"Generated report with {len(issue_dicts)} issues")

        return {
            'run_id': run_id,
            'summary': summary,
            'issues': issue_dicts,
            'filter': {
                'severity': severity,
                'issue_type': issue_type,
            }
        }
