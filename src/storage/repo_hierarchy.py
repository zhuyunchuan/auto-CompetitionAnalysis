"""
Repository for HierarchySnapshot CRUD operations.

This module provides data access methods for the hierarchy_snapshot table,
including creation, querying, and comparison operations for tracking
hierarchy changes over time.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.storage.schema import HierarchySnapshot
from src.core.types import HierarchyNode
from src.core.logging import get_logger

logger = get_logger(__name__)


class HierarchyRepository:
    """
    Repository for hierarchy snapshot data access.

    Provides methods to store, retrieve, and compare hierarchy snapshots
    for tracking series/subseries changes across runs.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_snapshot(
        self,
        run_id: str,
        node: HierarchyNode,
    ) -> HierarchySnapshot:
        """
        Create a new hierarchy snapshot record.

        Args:
            run_id: Run identifier
            node: Hierarchy node data

        Returns:
            Created HierarchySnapshot instance
        """
        snapshot = HierarchySnapshot(
            run_id=run_id,
            brand=node.brand,
            series_l1=node.series_l1,
            series_l2=node.series_l2,
            series_source=node.source,
            series_status=node.status,
            discovered_at=node.discovered_at,
        )

        self.session.add(snapshot)
        logger.debug(
            "Created hierarchy snapshot",
            extra={
                "run_id": run_id,
                "brand": node.brand,
                "series_l1": node.series_l1,
                "series_l2": node.series_l2,
            }
        )

        return snapshot

    def batch_create_snapshots(
        self,
        run_id: str,
        nodes: List[HierarchyNode],
        batch_size: int = 100,
    ) -> int:
        """
        Batch create hierarchy snapshot records.

        Args:
            run_id: Run identifier
            nodes: List of hierarchy nodes
            batch_size: Number of records to batch per insert

        Returns:
            Number of records created
        """
        count = 0

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]

            snapshots = [
                HierarchySnapshot(
                    run_id=run_id,
                    brand=node.brand,
                    series_l1=node.series_l1,
                    series_l2=node.series_l2,
                    series_source=node.source,
                    series_status=node.status,
                    discovered_at=node.discovered_at,
                )
                for node in batch
            ]

            self.session.add_all(snapshots)
            count += len(batch)

            logger.debug(
                f"Batch inserted {len(batch)} hierarchy snapshots",
                extra={"run_id": run_id, "batch_count": len(batch)}
            )

        logger.info(
            f"Batch created {count} hierarchy snapshots",
            extra={"run_id": run_id, "total_count": count}
        )

        return count

    def get_by_run_id(self, run_id: str) -> List[HierarchySnapshot]:
        """
        Get all hierarchy snapshots for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of HierarchySnapshot instances
        """
        query = self.session.query(HierarchySnapshot).filter(
            HierarchySnapshot.run_id == run_id
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} hierarchy snapshots for run",
            extra={"run_id": run_id}
        )

        return results

    def get_by_brand(
        self,
        run_id: str,
        brand: str,
    ) -> List[HierarchySnapshot]:
        """
        Get hierarchy snapshots for a specific brand in a run.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            List of HierarchySnapshot instances
        """
        query = self.session.query(HierarchySnapshot).filter(
            and_(
                HierarchySnapshot.run_id == run_id,
                HierarchySnapshot.brand == brand
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} hierarchy snapshots for brand",
            extra={"run_id": run_id, "brand": brand}
        )

        return results

    def get_series_l1(
        self,
        run_id: str,
        brand: str,
    ) -> List[str]:
        """
        Get all unique series_l1 values for a brand.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            List of series_l1 names
        """
        query = self.session.query(
            HierarchySnapshot.series_l1
        ).filter(
            and_(
                HierarchySnapshot.run_id == run_id,
                HierarchySnapshot.brand == brand
            )
        ).distinct()

        results = [row[0] for row in query.all() if row[0]]
        logger.debug(
            f"Retrieved {len(results)} series_l1 for brand",
            extra={"run_id": run_id, "brand": brand}
        )

        return results

    def get_series_l2(
        self,
        run_id: str,
        brand: str,
        series_l1: str,
    ) -> List[str]:
        """
        Get all unique series_l2 values for a brand and series_l1.

        Args:
            run_id: Run identifier
            brand: Brand name
            series_l1: Series level 1 name

        Returns:
            List of series_l2 names
        """
        query = self.session.query(
            HierarchySnapshot.series_l2
        ).filter(
            and_(
                HierarchySnapshot.run_id == run_id,
                HierarchySnapshot.brand == brand,
                HierarchySnapshot.series_l1 == series_l1
            )
        ).distinct()

        results = [row[0] for row in query.all() if row[0]]
        logger.debug(
            f"Retrieved {len(results)} series_l2 for series",
            extra={"run_id": run_id, "brand": brand, "series_l1": series_l1}
        )

        return results

    def compare_with_previous_run(
        self,
        current_run_id: str,
        previous_run_id: str,
        brand: str,
    ) -> Dict[str, Any]:
        """
        Compare hierarchy between two runs and identify changes.

        Args:
            current_run_id: Current run identifier
            previous_run_id: Previous run identifier
            brand: Brand to compare

        Returns:
            Dictionary with:
                - new_series: List of new (series_l1, series_l2) tuples
                - disappeared_series: List of missing (series_l1, series_l2) tuples
        """
        # Get hierarchies from both runs
        current_query = self.session.query(
            HierarchySnapshot.series_l1,
            HierarchySnapshot.series_l2,
        ).filter(
            and_(
                HierarchySnapshot.run_id == current_run_id,
                HierarchySnapshot.brand == brand
            )
        )

        previous_query = self.session.query(
            HierarchySnapshot.series_l1,
            HierarchySnapshot.series_l2,
        ).filter(
            and_(
                HierarchySnapshot.run_id == previous_run_id,
                HierarchySnapshot.brand == brand
            )
        )

        current_set = {
            (row.series_l1, row.series_l2)
            for row in current_query.all()
        }

        previous_set = {
            (row.series_l1, row.series_l2)
            for row in previous_query.all()
        }

        # Identify changes
        new_series = list(current_set - previous_set)
        disappeared_series = list(previous_set - current_set)

        result = {
            "new_series": new_series,
            "disappeared_series": disappeared_series,
            "new_count": len(new_series),
            "disappeared_count": len(disappeared_series),
        }

        logger.info(
            "Hierarchy comparison completed",
            extra={
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "brand": brand,
                "new_count": result["new_count"],
                "disappeared_count": result["disappeared_count"],
            }
        )

        return result

    def get_latest_run_id(self, brand: Optional[str] = None) -> Optional[str]:
        """
        Get the most recent run_id for a brand or overall.

        Args:
            brand: Optional brand filter

        Returns:
            Latest run_id or None if no data exists
        """
        query = self.session.query(
            HierarchySnapshot.run_id
        ).order_by(
            HierarchySnapshot.discovered_at.desc()
        )

        if brand:
            query = query.filter(HierarchySnapshot.brand == brand)

        result = query.first()

        if result:
            logger.debug(
                "Retrieved latest run_id",
                extra={"run_id": result[0], "brand": brand}
            )
            return result[0]

        return None

    def delete_by_run_id(self, run_id: str) -> int:
        """
        Delete all hierarchy snapshots for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Number of records deleted
        """
        count = self.session.query(HierarchySnapshot).filter(
            HierarchySnapshot.run_id == run_id
        ).delete()

        logger.info(
            f"Deleted {count} hierarchy snapshots for run",
            extra={"run_id": run_id}
        )

        return count

    def count_by_run_id(self, run_id: str) -> int:
        """
        Count hierarchy snapshots for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Count of records
        """
        count = self.session.query(HierarchySnapshot).filter(
            HierarchySnapshot.run_id == run_id
        ).count()

        return count
