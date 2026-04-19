"""
Override service for applying manual corrections to specifications.

This module fetches manual inputs from the manual_inputs table and applies
them to specification records in the product_specs_long table, maintaining
an audit trail of all overrides.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.storage.schema import ManualInput, ProductSpecLong
from src.core.logging import get_logger

logger = get_logger(__name__)


class OverrideService:
    """
    Apply manual overrides to specification records.

    Fetches manual inputs and applies them to spec records,
    setting is_manual_override flag and maintaining audit trail.
    """

    def __init__(self, session: Session):
        """
        Initialize override service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def apply_overrides_for_run(
        self,
        run_id: str,
    ) -> Dict[str, Any]:
        """
        Apply all manual overrides to a specific run.

        Fetches all manual inputs and applies matching overrides to spec records
        in the given run. Last write wins if multiple manual inputs match.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with application results:
                - applied_count: Number of overrides applied
                - skipped_count: Number of overrides skipped (no matching spec)
                - error_count: Number of errors
        """
        logger.info(
            f"Applying manual overrides for run",
            extra={"run_id": run_id}
        )

        # Get all manual inputs
        manual_inputs = self.session.query(ManualInput).all()

        results = {
            'applied_count': 0,
            'skipped_count': 0,
            'error_count': 0,
            'details': [],
        }

        for manual_input in manual_inputs:
            try:
                result = self._apply_single_override(run_id, manual_input)

                if result['applied']:
                    results['applied_count'] += 1
                    results['details'].append({
                        'input_id': manual_input.input_id,
                        'brand': manual_input.brand,
                        'model': manual_input.product_model,
                        'field_code': manual_input.field_code,
                        'status': 'applied',
                    })
                else:
                    results['skipped_count'] += 1
                    results['details'].append({
                        'input_id': manual_input.input_id,
                        'brand': manual_input.brand,
                        'model': manual_input.product_model,
                        'field_code': manual_input.field_code,
                        'status': 'skipped',
                        'reason': result.get('reason', 'No matching spec record'),
                    })

            except Exception as e:
                results['error_count'] += 1
                logger.exception(
                    f"Error applying manual override",
                    extra={
                        "input_id": manual_input.input_id,
                        "run_id": run_id,
                    }
                )

        self.session.flush()

        logger.info(
            f"Manual override application completed",
            extra={
                "run_id": run_id,
                "applied_count": results['applied_count'],
                "skipped_count": results['skipped_count'],
                "error_count": results['error_count'],
            }
        )

        return results

    def _apply_single_override(
        self,
        run_id: str,
        manual_input: ManualInput,
    ) -> Dict[str, Any]:
        """
        Apply a single manual override to spec records.

        Args:
            run_id: Run identifier
            manual_input: ManualInput record

        Returns:
            Dictionary with application result
        """
        # Build query conditions
        conditions = [
            ProductSpecLong.run_id == run_id,
            ProductSpecLong.brand == manual_input.brand,
            ProductSpecLong.series_l1 == manual_input.series_l1,
            ProductSpecLong.series_l2 == manual_input.series_l2,
            ProductSpecLong.product_model == manual_input.product_model,
            ProductSpecLong.field_code == manual_input.field_code,
        ]

        # Find matching spec record
        spec_record = self.session.query(ProductSpecLong).filter(
            *conditions
        ).first()

        if not spec_record:
            return {
                'applied': False,
                'reason': 'No matching spec record found',
            }

        # Apply override
        spec_record.raw_value = manual_input.manual_value
        spec_record.normalized_value = manual_input.manual_value  # Manual value is already normalized
        spec_record.is_manual_override = True
        spec_record.updated_at = datetime.utcnow()

        logger.debug(
            f"Applied manual override",
            extra={
                "run_id": run_id,
                "input_id": manual_input.input_id,
                "brand": manual_input.brand,
                "model": manual_input.product_model,
                "field_code": manual_input.field_code,
                "operator": manual_input.operator,
            }
        )

        return {
            'applied': True,
        }

    def apply_override_for_spec(
        self,
        run_id: str,
        brand: str,
        series_l1: str,
        series_l2: str,
        product_model: str,
        field_code: str,
        manual_value: str,
        operator: str,
        reason: str,
    ) -> bool:
        """
        Apply a manual override to a specific spec record.

        Creates a new manual input record and immediately applies it.

        Args:
            run_id: Run identifier
            brand: Brand name
            series_l1: Series level 1
            series_l2: Series level 2
            product_model: Product model
            field_code: Field code
            manual_value: Manual value to set
            operator: Operator name
            reason: Reason for override

        Returns:
            True if applied, False if not found
        """
        import uuid

        # Create manual input record
        manual_input = ManualInput(
            input_id=str(uuid.uuid4()),
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

        self.session.add(manual_input)
        self.session.flush()

        # Apply override
        result = self._apply_single_override(run_id, manual_input)

        return result['applied']

    def revert_override(
        self,
        run_id: str,
        brand: str,
        product_model: str,
        field_code: str,
    ) -> bool:
        """
        Revert a manual override for a specific spec.

        Removes the manual override flag and deletes the manual input record.

        Args:
            run_id: Run identifier
            brand: Brand name
            product_model: Product model
            field_code: Field code

        Returns:
            True if reverted, False if not found
        """
        # Find matching spec record
        spec_record = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.brand == brand,
                ProductSpecLong.product_model == product_model,
                ProductSpecLong.field_code == field_code,
                ProductSpecLong.is_manual_override == True,
            )
        ).first()

        if not spec_record:
            return False

        # Remove override flag
        spec_record.is_manual_override = False
        spec_record.updated_at = datetime.utcnow()

        # Delete manual input record
        self.session.query(ManualInput).filter(
            and_(
                ManualInput.brand == brand,
                ManualInput.product_model == product_model,
                ManualInput.field_code == field_code,
            )
        ).delete()

        logger.info(
            f"Reverted manual override",
            extra={
                "run_id": run_id,
                "brand": brand,
                "model": product_model,
                "field_code": field_code,
            }
        )

        return True

    def get_overridden_specs(
        self,
        run_id: str,
    ) -> List[ProductSpecLong]:
        """
        Get all specification records with manual overrides for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of ProductSpecLong instances with overrides
        """
        results = self.session.query(ProductSpecLong).filter(
            and_(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.is_manual_override == True,
            )
        ).all()

        logger.debug(
            f"Retrieved overridden specs",
            extra={
                "run_id": run_id,
                "count": len(results),
            }
        )

        return results

    def get_override_audit_trail(
        self,
        run_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail of all manual overrides for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of dictionaries with override details
        """
        # Get all overridden specs
        overridden_specs = self.get_overridden_specs(run_id)

        # Get matching manual inputs
        audit_trail = []

        for spec in overridden_specs:
            # Find matching manual input
            manual_input = self.session.query(ManualInput).filter(
                and_(
                    ManualInput.brand == spec.brand,
                    ManualInput.series_l1 == spec.series_l1,
                    ManualInput.series_l2 == spec.series_l2,
                    ManualInput.product_model == spec.product_model,
                    ManualInput.field_code == spec.field_code,
                )
            ).first()

            if manual_input:
                audit_trail.append({
                    'run_id': run_id,
                    'brand': spec.brand,
                    'series_l1': spec.series_l1,
                    'series_l2': spec.series_l2,
                    'product_model': spec.product_model,
                    'field_code': spec.field_code,
                    'previous_value': spec.raw_value if not spec.is_manual_override else 'N/A',
                    'current_value': manual_input.manual_value,
                    'operator': manual_input.operator,
                    'reason': manual_input.reason,
                    'applied_at': spec.updated_at.isoformat() if spec.updated_at else None,
                })

        return audit_trail

    def batch_apply_overrides(
        self,
        run_id: str,
        overrides: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Apply a batch of manual overrides.

        Args:
            run_id: Run identifier
            overrides: List of override dictionaries with keys:
                brand, series_l1, series_l2, product_model, field_code,
                manual_value, operator, reason

        Returns:
            Dictionary with batch results
        """
        logger.info(
            f"Applying batch manual overrides",
            extra={
                "run_id": run_id,
                "batch_size": len(overrides),
            }
        )

        results = {
            'applied_count': 0,
            'skipped_count': 0,
            'error_count': 0,
        }

        for override in overrides:
            try:
                # Validate required fields
                required_fields = [
                    'brand', 'series_l1', 'series_l2', 'product_model',
                    'field_code', 'manual_value', 'operator', 'reason'
                ]

                if not all(field in override for field in required_fields):
                    results['skipped_count'] += 1
                    continue

                applied = self.apply_override_for_spec(
                    run_id=run_id,
                    brand=override['brand'],
                    series_l1=override['series_l1'],
                    series_l2=override['series_l2'],
                    product_model=override['product_model'],
                    field_code=override['field_code'],
                    manual_value=override['manual_value'],
                    operator=override['operator'],
                    reason=override['reason'],
                )

                if applied:
                    results['applied_count'] += 1
                else:
                    results['skipped_count'] += 1

            except Exception as e:
                results['error_count'] += 1
                logger.exception(
                    f"Error applying batch override",
                    extra={"run_id": run_id}
                )

        self.session.flush()

        logger.info(
            f"Batch override application completed",
            extra={
                "run_id": run_id,
                "applied_count": results['applied_count'],
                "skipped_count": results['skipped_count'],
                "error_count": results['error_count'],
            }
        )

        return results
