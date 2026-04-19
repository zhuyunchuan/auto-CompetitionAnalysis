#!/usr/bin/env python3
"""
Full Dahua collection using saved HTML files (simplified version).

This script demonstrates the complete pipeline using previously saved HTML files.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.types import CatalogItem
from src.extractor.spec_extractor import SpecExtractor
from src.storage.db import init_database, get_database
from src.storage.schema import ProductCatalog, ProductSpecLong, RunSummary
from src.export.excel_writer import ExcelWriter


# Direct mapping of models to their HTML files
WIZSENSE_3_PRODUCTS = [
    ("IPC-HFW3541E-LED", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3541e-led"),
    ("IPC-HDBW3541E-LED", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hdbw3541e-led"),
    ("IPC-HFW3542T", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw3542t"),
    ("IPC-HDBW3542T", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hdbw3542t"),
    ("IPC-HFW4431E-LED", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hfw4431e-led"),
    ("IPC-HDBW4431E-LED", "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series/ipc-hdbw4431e-led"),
]

# Map file names to models
HTML_FILE_MAPPING = {
    "https___www.dahuasecurity.com_products_network-products_network-cameras_wizsense-3-series_ipc-hfw3541e-led.html": "IPC-HFW3541E-LED",
    "https___www.dahuasecurity.com_products_network-products_network-cameras_wizsense-3-series_ipc-hdbw3541e-led.html": "IPC-HDBW3541E-LED",
    "https___www.dahuasecurity.com_products_network-products_network-cameras_wizsense-3-series_ipc-hfw3542t.html": "IPC-HFW3542T",
    "https___www.dahuasecurity.com_products_network-products/network-cameras_wizsense-3-series_ipc-hdbw3542t.html": "IPC-HDBW3542T",
    "https___www.dahuasecurity.com_products_network-products/network-cameras_wizsense-3-series_ipc-hfw4431e-led.html": "IPC-HFW4431E-LED",
    "https___www.dahuasecurity.com_products_network-products/network-cameras_wizsense-3-series_ipc-hdbw4431e-led.html": "IPC-HDBW4431E-LED",
}


def generate_run_id() -> str:
    """Generate run ID in format YYYYMMDD_<type>_<sequence>."""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    return f"{date_str}_manual_03"


def main():
    """Main execution function."""
    print("=" * 80)
    print("Dahua WizSense 3 Collection from Saved HTML")
    print("=" * 80)

    # Configuration
    run_id = generate_run_id()
    db_path = "data/db/competition.db"
    artifact_dir = Path("data/artifacts")
    raw_html_dir = Path("data/raw_html/20260419_035458_manual")

    print(f"\nRun ID: {run_id}")
    print(f"Database: {db_path}")
    print(f"Output directory: {artifact_dir}")
    print(f"HTML source: {raw_html_dir}")

    # Step 1: Initialize database
    print("\n[1/6] Initializing database...")
    try:
        db = init_database(db_path=db_path, echo=False)
        print("   ✓ Database initialized successfully")
    except Exception as e:
        print(f"   ✗ Failed to initialize database: {e}")
        return

    # Step 2: Load products from saved HTML
    print("\n[2/6] Loading products from saved HTML...")
    try:
        unique_products = []

        # List all HTML files in the directory
        html_files = list(raw_html_dir.glob("*.html"))
        print(f"   Found {len(html_files)} HTML files")

        for html_file in html_files:
            # Check if this file matches one of our target products
            filename = html_file.name
            if filename in HTML_FILE_MAPPING:
                model = HTML_FILE_MAPPING[filename]
                # Find the URL for this model
                url = None
                for m, u in WIZSENSE_3_PRODUCTS:
                    if m == model:
                        url = u
                        break

                if url:
                    print(f"   Found HTML for {model}: {filename}")
                    unique_products.append((model, url, str(html_file)))

        print(f"\n   Total products with HTML: {len(unique_products)}")

        if not unique_products:
            print("   ✗ No products found!")
            return

    except Exception as e:
        print(f"   ✗ Failed to load products: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Extract specifications
    print("\n[3/6] Extracting specifications from HTML files...")
    extractor = SpecExtractor()
    all_specs = []
    catalog_entries = []

    for i, (model, url, html_path) in enumerate(unique_products, 1):
        print(f"   [{i}/{len(unique_products)}] Extracting: {model}")

        try:
            # Read HTML from file
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()

            if not html:
                print(f"      ⚠ Empty HTML file, skipping...")
                continue

            # Create catalog item
            product = CatalogItem(
                brand="dahua",
                series_l1="WizSense 3 Series",
                series_l2="WizSense 3 Series",
                model=model,
                name=model,
                url=url,
                locale="en",
            )
            catalog_entries.append(product)

            # Extract all fields
            results, warnings = extractor.extract_all_fields(html, url)

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
            import traceback
            traceback.print_exc()
            continue

    print(f"\n   Total catalog entries: {len(catalog_entries)}")
    print(f"   Total spec records: {len(all_specs)}")

    # Step 4: Save to database
    print("\n[4/6] Saving to database...")
    try:
        with db.session() as session:
            # Clear previous run data if exists
            session.query(ProductSpecLong).filter(ProductSpecLong.run_id == run_id).delete()
            session.query(ProductCatalog).filter(ProductCatalog.run_id == run_id).delete()
            session.query(RunSummary).filter(RunSummary.run_id == run_id).delete()

            # Save catalog entries
            for product in catalog_entries:
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
            now = datetime.now()
            summary = RunSummary(
                run_id=run_id,
                schedule_type="manual",
                started_at=now,
                ended_at=now,
                catalog_count=len(catalog_entries),
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

    # Step 5: Load data for Excel export
    print("\n[5/6] Loading data from database...")
    try:
        with db.session() as session:
            catalog_entries_db = session.query(ProductCatalog).filter(
                ProductCatalog.run_id == run_id,
                ProductCatalog.brand == "dahua"
            ).all()

            spec_entries_db = session.query(ProductSpecLong).filter(
                ProductSpecLong.run_id == run_id,
                ProductSpecLong.brand == "dahua"
            ).all()

            summary_entry = session.query(RunSummary).filter(
                RunSummary.run_id == run_id
            ).first()

        print(f"   Loaded {len(catalog_entries_db)} catalog entries")
        print(f"   Loaded {len(spec_entries_db)} spec entries")

    except Exception as e:
        print(f"   ✗ Failed to load from database: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 6: Export Excel report
    print("\n[6/6] Exporting Excel report...")
    try:
        # Prepare data for Excel writer
        catalog_data = {"dahua": catalog_entries_db}
        spec_data = {"dahua": spec_entries_db}
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
        print(f"   File size: {output_path.stat().st_size / 1024:.2f} KB")

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
    print(f"Products collected: {len(catalog_entries)}")
    print(f"Spec fields extracted: {len(all_specs)}")
    print(f"Database: {db_path}")
    print(f"Excel report: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
