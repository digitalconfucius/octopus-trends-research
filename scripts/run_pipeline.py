#!/usr/bin/env python3
"""Entry point for the ingestion + processing pipeline.

Run manually:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --max-items 10    # Quick test run

Schedule via cron:
    0 6 * * * cd /path/to/project && .venv/bin/python scripts/run_pipeline.py >> logs/pipeline.log 2>&1
"""

import argparse
import logging
import os
import sys

# Add project root to path so imports work when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import get_db_connection, init_db
from pipeline.ingest import run_ingest
from pipeline.process import run_process

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the ingestion + processing pipeline")
    parser.add_argument("--max-items", type=int, default=None,
                        help="Max items to process (overrides PIPELINE_MAX_ITEMS env var)")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Items per LLM batch call (overrides PIPELINE_BATCH_SIZE env var)")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip ingestion, only process existing unprocessed items")
    args = parser.parse_args()

    db_path = os.environ.get("DATABASE_PATH", "data/dashboard.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)
    db = get_db_connection(db_path)

    try:
        logger.info("=" * 60)
        logger.info("Starting pipeline run")
        logger.info("=" * 60)

        # Step 1: Ingest from all sources
        if not args.skip_ingest:
            logger.info("--- INGESTION ---")
            new_items, skipped = run_ingest(db)
        else:
            logger.info("--- SKIPPING INGESTION ---")
            new_items = 0

        # Step 2: Process unprocessed items through LLM (batched)
        logger.info("--- PROCESSING ---")
        processed, errors = run_process(
            db,
            max_items=args.max_items,
            batch_size=args.batch_size,
        )

        logger.info("=" * 60)
        logger.info(f"Pipeline complete: {new_items} ingested, {processed} processed, {errors} errors")
        logger.info("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
