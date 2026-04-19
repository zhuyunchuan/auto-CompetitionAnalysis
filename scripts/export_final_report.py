#!/usr/bin/env python3
"""
Export final Excel report for Phase 1.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, ".")
from src.export.excel_writer import ExcelWriter
from src.storage.schema import ProductCatalog, ProductSpecLong, DataQualityIssue, RunSummary

DB_PATH = "data/db/competition.db"
OUTPUT_DIR = "results"
RUN_ID = "20260420_phase1_final"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"=== Exporting Final Excel Report ===")
    print(f"Run ID: {RUN_ID}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Fetch catalog data by brand
    catalog_data = {}
    for brand in ['hikvision', 'dahua']:
        cur.execute("""
            SELECT brand, series_l1, series_l2, product_model, product_name,
                   product_url, catalog_status
            FROM product_catalog
            WHERE brand = ?
            ORDER BY series_l1, series_l2, product_model
        """, (brand,))
        rows = cur.fetchall()

        catalog_data[brand] = [
            ProductCatalog(
                brand=row['brand'],
                series_l1=row['series_l1'],
                series_l2=row['series_l2'],
                product_model=row['product_model'],
                product_name=row['product_name'],
                product_url=row['product_url'],
                locale="en",
                catalog_status=row['catalog_status'],
                first_seen_at=datetime.now(),
                last_seen_at=datetime.now(),
            )
            for row in rows
        ]
        print(f"{brand.capitalize()} catalog: {len(catalog_data[brand])} products")

    # Fetch spec data by brand
    spec_data = {}
    for brand in ['hikvision', 'dahua']:
        cur.execute("""
            SELECT brand, series_l1, series_l2, product_model, field_code, field_name,
                   raw_value, normalized_value, unit, extract_confidence, is_manual_override
            FROM product_specs_long
            WHERE brand = ?
            ORDER BY series_l1, series_l2, product_model, field_code
        """, (brand,))
        rows = cur.fetchall()

        spec_data[brand] = [
            ProductSpecLong(
                brand=row['brand'],
                series_l1=row['series_l1'],
                series_l2=row['series_l2'],
                product_model=row['product_model'],
                field_code=row['field_code'],
                field_name=row['field_name'],
                raw_value=row['raw_value'],
                normalized_value=row['normalized_value'],
                unit=row['unit'],
                value_type="text",
                source_url="",
                extract_confidence=row['extract_confidence'],
                is_manual_override=row['is_manual_override'],
                updated_at=datetime.now(),
            )
            for row in rows
        ]
        print(f"{brand.capitalize()} specs: {len(spec_data[brand])} records")

    # Fetch quality issues (empty for now)
    issues = []

    # Create run summary
    total_catalog = sum(len(catalog_data[b]) for b in catalog_data)
    total_specs = sum(len(spec_data[b]) for b in spec_data)

    # Calculate success rate
    products_with_specs = {}
    for brand in ['hikvision', 'dahua']:
        cur.execute("""
            SELECT COUNT(DISTINCT product_model)
            FROM product_specs_long
            WHERE brand = ?
        """, (brand,))
        products_with_specs[brand] = cur.fetchone()[0]

    success_rate = sum(products_with_specs.values()) / total_catalog if total_catalog > 0 else 0

    summary = RunSummary(
        run_id=RUN_ID,
        schedule_type="manual",
        started_at=datetime.now(),
        ended_at=datetime.now(),
        catalog_count=total_catalog,
        spec_field_count=total_specs,
        issue_count=0,
        new_series_count=0,
        disappeared_series_count=0,
        success_rate=success_rate,
        status="completed",
    )

    print()
    print("=== Run Summary ===")
    print(f"Total products: {total_catalog}")
    print(f"Total spec records: {total_specs}")
    print(f"Products with specs: {sum(products_with_specs.values())}")
    print(f"Success rate: {success_rate:.2%}")
    print()

    # Generate Excel report
    writer = ExcelWriter(output_dir=Path(OUTPUT_DIR))
    filepath = writer.generate_report(
        run_id=RUN_ID,
        catalog_data=catalog_data,
        spec_data=spec_data,
        issues=issues,
        summary=summary,
    )

    print(f"Excel report generated: {filepath}")
    print(f"File size: {filepath.stat().st_size / 1024:.1f} KB")

    # Cleanup
    conn.close()

    print(f"\nExport complete!")

if __name__ == "__main__":
    main()
