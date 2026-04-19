"""
Excel export and run summary notification tasks for OpenClaw DAG.

This module implements two tasks:
1. export_excel_report - Generate Excel artifacts for manual review
2. notify_run_summary - Send execution summary notification

Task: export_excel_report
Dependencies: detect_data_quality_issues, merge_manual_inputs
Output: Excel file with catalog, specs, issues, and summary sheets

Task: notify_run_summary
Dependencies: export_excel_report
Output: Run completion notification
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from src.storage.repo_catalog import CatalogRepository
from src.storage.repo_specs import SpecRepository
from src.storage.repo_issues import IssueRepository
from src.storage.repo_run_summary import RunSummaryRepository
from src.export.excel_writer import ExcelWriter
from src.export.run_summary_writer import RunSummaryWriter
from src.storage.db import get_database
from src.core.logging import get_logger

logger = get_logger(__name__)


def export_excel_report(
    run_id: str,
    artifact_dir: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Export data to Excel file for manual review and analysis.

    This task generates an Excel workbook with multiple sheets containing
    catalog data, specifications, quality issues, manual input template,
    and run summary.

    Args:
        run_id: Unique run identifier
        artifact_dir: Directory to save Excel file (default: /data/artifacts)
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - excel_path: Path to generated Excel file
            - sheets: List of sheet names created
            - file_size_mb: File size in MB
            - duration_seconds: Task execution time

    Raises:
        Exception: If export fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting Excel export for run_id={run_id}")

    try:
        # Set default artifact directory
        if artifact_dir is None:
            artifact_dir = "/data/artifacts"

        # Create artifact directory if it doesn't exist
        Path(artifact_dir).mkdir(parents=True, exist_ok=True)

        # Initialize database
        db = get_database()
        with db.session() as session:
            catalog_repo = CatalogRepository(session)
            spec_repo = SpecRepository(session)
            issue_repo = IssueRepository(session)
            run_summary_repo = RunSummaryRepository(session)

            # Get data for export
            logger.info("Fetching data for Excel export")

            # 1. Get catalog data by brand
            hikvision_catalog = catalog_repo.get_by_brand(run_id, "HIKVISION")
            dahua_catalog = catalog_repo.get_by_brand(run_id, "DAHUA")

            # 2. Get spec data by brand
            hikvision_specs = spec_repo.get_specs_for_brand(run_id, "HIKVISION")
            dahua_specs = spec_repo.get_specs_for_brand(run_id, "DAHUA")

            # 3. Get quality issues
            all_issues = issue_repo.get_by_run_id(run_id)

            # 4. Get run summary
            run_summary = run_summary_repo.get_by_run_id(run_id)

            if not run_summary:
                raise Exception(f"Run summary not found for run_id={run_id}")

            # Initialize Excel writer
            excel_filename = f"competitor_specs_{run_id}.xlsx"
            excel_path = os.path.join(artifact_dir, excel_filename)

            logger.info(f"Generating Excel file: {excel_path}")

            # Create Excel workbook
            excel_writer = ExcelWriter(excel_path)

            # Write catalog sheets
            if hikvision_catalog:
                excel_writer.write_catalog_sheet(
                    sheet_name="hikvision_catalog",
                    catalog_data=hikvision_catalog
                )
                logger.info(f"Wrote {len(hikvision_catalog)} Hikvision catalog entries")

            if dahua_catalog:
                excel_writer.write_catalog_sheet(
                    sheet_name="dahua_catalog",
                    catalog_data=dahua_catalog
                )
                logger.info(f"Wrote {len(dahua_catalog)} Dahua catalog entries")

            # Write spec sheets
            if hikvision_specs:
                excel_writer.write_specs_sheet(
                    sheet_name="hikvision_specs",
                    spec_data=hikvision_specs
                )
                logger.info(f"Wrote {len(hikvision_specs)} Hikvision spec records")

            if dahua_specs:
                excel_writer.write_specs_sheet(
                    sheet_name="dahua_specs",
                    spec_data=dahua_specs
                )
                logger.info(f"Wrote {len(dahua_specs)} Dahua spec records")

            # Write issues sheet
            if all_issues:
                excel_writer.write_issues_sheet(
                    sheet_name="data_quality_issues",
                    issue_data=all_issues
                )
                logger.info(f"Wrote {len(all_issues)} quality issues")

            # Write manual append template sheet
            excel_writer.write_manual_template_sheet(
                sheet_name="manual_append"
            )
            logger.info("Wrote manual append template sheet")

            # Write run summary sheet
            run_summary_writer = RunSummaryWriter()
            run_summary_writer.write_summary_sheet(
                excel_writer=excel_writer,
                sheet_name="run_summary",
                run_summary=run_summary
            )
            logger.info("Wrote run summary sheet")

            # Save Excel file
            excel_writer.save()

            # Get file size
            file_size_mb = os.path.getsize(excel_path) / (1024 * 1024)

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'excel_path': excel_path,
                'sheets': excel_writer.get_sheet_names(),
                'file_size_mb': round(file_size_mb, 2),
                'duration_seconds': duration,
            }

            logger.info(
                f"Excel export completed: {excel_path} "
                f"({file_size_mb:.2f} MB, {len(result['sheets'])} sheets) "
                f"in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Excel export failed after {duration:.2f}s: {e}",
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
                    error_message=f"export_excel_report failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def notify_run_summary(
    run_id: str,
    notification_method: str = "log",
    **kwargs
) -> Dict[str, Any]:
    """
    Send execution summary notification and mark run as completed.

    This task generates a run execution summary and sends a notification
    via the configured method (log, email, webhook, etc.). It also updates
    the run status to 'completed'.

    Args:
        run_id: Unique run identifier
        notification_method: Method for sending notification (log, email, webhook)
        **kwargs: Additional task parameters (not used)

    Returns:
        Dictionary with task results:
            - status: 'success' or 'failed'
            - run_summary: Dictionary with run metrics
            - notification_sent: Whether notification was sent successfully
            - duration_seconds: Task execution time

    Raises:
        Exception: If notification fails catastrophically
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting run summary notification for run_id={run_id}")

    try:
        # Initialize database
        db = get_database()
        with db.session() as session:
            run_summary_repo = RunSummaryRepository(session)
            issue_repo = IssueRepository(session)

            # Get run summary
            run_summary = run_summary_repo.get_by_run_id(run_id)

            if not run_summary:
                raise Exception(f"Run summary not found for run_id={run_id}")

            # Get issue summary
            issue_summary = issue_repo.get_issue_summary(run_id)

            # Build summary dictionary
            summary = {
                'run_id': run_id,
                'schedule_type': run_summary.schedule_type,
                'status': run_summary.status,
                'started_at': run_summary.started_at.isoformat() if run_summary.started_at else None,
                'ended_at': run_summary.ended_at.isoformat() if run_summary.ended_at else None,
                'catalog_count': run_summary.catalog_count,
                'spec_field_count': run_summary.spec_field_count,
                'issue_count': run_summary.issue_count,
                'new_series_count': run_summary.new_series_count,
                'disappeared_series_count': run_summary.disappeared_series_count,
                'success_rate': run_summary.success_rate,
                'issue_summary': issue_summary,
            }

            # Calculate duration
            if run_summary.started_at and run_summary.ended_at:
                duration_seconds = (run_summary.ended_at - run_summary.started_at).total_seconds()
            else:
                duration_seconds = 0

            summary['duration_seconds'] = duration_seconds

            # Send notification
            notification_sent = False

            if notification_method == "log":
                # Log the summary
                logger.info(
                    f"Run Summary for {run_id}:",
                    extra={
                        'run_id': run_id,
                        'catalog_count': summary['catalog_count'],
                        'spec_count': summary['spec_field_count'],
                        'issue_count': summary['issue_count'],
                        'success_rate': summary['success_rate'],
                        'duration_seconds': duration_seconds,
                    }
                )

                # Log detailed summary
                logger.info(
                    f"  Schedule Type: {summary['schedule_type']}\n"
                    f"  Status: {summary['status']}\n"
                    f"  Products: {summary['catalog_count']}\n"
                    f"  Spec Fields: {summary['spec_field_count']}\n"
                    f"  Issues: {summary['issue_count']}\n"
                    f"  Success Rate: {summary['success_rate']:.2%}\n"
                    f"  New Series: {summary['new_series_count']}\n"
                    f"  Duration: {duration_seconds:.2f}s"
                )

                if issue_summary:
                    logger.info(
                        f"Issue Breakdown:\n"
                        f"  By Severity: {issue_summary['by_severity']}\n"
                        f"  By Type: {issue_summary['by_type']}\n"
                        f"  By Status: {issue_summary['by_status']}"
                    )

                notification_sent = True

            elif notification_method == "email":
                # TODO: Implement email notification
                logger.warning("Email notification not yet implemented")
                notification_sent = False

            elif notification_method == "webhook":
                # TODO: Implement webhook notification
                logger.warning("Webhook notification not yet implemented")
                notification_sent = False

            else:
                logger.warning(f"Unknown notification method: {notification_method}")
                notification_sent = False

            # Update run status to completed
            run_summary_repo.update_status(run_id, status='completed')

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'status': 'success',
                'run_summary': summary,
                'notification_sent': notification_sent,
                'duration_seconds': duration,
            }

            logger.info(
                f"Run summary notification completed in {duration:.2f}s"
            )

            return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Run summary notification failed after {duration:.2f}s: {e}",
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
                    error_message=f"notify_run_summary failed: {str(e)}"
                )
        except Exception as db_error:
            logger.error(f"Failed to update run summary status: {db_error}")

        raise


