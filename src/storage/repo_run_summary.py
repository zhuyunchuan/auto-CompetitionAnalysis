"""
Repository for RunSummary CRUD operations.

This module provides data access methods for the run_summary table,
including creation, querying, and status updates for run tracking.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.storage.schema import RunSummary
from src.core.logging import get_logger

logger = get_logger(__name__)


class RunSummaryRepository:
    """
    Repository for run summary data access.

    Provides methods to store, retrieve, and update run summaries,
    including status tracking and metrics updates.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_run_summary(
        self,
        run_id: str,
        schedule_type: str,
    ) -> RunSummary:
        """
        Create a new run summary record.

        Args:
            run_id: Run identifier
            schedule_type: Schedule type (manual, biweekly, monthly)

        Returns:
            Created RunSummary instance
        """
        run_summary = RunSummary(
            run_id=run_id,
            schedule_type=schedule_type,
            started_at=datetime.utcnow(),
            ended_at=None,
            catalog_count=0,
            spec_field_count=0,
            issue_count=0,
            new_series_count=0,
            disappeared_series_count=0,
            success_rate=0.0,
            status='running',
        )

        self.session.add(run_summary)
        logger.info(
            f"Created run summary for {run_id}",
            extra={"run_id": run_id, "schedule_type": schedule_type}
        )

        return run_summary

    def get_by_run_id(self, run_id: str) -> Optional[RunSummary]:
        """
        Get run summary by run ID.

        Args:
            run_id: Run identifier

        Returns:
            RunSummary instance or None
        """
        query = self.session.query(RunSummary).filter(
            RunSummary.run_id == run_id
        )

        result = query.first()

        if result:
            logger.debug(
                "Retrieved run summary",
                extra={"run_id": run_id}
            )

        return result

    def update_status(
        self,
        run_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[RunSummary]:
        """
        Update run status.

        Args:
            run_id: Run identifier
            status: New status (running, completed, failed, cancelled)
            error_message: Optional error message

        Returns:
            Updated RunSummary instance or None
        """
        run_summary = self.get_by_run_id(run_id)

        if not run_summary:
            logger.warning(
                f"Run summary not found for {run_id}, cannot update status"
            )
            return None

        run_summary.status = status

        if status in ['completed', 'failed', 'cancelled']:
            run_summary.ended_at = datetime.utcnow()

        if error_message:
            logger.error(
                f"Run {run_id} status updated to {status}: {error_message}",
                extra={"run_id": run_id, "status": status}
            )

        return run_summary

    def update_catalog_stats(
        self,
        run_id: str,
        catalog_count: int,
    ) -> Optional[RunSummary]:
        """
        Update catalog statistics.

        Args:
            run_id: Run identifier
            catalog_count: Number of products in catalog

        Returns:
            Updated RunSummary instance or None
        """
        run_summary = self.get_by_run_id(run_id)

        if not run_summary:
            logger.warning(
                f"Run summary not found for {run_id}, cannot update catalog stats"
            )
            return None

        run_summary.catalog_count = catalog_count

        logger.debug(
            f"Updated catalog stats for {run_id}: {catalog_count} products",
            extra={"run_id": run_id, "catalog_count": catalog_count}
        )

        return run_summary

    def update_spec_stats(
        self,
        run_id: str,
        spec_field_count: int,
    ) -> Optional[RunSummary]:
        """
        Update specification statistics.

        Args:
            run_id: Run identifier
            spec_field_count: Number of spec fields extracted

        Returns:
            Updated RunSummary instance or None
        """
        run_summary = self.get_by_run_id(run_id)

        if not run_summary:
            logger.warning(
                f"Run summary not found for {run_id}, cannot update spec stats"
            )
            return None

        run_summary.spec_field_count = spec_field_count

        logger.debug(
            f"Updated spec stats for {run_id}: {spec_field_count} fields",
            extra={"run_id": run_id, "spec_field_count": spec_field_count}
        )

        return run_summary

    def update_quality_stats(
        self,
        run_id: str,
        issue_count: int,
    ) -> Optional[RunSummary]:
        """
        Update quality statistics.

        Args:
            run_id: Run identifier
            issue_count: Number of quality issues detected

        Returns:
            Updated RunSummary instance or None
        """
        run_summary = self.get_by_run_id(run_id)

        if not run_summary:
            logger.warning(
                f"Run summary not found for {run_id}, cannot update quality stats"
            )
            return None

        run_summary.issue_count = issue_count

        # Calculate success rate
        if run_summary.catalog_count > 0:
            run_summary.success_rate = (
                (run_summary.catalog_count - issue_count) / run_summary.catalog_count
            )
        else:
            run_summary.success_rate = 0.0

        logger.debug(
            f"Updated quality stats for {run_id}: {issue_count} issues, "
            f"{run_summary.success_rate:.2%} success rate",
            extra={"run_id": run_id, "issue_count": issue_count}
        )

        return run_summary

    def update_hierarchy_stats(
        self,
        run_id: str,
        new_series_count: int,
        disappeared_series_count: int = 0,
    ) -> Optional[RunSummary]:
        """
        Update hierarchy statistics.

        Args:
            run_id: Run identifier
            new_series_count: Number of new series discovered
            disappeared_series_count: Number of disappeared series

        Returns:
            Updated RunSummary instance or None
        """
        run_summary = self.get_by_run_id(run_id)

        if not run_summary:
            logger.warning(
                f"Run summary not found for {run_id}, cannot update hierarchy stats"
            )
            return None

        run_summary.new_series_count = new_series_count
        run_summary.disappeared_series_count = disappeared_series_count

        logger.debug(
            f"Updated hierarchy stats for {run_id}: "
            f"{new_series_count} new, {disappeared_series_count} disappeared",
            extra={
                "run_id": run_id,
                "new_series_count": new_series_count,
                "disappeared_series_count": disappeared_series_count
            }
        )

        return run_summary

    def get_recent_runs(
        self,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[RunSummary]:
        """
        Get recent runs.

        Args:
            limit: Maximum number of runs to return
            status: Optional status filter

        Returns:
            List of RunSummary instances
        """
        query = self.session.query(RunSummary)

        if status:
            query = query.filter(RunSummary.status == status)

        query = query.order_by(RunSummary.started_at.desc()).limit(limit)

        results = query.all()

        logger.debug(
            f"Retrieved {len(results)} recent runs",
            extra={"limit": limit, "status": status}
        )

        return results

    def delete_by_run_id(self, run_id: str) -> int:
        """
        Delete run summary for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Number of records deleted (0 or 1)
        """
        count = self.session.query(RunSummary).filter(
            RunSummary.run_id == run_id
        ).delete()

        logger.info(
            f"Deleted run summary for {run_id}",
            extra={"run_id": run_id}
        )

        return count
