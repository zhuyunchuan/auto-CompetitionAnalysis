#!/usr/bin/env python3
"""
Manual pipeline execution script for competitor scraping system.

This script runs the complete pipeline with proper adapter configuration.
Uses the real DahuaAdapter with Playwright for JS-rendered pages.
"""

import os
import sys
import logging
from datetime import datetime
from src.pipeline.dag import run_manual_pipeline
from src.adapters.dahua_adapter import DahuaAdapter
from src.core.logging import get_logger

# Set database path to local directory (not /data)
os.environ['DB_PATH'] = 'data/db/competitor.db'

logger = get_logger(__name__)


def main():
    """Main entry point for manual pipeline execution."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Generate run_id
    now = datetime.utcnow()
    run_id = now.strftime('%Y%m%d_%H%M%S') + "_manual"

    logger.info(f"Starting pipeline execution: {run_id}")
    logger.info("=" * 60)

    # Initialize adapters with proper configuration
    # IMPORTANT: use_playwright=True is required for Dahua JS-rendered pages
    adapters = [
        DahuaAdapter(use_playwright=True)
    ]

    logger.info(f"Initialized {len(adapters)} adapter(s):")
    for adapter in adapters:
        logger.info(f"  - {adapter.__class__.__name__} (use_playwright={adapter.use_playwright})")

    # Optional: Run with limited series for testing
    # Uncomment to test with only one series:
    # adapters[0].TARGET_SERIES = ["WizSense 3 Series"]

    try:
        # Run the complete pipeline
        result = run_manual_pipeline(
            run_id=run_id,
            adapters=adapters,
            config={
                'max_workers': 3,  # Reduced for Playwright (needs more resources)
            }
        )

        # Check result
        if result['status'] == 'success':
            logger.info("=" * 60)
            logger.info(f"✅ Pipeline completed successfully!")
            logger.info(f"Run ID: {run_id}")
            logger.info(f"Duration: {result['duration_seconds']:.2f} seconds")
            logger.info("")
            logger.info("Task Results:")
            for task_name, task_result in result['task_results'].items():
                logger.info(f"  {task_name}: {task_result.get('status', 'N/A')}")
            logger.info("")
            logger.info("Next steps:")
            logger.info(f"  1. Check database: sqlite3 data/db/competition.db")
            logger.info(f"  2. View Excel report: ls -la data/artifacts/")
            logger.info(f"  3. View raw HTML: ls -la data/raw_html/{run_id}/")
            return 0
        else:
            logger.error("=" * 60)
            logger.error(f"❌ Pipeline failed: {result.get('error', 'Unknown error')}")
            return 1

    except Exception as e:
        logger.exception(f"Pipeline execution failed with exception: {e}")
        return 1
    finally:
        # Clean up Playwright browser
        for adapter in adapters:
            try:
                adapter.close()
            except Exception as e:
                logger.warning(f"Failed to close adapter: {e}")


if __name__ == "__main__":
    sys.exit(main())
