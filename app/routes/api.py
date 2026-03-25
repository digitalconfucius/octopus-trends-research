"""API routes — HTMX endpoints for card actions and manual item submission."""

import logging

from flask import Blueprint, render_template, request

from app.database import get_db
from app.models import get_item_by_id, add_action, remove_action
from pipeline.fetch import fetch_url_content
from pipeline.process import process_single_item

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/bookmark/<int:item_id>", methods=["POST"])
def bookmark(item_id):
    """Bookmark an item (CEO action)."""
    db = get_db()
    add_action(db, item_id, "bookmarked", "ceo")
    item = get_item_by_id(db, item_id)
    return render_template("components/card.html", item=item, view="dashboard")


@bp.route("/bookmark/<int:item_id>", methods=["DELETE"])
def unbookmark(item_id):
    """Remove bookmark from an item."""
    db = get_db()
    remove_action(db, item_id, "bookmarked", "ceo")
    item = get_item_by_id(db, item_id)
    return render_template("components/card.html", item=item, view="dashboard")


@bp.route("/promote/<int:item_id>", methods=["POST"])
def promote(item_id):
    """Promote an item to appear in CEO dashboard (ops action)."""
    db = get_db()
    add_action(db, item_id, "promoted", "ops")
    item = get_item_by_id(db, item_id)
    return render_template("components/card.html", item=item, view="admin")


@bp.route("/dismiss/<int:item_id>", methods=["POST"])
def dismiss(item_id):
    """Dismiss an item from CEO dashboard (ops action)."""
    db = get_db()
    add_action(db, item_id, "dismissed", "ops")
    item = get_item_by_id(db, item_id)
    return render_template("components/card.html", item=item, view="admin")


@bp.route("/add-url", methods=["POST"])
def add_url():
    """Add a URL — fetch content, insert into raw_items, run through LLM pipeline."""
    db = get_db()
    url = request.form.get("url", "").strip()

    if not url:
        return '<p class="text-sm text-red-500">Please provide a URL.</p>'

    try:
        # Fetch content from URL
        fetched = fetch_url_content(url)
        title = fetched["title"] or url
        content = fetched["content"]

        if not content:
            return (
                '<p class="text-sm text-amber-600">'
                'Could not extract content from URL. Try the manual entry form below.</p>'
            )

        # Insert into raw_items
        db.execute(
            """INSERT INTO raw_items (source_name, source_type, external_id, title, url, raw_content)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["manual", "manual", url, title, url, content],
        )
        db.commit()

        # Get the raw_item_id
        row = db.execute(
            "SELECT id FROM raw_items WHERE source_name = 'manual' AND external_id = ?",
            [url],
        ).fetchone()

        if row is None:
            return '<p class="text-sm text-red-500">Failed to insert item.</p>'

        # Process through LLM
        result = process_single_item(db, row["id"])

        return (
            f'<p class="text-sm text-emerald-600">'
            f'Added and processed: "{title[:60]}..." — verdict: {result.verdict}</p>'
        )

    except Exception as e:
        logger.error(f"Failed to add URL {url}: {e}")
        return (
            f'<p class="text-sm text-red-500">'
            f'Error processing URL: {e}. Try the manual entry form.</p>'
        )


@bp.route("/add-manual", methods=["POST"])
def add_manual():
    """Manually add an item with title + content."""
    db = get_db()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    url = request.form.get("url", "").strip() or None

    if not title:
        return '<p class="text-sm text-red-500">Title is required.</p>'

    try:
        external_id = url or f"manual-{title[:50]}"

        db.execute(
            """INSERT INTO raw_items (source_name, source_type, external_id, title, url, raw_content)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["manual", "manual", external_id, title, url, content or title],
        )
        db.commit()

        row = db.execute(
            "SELECT id FROM raw_items WHERE source_name = 'manual' AND external_id = ?",
            [external_id],
        ).fetchone()

        if row is None:
            return '<p class="text-sm text-red-500">Failed to insert item.</p>'

        result = process_single_item(db, row["id"])

        return (
            f'<p class="text-sm text-emerald-600">'
            f'Added: "{title[:60]}" — verdict: {result.verdict}</p>'
        )

    except Exception as e:
        logger.error(f"Failed to add manual item: {e}")
        return f'<p class="text-sm text-red-500">Error: {e}</p>'
