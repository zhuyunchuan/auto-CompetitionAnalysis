"""
Repository for DataQualityIssue CRUD operations.

This module provides data access methods for the data_quality_issues table,
including creation, querying, and management of quality issues.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from src.storage.schema import DataQualityIssue
from src.core.types import QualityIssue
from src.core.logging import get_logger

logger = get_logger(__name__)


class IssueRepository:
    """
    Repository for data quality issue data access.

    Provides methods to store, retrieve, and manage quality issues,
    including filtering by severity, status, and ownership.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_issue(
        self,
        issue: QualityIssue,
        owner: Optional[str] = None,
    ) -> DataQualityIssue:
        """
        Create a new quality issue record.

        Args:
            issue: QualityIssue data
            owner: Optional owner assignment

        Returns:
            Created DataQualityIssue instance
        """
        quality_issue = DataQualityIssue(
            run_id=issue.run_id,
            brand=issue.brand,
            series_l1=issue.series_l1,
            series_l2=issue.series_l2,
            product_model=issue.model if issue.model else None,
            issue_type=issue.issue_type,
            field_code=issue.field_code,
            issue_detail=issue.detail,
            severity=issue.severity,
            status="open",
            owner=owner,
            created_at=datetime.utcnow(),
        )

        self.session.add(quality_issue)
        logger.debug(
            "Created quality issue",
            extra={
                "run_id": issue.run_id,
                "brand": issue.brand,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
            }
        )

        return quality_issue

    def batch_create_issues(
        self,
        issues: List[QualityIssue],
        batch_size: int = 100,
    ) -> int:
        """
        Batch create quality issue records.

        Args:
            issues: List of quality issues
            batch_size: Number of records to batch per insert

        Returns:
            Number of records created
        """
        count = 0

        for i in range(0, len(issues), batch_size):
            batch = issues[i:i + batch_size]

            issue_records = [
                DataQualityIssue(
                    run_id=issue.run_id,
                    brand=issue.brand,
                    series_l1=issue.series_l1,
                    series_l2=issue.series_l2,
                    product_model=issue.model if issue.model else None,
                    issue_type=issue.issue_type,
                    field_code=issue.field_code,
                    issue_detail=issue.detail,
                    severity=issue.severity,
                    status="open",
                    owner=None,
                    created_at=datetime.utcnow(),
                )
                for issue in batch
            ]

            self.session.add_all(issue_records)
            count += len(batch)

            logger.debug(
                f"Batch inserted {len(batch)} quality issues",
                extra={"batch_count": len(batch)}
            )

        logger.info(
            f"Batch created {count} quality issues",
            extra={"total_count": count}
        )

        return count

    def get_by_run_id(self, run_id: str) -> List[DataQualityIssue]:
        """
        Get all quality issues for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.run_id == run_id
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} quality issues for run",
            extra={"run_id": run_id}
        )

        return results

    def get_by_severity(
        self,
        run_id: str,
        severity: str,
    ) -> List[DataQualityIssue]:
        """
        Get quality issues filtered by severity.

        Args:
            run_id: Run identifier
            severity: Severity level (P1, P2, P3)

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.severity == severity
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} {severity} issues",
            extra={"run_id": run_id, "severity": severity}
        )

        return results

    def get_by_status(
        self,
        run_id: str,
        status: str,
    ) -> List[DataQualityIssue]:
        """
        Get quality issues filtered by status.

        Args:
            run_id: Run identifier
            status: Status (open, in_progress, resolved, ignored, false_positive)

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.status == status
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} {status} issues",
            extra={"run_id": run_id, "status": status}
        )

        return results

    def get_by_issue_type(
        self,
        run_id: str,
        issue_type: str,
    ) -> List[DataQualityIssue]:
        """
        Get quality issues filtered by issue type.

        Args:
            run_id: Run identifier
            issue_type: Type of issue (missing_field, parse_failed, etc.)

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.issue_type == issue_type
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} {issue_type} issues",
            extra={"run_id": run_id, "issue_type": issue_type}
        )

        return results

    def get_by_product(
        self,
        run_id: str,
        model: str,
    ) -> List[DataQualityIssue]:
        """
        Get quality issues for a specific product.

        Args:
            run_id: Run identifier
            model: Product model number

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.product_model == model
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} issues for product",
            extra={"run_id": run_id, "model": model}
        )

        return results

    def get_by_owner(
        self,
        owner: str,
        status: Optional[str] = None,
    ) -> List[DataQualityIssue]:
        """
        Get quality issues assigned to a specific owner.

        Args:
            owner: Owner name
            status: Optional status filter

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.owner == owner
        )

        if status:
            query = query.filter(DataQualityIssue.status == status)

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} issues for owner",
            extra={"owner": owner, "status": status}
        )

        return results

    def get_open_issues(
        self,
        run_id: str,
        min_severity: Optional[str] = None,
    ) -> List[DataQualityIssue]:
        """
        Get all open issues, optionally filtered by minimum severity.

        Args:
            run_id: Run identifier
            min_severity: Minimum severity level (P1, P2, P3)

        Returns:
            List of DataQualityIssue instances
        """
        query = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.status == "open"
            )
        )

        if min_severity:
            # Filter by severity (P1 > P2 > P3)
            severity_order = {"P1": 3, "P2": 2, "P3": 1}
            min_level = severity_order.get(min_severity, 0)

            # Include all severities at or above min_level
            allowed_severities = [
                sev for sev, level in severity_order.items()
                if level >= min_level
            ]

            query = query.filter(
                DataQualityIssue.severity.in_(allowed_severities)
            )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} open issues",
            extra={"run_id": run_id, "min_severity": min_severity}
        )

        return results

    def update_status(
        self,
        issue_id: int,
        new_status: str,
        owner: Optional[str] = None,
    ) -> Optional[DataQualityIssue]:
        """
        Update the status of a quality issue.

        Args:
            issue_id: Issue ID
            new_status: New status value
            owner: Optional new owner assignment

        Returns:
            Updated DataQualityIssue instance or None
        """
        issue = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.id == issue_id
        ).first()

        if issue:
            issue.status = new_status

            if owner:
                issue.owner = owner

            logger.debug(
                f"Updated issue status to {new_status}",
                extra={"issue_id": issue_id, "status": new_status}
            )

            return issue

        return None

    def batch_update_status(
        self,
        run_id: str,
        issue_type: str,
        new_status: str,
    ) -> int:
        """
        Batch update status for all issues of a specific type.

        Args:
            run_id: Run identifier
            issue_type: Type of issue to update
            new_status: New status value

        Returns:
            Number of records updated
        """
        count = self.session.query(DataQualityIssue).filter(
            and_(
                DataQualityIssue.run_id == run_id,
                DataQualityIssue.issue_type == issue_type
            )
        ).update(
            {"status": new_status},
            synchronize_session=False
        )

        logger.info(
            f"Updated {count} issues to {new_status}",
            extra={
                "run_id": run_id,
                "issue_type": issue_type,
                "new_status": new_status,
            }
        )

        return count

    def assign_owner(
        self,
        issue_id: int,
        owner: str,
    ) -> Optional[DataQualityIssue]:
        """
        Assign an owner to a quality issue.

        Args:
            issue_id: Issue ID
            owner: Owner to assign

        Returns:
            Updated DataQualityIssue instance or None
        """
        issue = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.id == issue_id
        ).first()

        if issue:
            issue.owner = owner

            logger.debug(
                f"Assigned owner to issue",
                extra={"issue_id": issue_id, "owner": owner}
            )

            return issue

        return None

    def get_issue_summary(
        self,
        run_id: str,
    ) -> Dict[str, Dict[str, int]]:
        """
        Get summary statistics of issues by severity and type.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with:
                - by_severity: {severity: count}
                - by_type: {issue_type: count}
                - by_status: {status: count}
                - total: Total count
        """
        # Count by severity
        severity_query = self.session.query(
            DataQualityIssue.severity,
            func.count().label('count')
        ).filter(
            DataQualityIssue.run_id == run_id
        ).group_by(
            DataQualityIssue.severity
        )

        by_severity = {row.severity: row.count for row in severity_query.all()}

        # Count by issue type
        type_query = self.session.query(
            DataQualityIssue.issue_type,
            func.count().label('count')
        ).filter(
            DataQualityIssue.run_id == run_id
        ).group_by(
            DataQualityIssue.issue_type
        )

        by_type = {row.issue_type: row.count for row in type_query.all()}

        # Count by status
        status_query = self.session.query(
            DataQualityIssue.status,
            func.count().label('count')
        ).filter(
            DataQualityIssue.run_id == run_id
        ).group_by(
            DataQualityIssue.status
        )

        by_status = {row.status: row.count for row in status_query.all()}

        # Total count
        total = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.run_id == run_id
        ).count()

        summary = {
            "by_severity": by_severity,
            "by_type": by_type,
            "by_status": by_status,
            "total": total,
        }

        logger.debug(
            "Generated issue summary",
            extra={
                "run_id": run_id,
                "total_issues": total,
                "p1_count": by_severity.get("P1", 0),
                "p2_count": by_severity.get("P2", 0),
                "p3_count": by_severity.get("P3", 0),
            }
        )

        return summary

    def delete_by_run_id(self, run_id: str) -> int:
        """
        Delete all quality issues for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Number of records deleted
        """
        count = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.run_id == run_id
        ).delete()

        logger.info(
            f"Deleted {count} quality issues for run",
            extra={"run_id": run_id}
        )

        return count

    def count_by_run_id(self, run_id: str) -> int:
        """
        Count quality issues for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Count of records
        """
        count = self.session.query(DataQualityIssue).filter(
            DataQualityIssue.run_id == run_id
        ).count()

        return count

    def get_critical_issues(
        self,
        run_id: str,
    ) -> List[DataQualityIssue]:
        """
        Get all critical (P1) issues for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of P1 DataQualityIssue instances
        """
        return self.get_by_severity(run_id, "P1")
