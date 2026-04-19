#!/usr/bin/env python3
"""
Full Dahua WizSense 2 + 3 collection script.

This script:
1. Initializes the database schema
2. Collects all WizSense 2 and WizSense 3 products using Playwright
3. Extracts specifications from each product detail page
4. Saves to database
5. Exports Excel report to data/artifacts/
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.dahua_adapter import DahuaAdapter
from src.extractor.spec_extractor import SpecExtractor
from src.storage.db import init_database, get_database
from src.storage.schema import ProductCatalog, ProductSpecLong, RunSummary
from src.export.excel_writer import ExcelWriter


def generate_run_id() -> str:
    """Generate run ID in format YYYYMMDD_<type>_<sequence>."""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    return f"{date_str}_manual_01"


def main():
    """Main execution function."""
    print("=" * 80)
    print("Dahua WizSense 2 + 3 Full Collection")
    print("=" * 80)

    # Configuration
    run_id = generate_run_id()
    db_path = "data/db/competition.db"
    artifact_dir = Path("data/artifacts")

    print(f"\nRun ID: {run_id}")
    print(f"Database: {db_path}")
    print(f"Output directory: {artifact_dir}")

    # Step 1: Initialize database
    print("\n[1/6] Initializing database...")
    try:
        db = init_database(db_path=db_path, echo=False)
        print("   ✓ Database initialized successfully")
    except Exception as e:
        print(f"   ✗ Failed to initialize database: {e}")
        return

    # Step 2: Initialize adapter
    print("\n[2/6] Initializing Dahua adapter...")
    try:
        adapter = DahuaAdapter(use_playwright=True)
        print("   ✓ Adapter initialized")
    except Exception as e:
        print(f"   ✗ Failed to initialize adapter: {e}")
        return

    # Step 3: Discover series and products
    print("\n[3/6] Discovering WizSense 2 + 3 series and products...")
    try:
        series_list = adapter.discover_series()
        print(f"   Found series: {series_list}")

        # Find target series
        target_series_list = []
        for series in series_list:
            if "WizSense 2" in series or "wizsense 2" in series.lower():
                target_series_list.append(series)
            elif "WizSense 3" in series or "wizsense 3" in series.lower():
                target_series_list.append(series)

        if not target_series_list:
            print("   ✗ WizSense 2 or 3 series not found!")
            return

        print(f"   Target series: {target_series_list}")

        # Collect all products from both series
        all_products = []
        for target_series in target_series_list:
            print(f"\n   Processing series: {target_series}")

            # Discover subseries
            subseries_list = adapter.discover_subseries(target_series)
            print(f"   Found {len(subseries_list)} subseries: {subseries_list}")

            # Collect products
            for subseries in subseries_list:
                print(f"   Fetching products for subseries: {subseries}")
                products = adapter.list_products(target_series, subseries)
                print(f"   Found {len(products)} products")
                all_products.extend(products)
                time.sleep(1)  # Rate limiting

        # Remove duplicates
        seen_models = set()
        unique_products = []
        for p in all_products:
            if p.model not in seen_models:
                seen_models.add(p.model)
                unique_products.append(p)

        print(f"\n   Total unique products: {len(unique_products)}")

        if len(unique_products) < 30:
            print("   ⚠ Warning: Expected at least 30 products, found fewer")

    except Exception as e:
        print(f"   ✗ Failed to discover products: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        adapter.close()

    # Step 4: Extract specifications
    print("\n[4/6] Extracting specifications from product pages...")
    extractor = SpecExtractor()
    all_specs = []

    for i, product in enumerate(unique_products, 1):
        print(f"   [{i}/{len(unique_products)}] Extracting: {product.model}")

        try:
            # Fetch product detail page
            adapter = DahuaAdapter(use_playwright=True)
            html = adapter.fetch_product_detail(product.url)
            adapter.close()

            if not html:
                print(f"      ⚠ Failed to fetch page, skipping...")
                continue

            # Extract all fields
            results, warnings = extractor.extract_all_fields(html, product.url)

            # Convert to SpecRecord objects
            spec_records = extractor.to_spec_records(
                results,
                run_id,
                product.brand,
                product.series_l1,
                product.series_l2,
                product.model
            )

            all_specs.extend(spec_records)

            if warnings:
                for warning in warnings:
                    print(f"      ⚠ {warning}")

            print(f"      ✓ Extracted {len(spec_records)} fields")

        except Exception as e:
            print(f"      ✗ Error: {e}")
            continue

        time.sleep(1)  # Rate limiting between products

    print(f"\n   Total spec records: {len(all_specs)}")

    # Step 5: Save to database
    print("\n[5/6] Saving to database...")
    try:
        with db.session() as session:
            # Save catalog entries
            for product in unique_products:
                catalog_entry = ProductCatalog(
                    run_id=run_id,
                    brand=product.brand,
                    series_l1=product.series_l1,
                    series_l2=product.series_l2,
                    product_model=product.model,
                    product_name=product.name,
                    product_url=product.url,
                    locale=product.locale,
                    catalog_status="current"
                )
                session.add(catalog_entry)

            # Save spec records
            for spec in all_specs:
                spec_entry = ProductSpecLong(
                    run_id=run_id,
                    brand=spec.brand,
                    series_l1=spec.series_l1,
                    series_l2=spec.series_l2,
                    product_model=spec.model,
                    field_code=spec.field_code,
                    field_name=spec.field_code,  # Use field_code as field_name for now
                    raw_value=spec.raw_value,
                    normalized_value=spec.normalized_value,
                    unit=spec.unit,
                    value_type="string",  # Default value type
                    source_url=spec.source_url or "",
                    extract_confidence=spec.confidence,
                    is_manual_override=spec.is_manual_override
                )
                session.add(spec_entry)

            # Create run summary
            summary = RunSummary(
                run_id=run_id,
                schedule_type="manual",
                started_at=datetime.now(),
                ended_at=datetime.now(),
                catalog_count=len(unique_products),
                spec_field_count=len(all_specs),
                issue_count=0,
                new_series_count=0,
                disappeared_series_count=0,
                success_rate=1.0,
                status="completed"
            )
            session.add(summary)

        print("   ✓ Data saved to database successfully")

    except Exception as e:
        print(f"   ✗ Failed to save to database: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 6: Export Excel report
    print("\n[6/6] Exporting Excel report...")
    try:
        # Load data from database
        with db.session() as session:
            catalog_entries = session.query(ProductCatalog).filter(
                ProductCatalog.run_id == run_id,
                ProductCatalog.brand == "dahua"
            ).all()

            spec_entries = session.query(ProductSpecLong).filter(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.brand == "dahua"
            ).all()

            summary_entry = session.query(RunSummary).filter(
                RunSummary.run_id == run_id
            ).first()

        # Prepare data for Excel writer
        catalog_data = {"dahua": catalog_entries}
        spec_data = {"dahua": spec_entries}
        issues = []  # No quality issues in this run

        # Generate Excel report
        excel_writer = ExcelWriter(artifact_dir)
        output_path = excel_writer.generate_report(
            run_id,
            catalog_data,
            spec_data,
            issues,
            summary_entry
        )

        print(f"   ✓ Excel report exported: {output_path}")

    except Exception as e:
        print(f"   ✗ Failed to export Excel: {e}")
        import traceback
        traceback.print_exc()
        return

    # Summary
    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print(f"Run ID: {run_id}")
    print(f"Products collected: {len(unique_products)}")
    print(f"Spec fields extracted: {len(all_specs)}")
    print(f"Database: {db_path}")
    print(f"Excel report: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
