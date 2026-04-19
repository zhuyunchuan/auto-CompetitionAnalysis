"""
Repository for ProductCatalog CRUD operations.

This module provides data access methods for the product_catalog table,
including creation, querying, and lifecycle management for product catalog entries.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from src.storage.schema import ProductCatalog
from src.core.types import CatalogItem
from src.core.logging import get_logger

logger = get_logger(__name__)


class CatalogRepository:
    """
    Repository for product catalog data access.

    Provides methods to store, retrieve, and manage product catalog entries,
    including lifecycle tracking (first_seen, last_seen, status).
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_catalog_entry(
        self,
        run_id: str,
        item: CatalogItem,
        status: str = "current",
    ) -> ProductCatalog:
        """
        Create a new product catalog entry.

        Args:
            run_id: Run identifier
            item: Catalog item data
            status: Catalog status (current, discontinued, replaced)

        Returns:
            Created ProductCatalog instance
        """
        now = datetime.utcnow()

        catalog = ProductCatalog(
            run_id=run_id,
            brand=item.brand,
            series_l1=item.series_l1,
            series_l2=item.series_l2,
            product_model=item.model,
            product_name=item.name,
            product_url=item.url,
            locale=item.locale,
            first_seen_at=now,
            last_seen_at=now,
            catalog_status=status,
        )

        self.session.add(catalog)
        logger.debug(
            "Created catalog entry",
            extra={
                "run_id": run_id,
                "brand": item.brand,
                "model": item.model,
            }
        )

        return catalog

    def batch_create_catalog_entries(
        self,
        run_id: str,
        items: List[CatalogItem],
        batch_size: int = 100,
    ) -> int:
        """
        Batch create product catalog entries.

        Args:
            run_id: Run identifier
            items: List of catalog items
            batch_size: Number of records to batch per insert

        Returns:
            Number of records created
        """
        count = 0
        now = datetime.utcnow()

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            catalog_entries = [
                ProductCatalog(
                    run_id=run_id,
                    brand=item.brand,
                    series_l1=item.series_l1,
                    series_l2=item.series_l2,
                    product_model=item.model,
                    product_name=item.name,
                    product_url=item.url,
                    locale=item.locale,
                    first_seen_at=now,
                    last_seen_at=now,
                    catalog_status="current",
                )
                for item in batch
            ]

            self.session.add_all(catalog_entries)
            count += len(batch)

            logger.debug(
                f"Batch inserted {len(batch)} catalog entries",
                extra={"run_id": run_id, "batch_count": len(batch)}
            )

        logger.info(
            f"Batch created {count} catalog entries",
            extra={"run_id": run_id, "total_count": count}
        )

        return count

    def get_by_run_id(self, run_id: str) -> List[ProductCatalog]:
        """
        Get all catalog entries for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of ProductCatalog instances
        """
        query = self.session.query(ProductCatalog).filter(
            ProductCatalog.run_id == run_id
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} catalog entries for run",
            extra={"run_id": run_id}
        )

        return results

    def get_by_brand(
        self,
        run_id: str,
        brand: str,
    ) -> List[ProductCatalog]:
        """
        Get catalog entries for a specific brand in a run.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            List of ProductCatalog instances
        """
        query = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.brand == brand
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} catalog entries for brand",
            extra={"run_id": run_id, "brand": brand}
        )

        return results

    def get_by_series(
        self,
        run_id: str,
        brand: str,
        series_l1: str,
        series_l2: Optional[str] = None,
    ) -> List[ProductCatalog]:
        """
        Get catalog entries for a specific series hierarchy.

        Args:
            run_id: Run identifier
            brand: Brand name
            series_l1: Series level 1 name
            series_l2: Optional series level 2 name

        Returns:
            List of ProductCatalog instances
        """
        conditions = [
            ProductCatalog.run_id == run_id,
            ProductCatalog.brand == brand,
            ProductCatalog.series_l1 == series_l1,
        ]

        if series_l2:
            conditions.append(ProductCatalog.series_l2 == series_l2)

        query = self.session.query(ProductCatalog).filter(
            and_(*conditions)
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} catalog entries for series",
            extra={
                "run_id": run_id,
                "brand": brand,
                "series_l1": series_l1,
                "series_l2": series_l2,
            }
        )

        return results

    def get_by_model(
        self,
        run_id: str,
        model: str,
    ) -> Optional[ProductCatalog]:
        """
        Get catalog entry by product model.

        Args:
            run_id: Run identifier
            model: Product model number

        Returns:
            ProductCatalog instance or None
        """
        query = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.product_model == model
            )
        )

        result = query.first()

        if result:
            logger.debug(
                "Retrieved catalog entry by model",
                extra={"run_id": run_id, "model": model}
            )

        return result

    def check_duplicate_model(
        self,
        run_id: str,
        model: str,
    ) -> bool:
        """
        Check if a product model already exists in the run.

        Args:
            run_id: Run identifier
            model: Product model number

        Returns:
            True if duplicate exists, False otherwise
        """
        exists = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.product_model == model
            )
        ).first() is not None

        return exists

    def find_duplicates_in_run(
        self,
        run_id: str,
    ) -> Dict[str, List[ProductCatalog]]:
        """
        Find all duplicate product models within a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary mapping model to list of duplicate entries
        """
        # Subquery to find duplicates
        subq = self.session.query(
            ProductCatalog.product_model,
            func.count().label('count')
        ).filter(
            ProductCatalog.run_id == run_id
        ).group_by(
            ProductCatalog.product_model
        ).having(
            func.count() > 1
        ).subquery()

        # Query actual duplicate records
        query = self.session.query(ProductCatalog).join(
            subq,
            ProductCatalog.product_model == subq.c.product_model
        ).filter(
            ProductCatalog.run_id == run_id
        )

        results = query.all()

        # Group by model
        duplicates: Dict[str, List[ProductCatalog]] = {}
        for record in results:
            if record.product_model not in duplicates:
                duplicates[record.product_model] = []
            duplicates[record.product_model].append(record)

        logger.warning(
            f"Found {len(duplicates)} duplicate models in run",
            extra={
                "run_id": run_id,
                "duplicate_count": len(duplicates),
                "total_records": sum(len(v) for v in duplicates.values()),
            }
        )

        return duplicates

    def update_last_seen(
        self,
        run_id: str,
        models: List[str],
    ) -> int:
        """
        Update last_seen_at timestamp for existing products.

        This is used to mark products as still active in a new run.

        Args:
            run_id: Run identifier
            models: List of model numbers to update

        Returns:
            Number of records updated
        """
        now = datetime.utcnow()

        count = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.product_model.in_(models)
            )
        ).update(
            {"last_seen_at": now},
            synchronize_session=False
        )

        logger.debug(
            f"Updated last_seen_at for {count} products",
            extra={"run_id": run_id}
        )

        return count

    def mark_discontinued(
        self,
        run_id: str,
        older_than_days: int = 60,
    ) -> int:
        """
        Mark products as discontinued if not seen recently.

        Args:
            run_id: Current run identifier
            older_than_days: Days threshold for discontinuation

        Returns:
            Number of records marked as discontinued
        """
        threshold = datetime.utcnow()

        # Note: This is a simplified implementation
        # In practice, you'd want to compare with the latest run
        count = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.catalog_status == "current",
                ProductCatalog.last_seen_at < threshold
            )
        ).update(
            {"catalog_status": "discontinued"},
            synchronize_session=False
        )

        logger.info(
            f"Marked {count} products as discontinued",
            extra={"run_id": run_id}
        )

        return count

    def get_models_by_brand(
        self,
        run_id: str,
        brand: str,
    ) -> List[str]:
        """
        Get all product model numbers for a brand.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            List of model numbers
        """
        query = self.session.query(
            ProductCatalog.product_model
        ).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.brand == brand
            )
        )

        results = [row[0] for row in query.all()]
        logger.debug(
            f"Retrieved {len(results)} models for brand",
            extra={"run_id": run_id, "brand": brand}
        )

        return results

    def count_by_run_id(self, run_id: str) -> int:
        """
        Count catalog entries for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Count of records
        """
        count = self.session.query(ProductCatalog).filter(
            ProductCatalog.run_id == run_id
        ).count()

        return count

    def count_by_brand(
        self,
        run_id: str,
        brand: str,
    ) -> int:
        """
        Count catalog entries for a specific brand.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            Count of records
        """
        count = self.session.query(ProductCatalog).filter(
            and_(
                ProductCatalog.run_id == run_id,
                ProductCatalog.brand == brand
            )
        ).count()

        return count

    def delete_by_run_id(self, run_id: str) -> int:
        """
        Delete all catalog entries for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Number of records deleted
        """
        count = self.session.query(ProductCatalog).filter(
            ProductCatalog.run_id == run_id
        ).delete()

        logger.info(
            f"Deleted {count} catalog entries for run",
            extra={"run_id": run_id}
        )

        return count