def get_run_report(
    run_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate a comprehensive run report.

    This is a helper function for generating detailed run reports.

    Args:
        run_id: Unique run identifier
        **kwargs: Additional task parameters

    Returns:
        Dictionary with comprehensive run report
    """
    logger.info(f"Generating run report for run_id={run_id}")

    # Initialize database
    db = get_database()
    with db.session() as session:
        run_summary_repo = RunSummaryRepository(session)
        catalog_repo = CatalogRepository(session)
        spec_repo = SpecRepository(session)
        issue_repo = IssueRepository(session)

        # Get all data
        run_summary = run_summary_repo.get_by_run_id(run_id)
        catalog_count_by_brand = {}
        spec_count_by_brand = {}
        issue_summary = issue_repo.get_issue_summary(run_id)

        # Get counts by brand
        for brand in ["HIKVISION", "DAHUA"]:
            catalog_count_by_brand[brand] = catalog_repo.count_by_brand(run_id, brand)
            spec_count_by_brand[brand] = len(spec_repo.get_specs_for_brand(run_id, brand))

        # Build report
        report = {
            'run_id': run_id,
            'run_summary': {
                'schedule_type': run_summary.schedule_type if run_summary else None,
                'status': run_summary.status if run_summary else None,
                'started_at': run_summary.started_at.isoformat() if run_summary and run_summary.started_at else None,
                'ended_at': run_summary.ended_at.isoformat() if run_summary and run_summary.ended_at else None,
                'catalog_count': run_summary.catalog_count if run_summary else 0,
                'spec_field_count': run_summary.spec_field_count if run_summary else 0,
                'issue_count': run_summary.issue_count if run_summary else 0,
                'success_rate': run_summary.success_rate if run_summary else 0.0,
            },
            'catalog_count_by_brand': catalog_count_by_brand,
            'spec_count_by_brand': spec_count_by_brand,
            'issue_summary': issue_summary,
        }

        logger.info(f"Generated run report for {run_id}")

        return report
