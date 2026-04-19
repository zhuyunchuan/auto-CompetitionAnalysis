"""
Run summary writer for competitor analysis system.

This module generates and updates run summary records with execution metrics
and statistics for monitoring and trend analysis.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.storage.schema import RunSummary
from src.core.logging import get_logger

logger = get_logger(__name__)


class RunSummaryWriter:
    """
    Generate and manage run summary records.

    Calculates metrics from database data and creates RunSummary records
    for monitoring and reporting.
    """

    def __init__(self, session: Session):
        """
        Initialize run summary writer.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_run_summary(
        self,
        run_id: str,
        schedule_type: str,
        started_at: datetime,
    ) -> RunSummary:
        """
        Create a new run summary record with initial values.

        Args:
            run_id: Run identifier
            schedule_type: Schedule type (manual, biweekly, monthly)
            started_at: Start timestamp

        Returns:
            Created RunSummary instance
        """
        summary = RunSummary(
            run_id=run_id,
            schedule_type=schedule_type,
            started_at=started_at,
            ended_at=None,
            catalog_count=0,
            spec_field_count=0,
            issue_count=0,
            new_series_count=0,
            disappeared_series_count=0,
            success_rate=0.0,
            status='running',
        )

        self.session.add(summary)
        self.session.flush()

        logger.info(
            f"Created run summary",
            extra={
                "run_id": run_id,
                "schedule_type": schedule_type,
            }
        )

        return summary

    def update_run_completion(
        self,
        run_id: str,
        ended_at: datetime,
        status: str = 'completed',
    ) -> Optional[RunSummary]:
        """
        Update run summary with completion status and timestamp.

        Args:
            run_id: Run identifier
            ended_at: End timestamp
            status: Final status (completed, failed, cancelled)

        Returns:
            Updated RunSummary instance or None
        """
        summary = self.session.query(RunSummary).filter(
            RunSummary.run_id == run_id
        ).first()

        if summary:
            summary.ended_at = ended_at
            summary.status = status

            self.session.flush()

            logger.info(
                f"Updated run summary completion",
                extra={
                    "run_id": run_id,
                    "status": status,
                    "duration_sec": (ended_at - summary.started_at).total_seconds(),
                }
            )

        return summary

    def update_metrics(
        self,
        run_id: str,
        catalog_count: Optional[int] = None,
        spec_field_count: Optional[int] = None,
        issue_count: Optional[int] = None,
        new_series_count: Optional[int] = None,
        disappeared_series_count: Optional[int] = None,
        success_rate: Optional[float] = None,
    ) -> Optional[RunSummary]:
        """
        Update run summary metrics.

        Args:
            run_id: Run identifier
            catalog_count: Number of catalog entries
            spec_field_count: Number of spec field records
            issue_count: Number of quality issues
            new_series_count: Number of new series discovered
            disappeared_series_count: Number of disappeared series
            success_rate: Success rate (0.0 to 1.0)

        Returns:
            Updated RunSummary instance or None
        """
        summary = self.session.query(RunSummary).filter(
            RunSummary.run_id == run_id
        ).first()

        if summary:
            if catalog_count is not None:
                summary.catalog_count = catalog_count
            if spec_field_count is not None:
                summary.spec_field_count = spec_field_count
            if issue_count is not None:
                summary.issue_count = issue_count
            if new_series_count is not None:
                summary.new_series_count = new_series_count
            if disappeared_series_count is not None:
                summary.disappeared_series_count = disappeared_series_count
            if success_rate is not None:
                summary.success_rate = success_rate

            self.session.flush()

            logger.debug(
                f"Updated run summary metrics",
                extra={
                    "run_id": run_id,
                    "catalog_count": catalog_count,
                    "spec_field_count": spec_field_count,
                    "issue_count": issue_count,
                }
            )

        return summary

    def calculate_success_rate(
        self,
        run_id: str,
        total_products: int,
        failed_products: int,
    ) -> float:
        """
        Calculate success rate for a run.

        Args:
            run_id: Run identifier
            total_products: Total number of products processed
            failed_products: Number of products with failures

        Returns:
            Success rate (0.0 to 1.0)
        """
        if total_products == 0:
            return 0.0

        success_rate = (total_products - failed_products) / total_products
        return round(success_rate, 4)

    def get_run_summary(self, run_id: str) -> Optional[RunSummary]:
        """
        Get run summary by run ID.

        Args:
            run_id: Run identifier

        Returns:
            RunSummary instance or None
        """
        summary = self.session.query(RunSummary).filter(
            RunSummary.run_id == run_id
        ).first()

        return summary

    def get_recent_runs(
        self,
        limit: int = 10,
        schedule_type: Optional[str] = None,
    ) -> list[RunSummary]:
        """
        Get recent run summaries.

        Args:
            limit: Maximum number of runs to return
            schedule_type: Optional schedule type filter

        Returns:
            List of RunSummary instances
        """
        query = self.session.query(RunSummary).order_by(
            RunSummary.started_at.desc()
        )

        if schedule_type:
            query = query.filter(RunSummary.schedule_type == schedule_type)

        results = query.limit(limit).all()

        logger.debug(
            f"Retrieved recent runs",
            extra={"count": len(results), "limit": limit}
        )

        return results

    def get_run_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with run statistics
        """
        summary = self.get_run_summary(run_id)

        if not summary:
            return {}

        duration = None
        if summary.started_at and summary.ended_at:
            duration = (summary.ended_at - summary.started_at).total_seconds()

        stats = {
            'run_id': summary.run_id,
            'schedule_type': summary.schedule_type,
            'started_at': summary.started_at.isoformat() if summary.started_at else None,
            'ended_at': summary.ended_at.isoformat() if summary.ended_at else None,
            'duration_seconds': duration,
            'catalog_count': summary.catalog_count,
            'spec_field_count': summary.spec_field_count,
            'issue_count': summary.issue_count,
            'new_series_count': summary.new_series_count,
            'disappeared_series_count': summary.disappeared_series_count,
            'success_rate': summary.success_rate,
            'status': summary.status,
        }

        return stats

    def mark_failed(
        self,
        run_id: str,
        ended_at: datetime,
        error_message: Optional[str] = None,
    ) -> Optional[RunSummary]:
        """
        Mark a run as failed.

        Args:
            run_id: Run identifier
            ended_at: End timestamp
            error_message: Optional error message

        Returns:
            Updated RunSummary instance or None
        """
        summary = self.update_run_completion(run_id, ended_at, status='failed')

        if error_message:
            logger.error(
                f"Run marked as failed: {error_message}",
                extra={"run_id": run_id}
            )

        return summary

    def mark_cancelled(
        self,
        run_id: str,
        ended_at: datetime,
    ) -> Optional[RunSummary]:
        """
        Mark a run as cancelled.

        Args:
            run_id: Run identifier
            ended_at: End timestamp

        Returns:
            Updated RunSummary instance or None
        """
        summary = self.update_run_completion(run_id, ended_at, status='cancelled')

        logger.warning(
            f"Run marked as cancelled",
            extra={"run_id": run_id}
        )

        return summary
