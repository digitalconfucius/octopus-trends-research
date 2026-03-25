"""Processing pipeline — run raw items through the LLM taste filter."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time

from pipeline.llm.base import LLMProvider, ProcessedResult
from pipeline.llm.anthropic_provider import AnthropicProvider
from pipeline.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    """Create the configured LLM provider based on environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        return AnthropicProvider()
    elif provider == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use 'anthropic' or 'openai'.")


def run_process(db: sqlite3.Connection, llm: LLMProvider | None = None):
    """Process all unprocessed raw items through the LLM taste filter."""
    if llm is None:
        llm = get_llm_provider()

    # Find raw items that haven't been processed yet
    unprocessed = db.execute("""
        SELECT r.id, r.title, r.url, r.raw_content, r.source_name
        FROM raw_items r
        LEFT JOIN processed_items p ON p.raw_item_id = r.id
        WHERE p.id IS NULL
        ORDER BY r.fetched_at DESC
    """).fetchall()

    logger.info(f"Found {len(unprocessed)} unprocessed items")

    processed_count = 0
    error_count = 0

    for row in unprocessed:
        raw_id = row[0]
        title = row[1]
        url = row[2] or ""
        content = row[3] or ""
        source = row[4]

        try:
            logger.info(f"Processing: {title[:80]}...")
            result = llm.process_item(title=title, content=content, source=source, url=url)
            _store_result(db, raw_id, result)
            processed_count += 1
            time.sleep(0.5)  # Basic rate limiting between LLM calls
        except json.JSONDecodeError as e:
            logger.error(f"Malformed LLM response for raw_item {raw_id}: {e}")
            error_count += 1
            continue
        except Exception as e:
            logger.error(f"Failed to process raw_item {raw_id}: {e}")
            error_count += 1
            continue

    logger.info(f"Processing complete: {processed_count} processed, {error_count} errors")
    return processed_count, error_count


def process_single_item(db: sqlite3.Connection, raw_item_id: int, llm: LLMProvider | None = None):
    """Process a single raw item (used for manual URL submissions)."""
    if llm is None:
        llm = get_llm_provider()

    row = db.execute(
        "SELECT id, title, url, raw_content, source_name FROM raw_items WHERE id = ?",
        [raw_item_id],
    ).fetchone()

    if row is None:
        raise ValueError(f"Raw item {raw_item_id} not found")

    result = llm.process_item(
        title=row[1],
        content=row[3] or "",
        source=row[4],
        url=row[2] or "",
    )
    _store_result(db, raw_item_id, result)
    return result


def _store_result(db: sqlite3.Connection, raw_item_id: int, result: ProcessedResult):
    """Insert a ProcessedResult into the processed_items table."""
    db.execute(
        """INSERT INTO processed_items
           (raw_item_id, summary, relevance_score, hype_score, teaching_angle, key_stats, tags, verdict, llm_reasoning)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            raw_item_id,
            result.summary,
            result.relevance_score,
            result.hype_score,
            result.teaching_angle,
            json.dumps(result.key_stats),
            json.dumps(result.tags),
            result.verdict,
            result.reasoning,
        ],
    )
    db.commit()
