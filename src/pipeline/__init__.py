"""
OpenClaw DAG pipeline and task modules.

This package provides the main DAG and tasks for the competitor scraping system.
"""

from src.pipeline.dag import (
    create_competitor_scraping_dag,
    register_dag,
    run_manual_pipeline,
)

__all__ = [
    'create_competitor_scraping_dag',
    'register_dag',
    'run_manual_pipeline',
]
