"""
Main DAG definition for competitor scraping system.

This module defines the OpenClaw DAG that orchestrates the entire data pipeline
from hierarchy discovery to Excel export and run summary notification.

DAG Structure:
    discover_hierarchy → crawl_product_catalog → fetch_product_detail →
    extract_and_normalize_specs → merge_manual_inputs →
    detect_data_quality_issues → export_excel_report → notify_run_summary

Usage:
    # Register DAG with OpenClaw
    from src.pipeline.dag import create_competitor_scraping_dag
    dag = create_competitor_scraping_dag()
    dag.register()
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.pipeline.tasks_discover import discover_hierarchy
from src.pipeline.tasks_collect import crawl_product_catalog, fetch_product_detail
from src.pipeline.tasks_extract import extract_and_normalize_specs
from src.pipeline.tasks_merge_manual import merge_manual_inputs
from src.pipeline.tasks_quality import detect_data_quality_issues
from src.pipeline.tasks_export import export_excel_report, notify_run_summary
from src.storage.repo_run_summary import RunSummaryRepository
from src.storage.db import get_database, init_database
from src.core.logging import get_logger

logger = get_logger(__name__)

# Default DAG configuration
DEFAULT_SCHEDULE = "0 2 * * 1,15"  # Biweekly: 2 AM on Monday every 2 weeks
DEFAULT_RETRY_DELAYS = [300, 900, 1800]  # 5min, 15min, 30min
DEFAULT_TIMEOUT_SECONDS = 7200  # 2 hours
DEFAULT_MAX_WORKERS = 5


def create_competitor_scraping_dag(
    dag_id: str = "competitor_scraping_dag",
    schedule: str = DEFAULT_SCHEDULE,
    adapters: Optional[List] = None,
    config: Optional[Dict[str, Any]] = None,
) -> 'DAG':
    """
    Create the competitor scraping DAG.

    This function creates and configures the main DAG for the competitor
    scraping system with all task dependencies.

    Args:
        dag_id: Unique DAG identifier
        schedule: Cron schedule expression
        adapters: List of brand adapter instances (HikvisionAdapter, DahuaAdapter)
        config: Optional configuration dict with task parameters

    Returns:
        Configured DAG instance

    Example:
        >>> from src.adapters.hikvision_adapter import HikvisionAdapter
        >>> from src.adapters.dahua_adapter import DahuaAdapter
        >>>
        >>> adapters = [HikvisionAdapter(), DahuaAdapter()]
        >>> dag = create_competitor_scraping_dag(adapters=adapters)
        >>> dag.register()
    """
    # Import here to avoid circular dependencies
    try:
        # Try OpenClaw DAG import
        from openclaw import DAG as OpenClawDAG, task
    except ImportError:
        # Fallback to mock DAG for testing
        logger.warning("OpenClaw not available, using mock DAG")
        from unittest.mock import MagicMock
        OpenClawDAG = MagicMock
        task = lambda **kwargs: lambda func: func

    # Merge default config with user config
    dag_config = {
        'max_workers': DEFAULT_MAX_WORKERS,
        'quality_detection': {
            'enable_duplicate_detection': True,
            'enable_hierarchy_change_detection': True,
        },
    }
    if config:
        dag_config.update(config)

    # Create DAG instance
    dag = OpenClawDAG(
        dag_id=dag_id,
        schedule=schedule,
        description=(
            "Competitor product scraping pipeline for Hikvision and Dahua. "
            "Discovers hierarchies, crawls catalogs, extracts specs, detects issues, "
            "and exports Excel reports."
        ),
        default_args={
            'owner': 'data-team',
            'retries': 3,
            'retry_delays': DEFAULT_RETRY_DELAYS,
            'timeout_seconds': DEFAULT_TIMEOUT_SECONDS,
        },
    )

    # ========================================================================
    # Task 1: Initialize Run
    # ========================================================================

    @task(dag=dag, name="initialize_run")
    def initialize_run(**context) -> Dict[str, Any]:
        """
        Initialize a new run by creating run summary record.

        This task runs first and sets up the run_id and other metadata
        that will be passed to all subsequent tasks.

        Args:
            **context: Task context provided by OpenClaw

        Returns:
            Dictionary with run initialization results
        """
        # Generate run_id from current date and schedule type
        execution_date = context.get('execution_date', datetime.utcnow())
        schedule_type = context.get('schedule_type', 'biweekly')

        # Format: YYYYMMDD_<schedule_type>_NN
        date_str = execution_date.strftime('%Y%m%d')
        sequence = context.get('run_sequence', 1)
        run_id = f"{date_str}_{schedule_type}_{sequence:02d}"

        logger.info(f"Initializing run: {run_id}")

        # Initialize database
        init_database()

        # Create run summary
        db = get_database()
        with db.session() as session:
            run_summary_repo = RunSummaryRepository(session)
            run_summary_repo.create_run_summary(
                run_id=run_id,
                schedule_type=schedule_type
            )

        logger.info(f"Run {run_id} initialized successfully")

        return {
            'run_id': run_id,
            'schedule_type': schedule_type,
            'execution_date': execution_date.isoformat(),
        }

    # ========================================================================
    # Task 2: Discover Hierarchy
    # ========================================================================

    @task(dag=dag, name="discover_hierarchy")
    def task_discover_hierarchy(
        run_init_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Discover product hierarchies from competitor websites.

        Args:
            run_init_result: Output from initialize_run task
            **context: Task context

        Returns:
            Dictionary with hierarchy discovery results
        """
        run_id = run_init_result['run_id']

        if adapters is None:
            raise ValueError("Brand adapters must be provided to create DAG")

        return discover_hierarchy(
            run_id=run_id,
            adapters=adapters
        )

    # ========================================================================
    # Task 3: Crawl Product Catalog
    # ========================================================================

    @task(dag=dag, name="crawl_product_catalog")
    def task_crawl_product_catalog(
        run_init_result: Dict[str, Any],
        hierarchy_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Crawl product catalogs for discovered hierarchies.

        Args:
            run_init_result: Output from initialize_run task
            hierarchy_result: Output from discover_hierarchy task
            **context: Task context

        Returns:
            Dictionary with catalog crawl results
        """
        run_id = run_init_result['run_id']

        if adapters is None:
            raise ValueError("Brand adapters must be provided to create DAG")

        return crawl_product_catalog(
            run_id=run_id,
            adapters=adapters
        )

    # ========================================================================
    # Task 4: Fetch Product Detail
    # ========================================================================

    @task(dag=dag, name="fetch_product_detail")
    def task_fetch_product_detail(
        run_init_result: Dict[str, Any],
        catalog_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Fetch product detail pages for all catalog items.

        Args:
            run_init_result: Output from initialize_run task
            catalog_result: Output from crawl_product_catalog task
            **context: Task context

        Returns:
            Dictionary with detail fetch results
        """
        run_id = run_init_result['run_id']

        if adapters is None:
            raise ValueError("Brand adapters must be provided to create DAG")

        return fetch_product_detail(
            run_id=run_id,
            adapters=adapters,
            max_workers=dag_config['max_workers']
        )

    # ========================================================================
    # Task 5: Extract and Normalize Specs
    # ========================================================================

    @task(dag=dag, name="extract_and_normalize_specs")
    def task_extract_and_normalize_specs(
        run_init_result: Dict[str, Any],
        detail_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Extract and normalize product specifications from HTML pages.

        Args:
            run_init_result: Output from initialize_run task
            detail_result: Output from fetch_product_detail task
            **context: Task context

        Returns:
            Dictionary with extraction results
        """
        run_id = run_init_result['run_id']

        return extract_and_normalize_specs(
            run_id=run_id
        )

    # ========================================================================
    # Task 6: Merge Manual Inputs
    # ========================================================================

    @task(dag=dag, name="merge_manual_inputs")
    def task_merge_manual_inputs(
        run_init_result: Dict[str, Any],
        extract_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Merge manual corrections with extracted specifications.

        Args:
            run_init_result: Output from initialize_run task
            extract_result: Output from extract_and_normalize_specs task
            **context: Task context

        Returns:
            Dictionary with merge results
        """
        run_id = run_init_result['run_id']

        return merge_manual_inputs(
            run_id=run_id
        )

    # ========================================================================
    # Task 7: Detect Data Quality Issues
    # ========================================================================

    @task(dag=dag, name="detect_data_quality_issues")
    def task_detect_data_quality_issues(
        run_init_result: Dict[str, Any],
        merge_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Detect data quality issues in specifications and catalog data.

        Args:
            run_init_result: Output from initialize_run task
            merge_result: Output from merge_manual_inputs task
            **context: Task context

        Returns:
            Dictionary with quality detection results
        """
        run_id = run_init_result['run_id']

        return detect_data_quality_issues(
            run_id=run_id,
            config=dag_config.get('quality_detection')
        )

    # ========================================================================
    # Task 8: Export Excel Report
    # ========================================================================

    @task(dag=dag, name="export_excel_report")
    def task_export_excel_report(
        run_init_result: Dict[str, Any],
        quality_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Export data to Excel file for manual review.

        Args:
            run_init_result: Output from initialize_run task
            quality_result: Output from detect_data_quality_issues task
            **context: Task context

        Returns:
            Dictionary with export results
        """
        run_id = run_init_result['run_id']

        return export_excel_report(
            run_id=run_id
        )

    # ========================================================================
    # Task 9: Notify Run Summary
    # ========================================================================

    @task(dag=dag, name="notify_run_summary")
    def task_notify_run_summary(
        run_init_result: Dict[str, Any],
        export_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        Send execution summary notification and mark run as completed.

        Args:
            run_init_result: Output from initialize_run task
            export_result: Output from export_excel_report task
            **context: Task context

        Returns:
            Dictionary with notification results
        """
        run_id = run_init_result['run_id']

        return notify_run_summary(
            run_id=run_id,
            notification_method='log'
        )

    # ========================================================================
    # Define Task Dependencies
    # ========================================================================

    # Set up the linear dependency chain
    initialize_run >> task_discover_hierarchy
    task_discover_hierarchy >> task_crawl_product_catalog
    task_crawl_product_catalog >> task_fetch_product_detail
    task_fetch_product_detail >> task_extract_and_normalize_specs
    task_extract_and_normalize_specs >> task_merge_manual_inputs
    task_merge_manual_inputs >> task_detect_data_quality_issues
    task_detect_data_quality_issues >> task_export_excel_report
    task_export_excel_report >> task_notify_run_summary

    logger.info(f"DAG '{dag_id}' created with 9 tasks")

    return dag


def register_dag(
    adapters: List,
    dag_config: Optional[Dict[str, Any]] = None,
) -> 'DAG':
    """
    Create and register the competitor scraping DAG.

    This is the main entry point for deploying the DAG to OpenClaw.

    Args:
        adapters: List of brand adapter instances
        dag_config: Optional DAG configuration

    Returns:
        Registered DAG instance

    Example:
        >>> from src.adapters.hikvision_adapter import HikvisionAdapter
        >>> from src.adapters.dahua_adapter import DahuaAdapter
        >>>
        >>> adapters = [HikvisionAdapter(), DahuaAdapter()]
        >>> dag = register_dag(adapters)
        >>> print(f"DAG registered: {dag.dag_id}")
    """
    logger.info("Registering competitor scraping DAG")

    dag = create_competitor_scraping_dag(
        adapters=adapters,
        config=dag_config
    )

    # Register with OpenClaw
    try:
        dag.register()
        logger.info(f"DAG '{dag.dag_id}' registered successfully")
    except Exception as e:
        logger.error(f"Failed to register DAG: {e}")
        raise

    return dag


# ========================================================================
# Manual Run Helpers
# ========================================================================

def run_manual_pipeline(
    run_id: str,
    adapters: List,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Manually run the entire pipeline for testing or ad-hoc execution.

    This function executes all tasks sequentially without OpenClaw orchestration.

    Args:
        run_id: Unique run identifier
        adapters: List of brand adapter instances
        config: Optional configuration

    Returns:
        Dictionary with pipeline execution results

    Example:
        >>> adapters = [HikvisionAdapter(), DahuaAdapter()]
        >>> result = run_manual_pipeline(
        ...     run_id="20260418_manual_01",
        ...     adapters=adapters
        ... )
        >>> print(f"Pipeline completed: {result['status']}")
    """
    logger.info(f"Starting manual pipeline execution for run_id={run_id}")

    start_time = datetime.utcnow()
    results = {}

    try:
        # Initialize database
        init_database()

        # Create run summary
        db = get_database()
        with db.session() as session:
            run_summary_repo = RunSummaryRepository(session)
            run_summary_repo.create_run_summary(
                run_id=run_id,
                schedule_type='manual'
            )

        # Execute tasks sequentially
        logger.info("Step 1: Discover hierarchy")
        results['discover'] = discover_hierarchy(run_id, adapters)

        logger.info("Step 2: Crawl catalog")
        results['catalog'] = crawl_product_catalog(run_id, adapters)

        logger.info("Step 3: Fetch details")
        results['detail'] = fetch_product_detail(
            run_id,
            adapters,
            max_workers=config.get('max_workers', DEFAULT_MAX_WORKERS) if config else DEFAULT_MAX_WORKERS
        )

        logger.info("Step 4: Extract specs")
        results['extract'] = extract_and_normalize_specs(run_id)

        logger.info("Step 5: Merge manual inputs")
        results['merge'] = merge_manual_inputs(run_id)

        logger.info("Step 6: Detect quality issues")
        quality_config = config.get('quality_detection') if config else None
        results['quality'] = detect_data_quality_issues(run_id, quality_config)

        logger.info("Step 7: Export Excel")
        results['export'] = export_excel_report(run_id)

        logger.info("Step 8: Notify summary")
        results['notify'] = notify_run_summary(run_id)

        duration = (datetime.utcnow() - start_time).total_seconds()

        result = {
            'status': 'success',
            'run_id': run_id,
            'duration_seconds': duration,
            'task_results': results,
        }

        logger.info(f"Manual pipeline completed successfully in {duration:.2f}s")

        return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"Manual pipeline failed after {duration:.2f}s: {e}", exc_info=True)

        # Update run status to failed
        try:
            db = get_database()
            with db.session() as session:
                run_summary_repo = RunSummaryRepository(session)
                run_summary_repo.update_status(
                    run_id=run_id,
                    status='failed',
                    error_message=str(e)
                )
        except Exception as db_error:
            logger.error(f"Failed to update run status: {db_error}")

        return {
            'status': 'failed',
            'run_id': run_id,
            'duration_seconds': duration,
            'error': str(e),
            'task_results': results,
        }
