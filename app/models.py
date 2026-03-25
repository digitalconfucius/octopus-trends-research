"""Lightweight query helpers wrapping raw SQL. No ORM."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


# --- Data classes for type clarity ---

@dataclass
class RawItem:
    id: int
    source_name: str
    source_type: str
    external_id: str | None
    title: str
    url: str | None
    raw_content: str | None
    author: str | None
    fetched_at: str


@dataclass
class ProcessedItem:
    id: int
    raw_item_id: int
    summary: str
    relevance_score: int
    hype_score: int
    teaching_angle: str | None
    key_stats: list[str]
    tags: list[str]
    verdict: str
    llm_reasoning: str | None
    processed_at: str
    # Joined fields from raw_items
    title: str = ""
    url: str | None = None
    source_name: str = ""
    source_type: str = ""
    # Action state
    is_bookmarked: bool = False
    is_promoted: bool = False
    is_dismissed: bool = False


def _row_to_processed_item(row: sqlite3.Row) -> ProcessedItem:
    """Convert a joined query row into a ProcessedItem."""
    key_stats = json.loads(row["key_stats"]) if row["key_stats"] else []
    tags = json.loads(row["tags"]) if row["tags"] else []

    return ProcessedItem(
        id=row["id"],
        raw_item_id=row["raw_item_id"],
        summary=row["summary"],
        relevance_score=row["relevance_score"],
        hype_score=row["hype_score"],
        teaching_angle=row["teaching_angle"],
        key_stats=key_stats,
        tags=tags,
        verdict=row["verdict"],
        llm_reasoning=row["llm_reasoning"],
        processed_at=row["processed_at"],
        title=row["title"],
        url=row["url"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        is_bookmarked=bool(row["is_bookmarked"]) if "is_bookmarked" in row.keys() else False,
        is_promoted=bool(row["is_promoted"]) if "is_promoted" in row.keys() else False,
        is_dismissed=bool(row["is_dismissed"]) if "is_dismissed" in row.keys() else False,
    )


# --- Base query for processed items with raw_items join and action flags ---

_BASE_SELECT = """
    SELECT
        p.id, p.raw_item_id, p.summary, p.relevance_score, p.hype_score,
        p.teaching_angle, p.key_stats, p.tags, p.verdict, p.llm_reasoning,
        p.processed_at,
        r.title, r.url, r.source_name, r.source_type,
        COALESCE(MAX(CASE WHEN a.action = 'bookmarked' THEN 1 END), 0) AS is_bookmarked,
        COALESCE(MAX(CASE WHEN a.action = 'promoted' THEN 1 END), 0) AS is_promoted,
        COALESCE(MAX(CASE WHEN a.action = 'dismissed' THEN 1 END), 0) AS is_dismissed
    FROM processed_items p
    JOIN raw_items r ON p.raw_item_id = r.id
    LEFT JOIN item_actions a ON a.processed_item_id = p.id
