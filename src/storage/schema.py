"""
Database schema definitions for SQLite.

This module defines the ORM models for SQLite using SQLAlchemy.
All tables are designed to support the competition analysis system's
data storage needs with proper indexing for performance.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Integer, Float, Boolean, Text,
    Index, ForeignKey, create_engine, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class HierarchySnapshot(Base):
    """
    Snapshot of series hierarchy at a point in time.

    This table stores the discovered hierarchy structure (brand, series levels)
    for each run, enabling tracking of changes over time.
    """
    __tablename__ = 'hierarchy_snapshot'

    # Primary key is composite of run_id and hierarchy path
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    series_l1 = Column(String(200), nullable=True, index=True)
    series_l2 = Column(String(200), nullable=True, index=True)
    series_source = Column(String(100), nullable=False)  # e.g., 'sitemap', 'catalog'
    series_status = Column(String(50), nullable=False)  # 'active', 'discontinued', 'unknown'
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_hierarchy_run_brand', 'run_id', 'brand'),
        Index('idx_hierarchy_brand_series', 'brand', 'series_l1', 'series_l2'),
    )


class ProductCatalog(Base):
    """
    Product catalog entries.

    This table stores discovered products with their metadata.
    Supports tracking product lifecycle (first_seen, last_seen, status).
    """
    __tablename__ = 'product_catalog'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    series_l1 = Column(String(200), nullable=True)
    series_l2 = Column(String(200), nullable=True)
    product_model = Column(String(200), nullable=False, index=True)
    product_name = Column(String(500), nullable=False)
    product_url = Column(String(1000), nullable=False)
    locale = Column(String(20), nullable=False, default='en-US')
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    catalog_status = Column(String(50), nullable=False, default='current')  # 'current', 'discontinued', 'replaced'

    # Unique constraint on run_id + product_model to prevent duplicates
    # Indexes for common queries
    __table_args__ = (
        Index('idx_catalog_run_model', 'run_id', 'product_model'),
        Index('idx_catalog_brand_series', 'brand', 'series_l1', 'series_l2'),
        Index('idx_catalog_status', 'catalog_status', 'last_seen_at'),
    )


class ProductSpecLong(Base):
    """
    Product specifications in long format (one row per field).

    This normalized schema allows flexible spec storage with support for
    manual overrides and confidence tracking.
    """
    __tablename__ = 'product_specs_long'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    series_l1 = Column(String(200), nullable=True)
    series_l2 = Column(String(200), nullable=True)
    product_model = Column(String(200), nullable=False, index=True)
    field_code = Column(String(100), nullable=False, index=True)
    field_name = Column(String(200), nullable=False)
    raw_value = Column(Text, nullable=False)
    normalized_value = Column(String(500), nullable=True)
    unit = Column(String(50), nullable=True)  # e.g., 'px', 'm', 'f', 'MP'
    value_type = Column(String(50), nullable=False)  # 'string', 'numeric', 'boolean', 'enum', 'list', 'range'
    source_url = Column(String(1000), nullable=False)
    extract_confidence = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    is_manual_override = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_specs_run_model', 'run_id', 'product_model'),
        Index('idx_specs_model_field', 'product_model', 'field_code'),
        Index('idx_specs_brand_series', 'brand', 'series_l1', 'series_l2', 'field_code'),
        Index('idx_specs_override', 'is_manual_override', 'updated_at'),
    )


class ManualInput(Base):
    """
    Manual overrides and corrections.

    This table stores human-provided corrections that override extracted values,
    providing an audit trail of all manual interventions.
    """
    __tablename__ = 'manual_inputs'

    input_id = Column(String(50), primary_key=True)  # UUID
    brand = Column(String(100), nullable=False, index=True)
    series_l1 = Column(String(200), nullable=True)
    series_l2 = Column(String(200), nullable=True)
    product_model = Column(String(200), nullable=True, index=True)  # NULL if series-level override
    field_code = Column(String(100), nullable=False, index=True)
    manual_value = Column(Text, nullable=False)
    operator = Column(String(100), nullable=False)  # Who made the change
    reason = Column(Text, nullable=False)  # Why the change was made
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_manual_brand_field', 'brand', 'field_code'),
        Index('idx_manual_product', 'product_model', 'field_code'),
    )


class DataQualityIssue(Base):
    """
    Data quality issues detected during processing.

    This table tracks all quality issues for resolution workflow.
    Issues can be filtered by severity, status, and owner.
    """
    __tablename__ = 'data_quality_issues'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    series_l1 = Column(String(200), nullable=True)
    series_l2 = Column(String(200), nullable=True)
    product_model = Column(String(200), nullable=True, index=True)
    issue_type = Column(String(100), nullable=False, index=True)  # e.g., 'missing_field', 'parse_failed', 'value_abnormal'
    field_code = Column(String(100), nullable=True, index=True)  # NULL if not field-specific
    issue_detail = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # 'critical', 'high', 'medium', 'low', 'info'
    status = Column(String(50), nullable=False, default='open', index=True)  # 'open', 'in_progress', 'resolved', 'ignored', 'false_positive'
    owner = Column(String(100), nullable=True, index=True)  # Who is responsible for fixing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_issues_run_severity', 'run_id', 'severity'),
        Index('idx_issues_status_owner', 'status', 'owner'),
        Index('idx_issues_brand_type', 'brand', 'issue_type'),
    )


class RunSummary(Base):
    """
    Summary of each run execution.

    This table provides high-level metrics and status for each run,
    useful for monitoring and trend analysis.
    """
    __tablename__ = 'run_summary'

    run_id = Column(String(50), primary_key=True)
    schedule_type = Column(String(50), nullable=False)  # 'manual', 'hourly', 'daily', 'weekly'
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    catalog_count = Column(Integer, nullable=False, default=0)
    spec_field_count = Column(Integer, nullable=False, default=0)
    issue_count = Column(Integer, nullable=False, default=0)
    new_series_count = Column(Integer, nullable=False, default=0)
    disappeared_series_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    status = Column(String(50), nullable=False, default='running')  # 'running', 'completed', 'failed', 'cancelled'

    # Indexes for common queries
    __table_args__ = (
        Index('idx_runs_started', 'started_at'),
        Index('idx_runs_status', 'status', 'started_at'),
    )
