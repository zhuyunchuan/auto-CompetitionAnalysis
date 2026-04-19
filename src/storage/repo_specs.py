"""
Repository for ProductSpecLong CRUD operations.

This module provides data access methods for the product_specs_long table,
including creation, querying, and management of specification records in long format.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from src.storage.schema import ProductSpecLong
from src.core.types import SpecRecord
from src.core.logging import get_logger

logger = get_logger(__name__)


class SpecRepository:
    """
    Repository for product specification data access.

    Provides methods to store, retrieve, and manage specification records
    in long format (one row per field per product).
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create_spec_record(
        self,
        record: SpecRecord,
        value_type: str = "string",
    ) -> ProductSpecLong:
        """
        Create a new specification record.

        Args:
            record: SpecRecord data
            value_type: Type of value (string, numeric, boolean, enum, list, range)

        Returns:
            Created ProductSpecLong instance
        """
        spec = ProductSpecLong(
            run_id=record.run_id,
            brand=record.brand,
            series_l1=record.series_l1,
            series_l2=record.series_l2,
            product_model=record.model,
            field_code=record.field_code,
            field_name=record.field_code,  # TODO: Map to display name
            raw_value=record.raw_value,
            normalized_value=record.normalized_value,
            unit=record.unit,
            value_type=value_type,
            source_url=record.source_url,
            extract_confidence=record.confidence,
            is_manual_override=False,
            updated_at=datetime.utcnow(),
        )

        self.session.add(spec)
        logger.debug(
            "Created spec record",
            extra={
                "run_id": record.run_id,
                "brand": record.brand,
                "model": record.model,
                "field_code": record.field_code,
            }
        )

        return spec

    def batch_create_spec_records(
        self,
        records: List[SpecRecord],
        batch_size: int = 100,
    ) -> int:
        """
        Batch create specification records.

        Args:
            records: List of spec records
            batch_size: Number of records to batch per insert

        Returns:
            Number of records created
        """
        count = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            spec_records = [
                ProductSpecLong(
                    run_id=record.run_id,
                    brand=record.brand,
                    series_l1=record.series_l1,
                    series_l2=record.series_l2,
                    product_model=record.model,
                    field_code=record.field_code,
                    field_name=record.field_code,
                    raw_value=record.raw_value,
                    normalized_value=record.normalized_value,
                    unit=record.unit,
                    value_type="string",  # TODO: Infer from value
                    source_url=record.source_url,
                    extract_confidence=record.confidence,
                    is_manual_override=False,
                    updated_at=datetime.utcnow(),
                )
                for record in batch
            ]

            self.session.add_all(spec_records)
            count += len(batch)

            logger.debug(
                f"Batch inserted {len(batch)} spec records",
                extra={"batch_count": len(batch)}
            )

        logger.info(
            f"Batch created {count} spec records",
            extra={"total_count": count}
        )

        return count

    def get_by_run_id(self, run_id: str) -> List[ProductSpecLong]:
        """
        Get all specification records for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of ProductSpecLong instances
        """
        query = self.session.query(ProductSpecLong).filter(
            ProductSpecLong.run_id == run_id
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} spec records for run",
            extra={"run_id": run_id}
        )

        return results

    def get_by_product(
        self,
        run_id: str,
        model: str,
    ) -> List[ProductSpecLong]:
        """
        Get all specifications for a specific product.

        Args:
            run_id: Run identifier
            model: Product model number

        Returns:
            List of ProductSpecLong instances
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.product_model == model
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} spec records for product",
            extra={"run_id": run_id, "model": model}
        )

        return results

    def get_by_field(
        self,
        run_id: str,
        field_code: str,
    ) -> List[ProductSpecLong]:
        """
        Get all specification records for a specific field.

        Args:
            run_id: Run identifier
            field_code: Field code

        Returns:
            List of ProductSpecLong instances
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.field_code == field_code
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} spec records for field",
            extra={"run_id": run_id, "field_code": field_code}
        )

        return results

    def get_spec_value(
        self,
        run_id: str,
        model: str,
        field_code: str,
    ) -> Optional[ProductSpecLong]:
        """
        Get a specific specification value for a product.

        Args:
            run_id: Run identifier
            model: Product model number
            field_code: Field code

        Returns:
            ProductSpecLong instance or None
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.product_model == model,
                ProductSpecLong.field_code == field_code
            )
        )

        result = query.first()

        if result:
            logger.debug(
                "Retrieved spec value",
                extra={
                    "run_id": run_id,
                    "model": model,
                    "field_code": field_code,
                }
            )

        return result

    def get_specs_for_brand(
        self,
        run_id: str,
        brand: str,
    ) -> List[ProductSpecLong]:
        """
        Get all specifications for a brand.

        Args:
            run_id: Run identifier
            brand: Brand name

        Returns:
            List of ProductSpecLong instances
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.brand == brand
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} spec records for brand",
            extra={"run_id": run_id, "brand": brand}
        )

        return results

    def get_missing_fields(
        self,
        run_id: str,
        model: str,
        required_fields: List[str],
    ) -> List[str]:
        """
        Identify which required fields are missing for a product.

        Args:
            run_id: Run identifier
            model: Product model number
            required_fields: List of required field codes

        Returns:
            List of missing field codes
        """
        # Get existing fields
        existing_query = self.session.query(
            ProductSpecLong.field_code
        ).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.product_model == model,
                ProductSpecLong.field_code.in_(required_fields)
            )
        )

        existing_fields = {row[0] for row in existing_query.all()}

        # Find missing
        missing = set(required_fields) - existing_fields

        return list(missing)

    def upsert_spec_record(
        self,
        record: SpecRecord,
        value_type: str = "string",
    ) -> ProductSpecLong:
        """
        Insert or update a specification record.

        If a record with the same run_id, model, and field_code exists,
        it will be updated. Otherwise, a new record is created.

        Args:
            record: SpecRecord data
            value_type: Type of value

        Returns:
            Created or updated ProductSpecLong instance
        """
        # Try to find existing record
        existing = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == record.run_id,
                ProductSpecLong.product_model == record.model,
                ProductSpecLong.field_code == record.field_code
            )
        ).first()

        if existing:
            # Update existing record
            existing.raw_value = record.raw_value
            existing.normalized_value = record.normalized_value
            existing.unit = record.unit
            existing.value_type = value_type
            existing.source_url = record.source_url
            existing.extract_confidence = record.confidence
            existing.updated_at = datetime.utcnow()

            logger.debug(
                "Updated spec record",
                extra={
                    "run_id": record.run_id,
                    "model": record.model,
                    "field_code": record.field_code,
                }
            )

            return existing
        else:
            # Create new record
            return self.create_spec_record(record, value_type)

    def get_manual_overrides(
        self,
        run_id: str,
    ) -> List[ProductSpecLong]:
        """
        Get all specification records that were manually overridden.

        Args:
            run_id: Run identifier

        Returns:
            List of ProductSpecLong instances with manual overrides
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.is_manual_override == True
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} manual override records",
            extra={"run_id": run_id}
        )

        return results

    def get_low_confidence_specs(
        self,
        run_id: str,
        threshold: float = 0.7,
    ) -> List[ProductSpecLong]:
        """
        Get specification records with low extraction confidence.

        Args:
            run_id: Run identifier
            threshold: Confidence threshold (default 0.7)

        Returns:
            List of ProductSpecLong instances below threshold
        """
        query = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.extract_confidence < threshold
            )
        )

        results = query.all()
        logger.debug(
            f"Retrieved {len(results)} low confidence spec records",
            extra={"run_id": run_id, "threshold": threshold}
        )

        return results

    def delete_by_run_id(self, run_id: str) -> int:
        """
        Delete all specification records for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Number of records deleted
        """
        count = self.session.query(ProductSpecLong).filter(
            ProductSpecLong.run_id == run_id
        ).delete()

        logger.info(
            f"Deleted {count} spec records for run",
            extra={"run_id": run_id}
        )

        return count

    def count_by_run_id(self, run_id: str) -> int:
        """
        Count specification records for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            Count of records
        """
        count = self.session.query(ProductSpecLong).filter(
            ProductSpecLong.run_id == run_id
        ).count()

        return count

    def count_by_product(
        self,
        run_id: str,
        model: str,
    ) -> int:
        """
        Count specification records for a product.

        Args:
            run_id: Run identifier
            model: Product model number

        Returns:
            Count of records
        """
        count = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.product_model == model
            )
        ).count()

        return count

    def get_field_statistics(
        self,
        run_id: str,
    ) -> Dict[str, Dict[str, int]]:
        """
        Get statistics about fields extracted in a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary mapping field_code to stats:
                - count: Number of products with this field
                - missing: Number of products missing this field
        """
        # Count products with each field
        query = self.session.query(
            ProductSpecLong.field_code,
            func.count().label('count')
        ).filter(
            ProductSpecLong.run_id == run_id
        ).group_by(
            ProductSpecLong.field_code
        )

        stats = {}
        for row in query.all():
            stats[row.field_code] = {
                "count": row.count,
                "missing": 0,  # TODO: Calculate from total product count
            }

        logger.debug(
            f"Calculated field statistics for {len(stats)} fields",
            extra={"run_id": run_id}
        )

        return stats