"""

_GROUP_BY = "GROUP BY p.id"


def get_dashboard_items(
    db: sqlite3.Connection,
    verdict_filter: list[str] | None = None,
    tag_filter: str | None = None,
    source_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    bookmarked_only: bool = False,
    page: int = 1,
    per_page: int = 30,
) -> list[ProcessedItem]:
    """Fetch processed items for the CEO dashboard."""
    conditions = []
    params = []

    if bookmarked_only:
        conditions.append("a.action = 'bookmarked'")
    else:
        # Exclude dismissed items from CEO view
        conditions.append("""
            p.id NOT IN (
                SELECT processed_item_id FROM item_actions WHERE action = 'dismissed'
            )
        """)
        # Filter by verdict (or show promoted items regardless of verdict)
        if verdict_filter:
            placeholders = ",".join("?" for _ in verdict_filter)
            conditions.append(f"""
                (p.verdict IN ({placeholders})
                 OR p.id IN (SELECT processed_item_id FROM item_actions WHERE action = 'promoted'))
            """)
            params.extend(verdict_filter)

    if tag_filter:
        conditions.append("p.tags LIKE ?")
        params.append(f'%"{tag_filter}"%')

    if source_filter:
        conditions.append("r.source_name = ?")
        params.append(source_filter)

    if date_from:
        conditions.append("DATE(p.processed_at) >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("DATE(p.processed_at) <= ?")
        params.append(date_to)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    query = f"""
        {_BASE_SELECT}
        {where}
        {_GROUP_BY}
        ORDER BY p.processed_at DESC
        LIMIT ? OFFSET ?
    """

    rows = db.execute(query, params).fetchall()
    return [_row_to_processed_item(row) for row in rows]


def get_admin_items(
    db: sqlite3.Connection,
    page: int = 1,
    per_page: int = 50,
) -> list[ProcessedItem]:
    """Fetch ALL processed items for the ops admin queue."""
    offset = (page - 1) * per_page
    query = f"""
        {_BASE_SELECT}
        {_GROUP_BY}
        ORDER BY p.processed_at DESC
        LIMIT ? OFFSET ?
    """
    rows = db.execute(query, [per_page, offset]).fetchall()
    return [_row_to_processed_item(row) for row in rows]


def get_item_by_id(db: sqlite3.Connection, item_id: int) -> ProcessedItem | None:
    """Fetch a single processed item by ID."""
    query = f"""
        {_BASE_SELECT}
        WHERE p.id = ?
        {_GROUP_BY}
    """
    row = db.execute(query, [item_id]).fetchone()
    if row is None:
        return None
    return _row_to_processed_item(row)


def add_action(db: sqlite3.Connection, processed_item_id: int, action: str, acted_by: str, note: str | None = None):
    """Record an action on a processed item."""
    # Remove existing same-type action to allow toggling
    db.execute(
        "DELETE FROM item_actions WHERE processed_item_id = ? AND action = ? AND acted_by = ?",
        [processed_item_id, action, acted_by],
    )
    db.execute(
        "INSERT INTO item_actions (processed_item_id, action, acted_by, note) VALUES (?, ?, ?, ?)",
        [processed_item_id, action, acted_by, note],
    )
    db.commit()


def remove_action(db: sqlite3.Connection, processed_item_id: int, action: str, acted_by: str):
    """Remove an action (e.g., unbookmark)."""
    db.execute(
        "DELETE FROM item_actions WHERE processed_item_id = ? AND action = ? AND acted_by = ?",
        [processed_item_id, action, acted_by],
    )
    db.commit()


def get_all_sources(db: sqlite3.Connection) -> list[str]:
    """Get distinct source names from raw_items."""
    rows = db.execute("SELECT DISTINCT source_name FROM raw_items ORDER BY source_name").fetchall()
    return [row["source_name"] for row in rows]


def get_all_tags(db: sqlite3.Connection) -> list[str]:
    """Get all unique tags across processed items."""
    rows = db.execute("SELECT DISTINCT tags FROM processed_items WHERE tags IS NOT NULL").fetchall()
    all_tags = set()
    for row in rows:
        try:
            tags = json.loads(row["tags"])
            all_tags.update(tags)
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(all_tags)


def count_dashboard_items(
    db: sqlite3.Connection,
    verdict_filter: list[str] | None = None,
    tag_filter: str | None = None,
    source_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    bookmarked_only: bool = False,
) -> int:
    """Count items matching dashboard filters (for pagination)."""
    conditions = []
    params = []

    if bookmarked_only:
        conditions.append("a.action = 'bookmarked'")
    else:
        conditions.append("""
            p.id NOT IN (
                SELECT processed_item_id FROM item_actions WHERE action = 'dismissed'
            )
        """)
        if verdict_filter:
            placeholders = ",".join("?" for _ in verdict_filter)
            conditions.append(f"""
                (p.verdict IN ({placeholders})
                 OR p.id IN (SELECT processed_item_id FROM item_actions WHERE action = 'promoted'))
            """)
            params.extend(verdict_filter)

    if tag_filter:
        conditions.append("p.tags LIKE ?")
        params.append(f'%"{tag_filter}"%')

    if source_filter:
        conditions.append("r.source_name = ?")
        params.append(source_filter)

    if date_from:
        conditions.append("DATE(p.processed_at) >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("DATE(p.processed_at) <= ?")
        params.append(date_to)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT COUNT(DISTINCT p.id) as cnt
        FROM processed_items p
        JOIN raw_items r ON p.raw_item_id = r.id
        LEFT JOIN item_actions a ON a.processed_item_id = p.id
        {where}
    """
    row = db.execute(query, params).fetchone()
    return row["cnt"]
