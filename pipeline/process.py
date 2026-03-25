"""Processing pipeline — batch items through the LLM taste filter."""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from pipeline.llm.base import LLMProvider, ProcessedResult

logger = logging.getLogger(__name__)

# Defaults — override via env vars or CLI args
DEFAULT_MAX_ITEMS = 50      # Max items to process per pipeline run
DEFAULT_BATCH_SIZE = 15     # Items per LLM call


def get_llm_provider() -> LLMProvider:
    """Create the configured LLM provider based on environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    if provider == "google":
        from pipeline.llm.google_provider import GoogleProvider
        return GoogleProvider()
    elif provider == "anthropic":
        from pipeline.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider == "openai":
        from pipeline.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use 'google', 'anthropic', or 'openai'.")


def run_process(
    db: sqlite3.Connection,
    llm: LLMProvider | None = None,
    max_items: int | None = None,
    batch_size: int | None = None,
):
    """Process unprocessed raw items in batches through the LLM taste filter."""
    if llm is None:
        llm = get_llm_provider()

    max_items = max_items or int(os.environ.get("PIPELINE_MAX_ITEMS", DEFAULT_MAX_ITEMS))
    batch_size = batch_size or int(os.environ.get("PIPELINE_BATCH_SIZE", DEFAULT_BATCH_SIZE))

    # Find raw items that haven't been processed yet
    unprocessed = db.execute("""
        SELECT r.id, r.title, r.url, r.raw_content, r.source_name
        FROM raw_items r
        LEFT JOIN processed_items p ON p.raw_item_id = r.id
        WHERE p.id IS NULL
        ORDER BY r.fetched_at DESC
        LIMIT ?
    """, [max_items]).fetchall()

    logger.info(f"Found {len(unprocessed)} unprocessed items (max_items={max_items}, batch_size={batch_size})")

    if not unprocessed:
        return 0, 0

    # Build item dicts for batching
    all_items = []
    for row in unprocessed:
        all_items.append({
            "id": row[0],
            "title": row[1] or "",
            "url": row[2] or "",
            "content": row[3] or "",
            "source": row[4] or "",
        })

    processed_count = 0
    error_count = 0

    # Process in batches
    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} items)...")

        try:
            results = llm.process_batch(batch)
            # Map results by id for reliable matching
            results_by_id = {}
            for r in results:
                rid = r.get("id")
                if rid is not None:
                    results_by_id[int(rid)] = r

            for item in batch:
                raw_id = item["id"]
                result_data = results_by_id.get(raw_id)
                if result_data is None:
                    logger.warning(f"No result returned for raw_item {raw_id}: {item['title'][:60]}")
                    error_count += 1
                    continue
                try:
                    result = ProcessedResult(
                        summary=result_data["summary"],
                        relevance_score=int(result_data["relevance_score"]),
                        hype_score=int(result_data["hype_score"]),
                        teaching_angle=result_data.get("teaching_angle"),
                        key_stats=result_data.get("key_stats", []),
                        tags=result_data.get("tags", []),
                        verdict=result_data["verdict"],
                        reasoning=result_data["reasoning"],
                    )
                    _store_result(db, raw_id, result)
                    processed_count += 1
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Bad result data for raw_item {raw_id}: {e}")
                    error_count += 1

        except json.JSONDecodeError as e:
            logger.error(f"Malformed LLM batch response: {e}")
            error_count += len(batch)
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            error_count += len(batch)

    logger.info(f"Processing complete: {processed_count} processed, {error_count} errors")
    return processed_count, error_count


def process_single_item(db: sqlite3.Connection, raw_item_id: int, llm: LLMProvider | None = None):
    """Process a single raw item (used for manual URL submissions via admin UI)."""
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
