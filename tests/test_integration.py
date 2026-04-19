"""
Integration tests for the competitor scraping system.

These tests verify end-to-end functionality across multiple modules.
"""

import pytest
from datetime import datetime

from src.pipeline import run_manual_pipeline
from src.storage.db import get_session
from src.storage.schema import RunSummary, ProductCatalog, ProductSpecLong
from src.core.constants import Brand, ScheduleType


@pytest.mark.integration
class TestEndToEndPipeline:
    """Test the complete pipeline from start to finish."""

    def test_manual_pipeline_hikvision_sample(self):
        """Test manual pipeline execution with small Hikvision sample."""
        run_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run pipeline with single brand, limited series
        result = run_manual_pipeline(
            run_id=run_id,
            brands=["hikvision"],
            schedule_type="manual",
            config_overrides={
                "brands": {
                    "hikvision": {
                        "series_l1_allowlist": ["Pro"]  # Only Pro series
                    }
                },
                "crawler": {
                    "concurrent_requests": 2,  # Low concurrency for testing
                    "cache_enabled": True
                }
            }
        )

        # Verify run completed successfully
        with get_session() as session:
            run_summary = session.query(RunSummary).filter_by(run_id=run_id).first()
            assert run_summary is not None
            assert run_summary.status == "completed"

            # Verify catalog entries
            catalog_count = session.query(ProductCatalog).filter_by(
                run_id=run_id,
                brand="HIKVISION"
            ).count()
            assert catalog_count > 0, "Should have discovered products"

            # Verify spec records
            spec_count = session.query(ProductSpecLong).filter_by(
                run_id=run_id,
                brand="HIKVISION"
            ).count()
            assert spec_count > 0, "Should have extracted specs"

    def test_manual_pipeline_dahua_sample(self):
        """Test manual pipeline execution with small Dahua sample."""
        run_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run pipeline with single brand, limited series
        result = run_manual_pipeline(
            run_id=run_id,
            brands=["dahua"],
            schedule_type="manual",
            config_overrides={
                "brands": {
                    "dahua": {
                        "series_keywords_allowlist": ["WizSense 3"]
                    }
                },
                "crawler": {
                    "concurrent_requests": 2
                }
            }
        )

        # Verify run completed
        with get_session() as session:
            run_summary = session.query(RunSummary).filter_by(run_id=run_id).first()
            assert run_summary is not None
            assert run_summary.status == "completed"


@pytest.mark.integration
class TestStorageIntegration:
    """Test database operations and integration."""

    def test_hierarchy_storage(self):
        """Test hierarchy snapshot storage and retrieval."""
        from src.storage.repo_hierarchy import HierarchyRepository
        from src.core.types import HierarchyNode
        from datetime import datetime

        with get_session() as session:
            repo = HierarchyRepository(session)
            run_id = "test_hierarchy_storage"

            # Create test hierarchy node
            node = HierarchyNode(
                brand="HIKVISION",
                series_l1="Pro",
                series_l2="EasyIP 4.0",
                source="sitemap",
                status="active",
                discovered_at=datetime.utcnow()
            )

            # Save hierarchy
            repo.save_hierarchy(run_id, [node])

            # Retrieve hierarchy
            retrieved = repo.get_by_run_id(run_id)
            assert len(retrieved) == 1
            assert retrieved[0].brand == "HIKVISION"
            assert retrieved[0].series_l1 == "Pro"

    def test_spec_storage_with_override(self):
        """Test spec storage with manual override."""
        from src.storage.repo_specs import SpecRepository
        from src.core.types import SpecRecord
        from datetime import datetime

        with get_session() as session:
            repo = SpecRepository(session)
            run_id = "test_spec_override"

            # Create initial spec
            spec1 = SpecRecord(
                run_id=run_id,
                brand="DAHUA",
                series_l1="WizSense 3",
                series_l2="Bullet",
                model="IPC-HFW1230",
                field_code="max_resolution",
                raw_value="4K",
                normalized_value="3840x2160",
                unit="px",
                source_url="https://example.com",
                confidence=0.9
            )

            # Save initial spec
            repo.save_specs(run_id, [spec1])

            # Create manual override
            spec2 = SpecRecord(
                run_id=run_id,
                brand="DAHUA",
                series_l1="WizSense 3",
                series_l2="Bullet",
                model="IPC-HFW1230",
                field_code="max_resolution",
                raw_value="Manual Entry",
                normalized_value="4000x3000",
                unit="px",
                source_url="manual",
                confidence=1.0
            )

            # Apply override
            repo.update_spec_with_override(run_id, "DAHUA", "IPC-HFW1230", "max_resolution", spec2)

            # Verify override applied
            retrieved = repo.get_specs_by_model(run_id, "DAHUA", "IPC-HFW1230")
            max_res_spec = [s for s in retrieved if s.field_code == "max_resolution"][0]
            assert max_res_spec.normalized_value == "4000x3000"
            assert max_res_spec.is_manual_override is True


@pytest.mark.integration
class TestExtractorIntegration:
    """Test extractor integration with real HTML."""

    def test_extract_from_sample_html(self):
        """Test extraction from sample HTML file."""
        from src.extractor import SpecExtractor, FieldRegistry
        from bs4 import BeautifulSoup

        # Load sample HTML (you would create this file)
        # with open('tests/fixtures/hikvision_sample.html') as f:
        #     html = f.read()

        # For now, use minimal HTML
        html = """
        <html>
        <body>
        <table>
        <tr><th>Image Sensor</th><td>1/2.8" Progressive Scan CMOS</td></tr>
        <tr><th>Max. Resolution</th><td>2688 x 1520</td></tr>
        <tr><th>Lens Type</th><td>Fixed focal</td></tr>
        </table>
        </body>
        </html>
        """

        extractor = SpecExtractor()
        results, warnings = extractor.extract_all_fields(
            html=html,
            url="https://test.example.com/product"
        )

        # Verify extraction
        assert "image_sensor" in results
        assert "max_resolution" in results
        assert "lens_type" in results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
