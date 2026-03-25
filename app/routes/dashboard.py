"""Dashboard routes — CEO's main view."""

from __future__ import annotations

from datetime import datetime, date

from flask import Blueprint, render_template, request

from app.database import get_db
from app.models import get_dashboard_items, count_dashboard_items, get_all_tags, get_all_sources

bp = Blueprint("dashboard", __name__)

PER_PAGE = 30


def _parse_verdict_filter(verdict_param: str) -> list[str] | None:
    """Convert URL param into verdict list."""
    if verdict_param == "high":
        return ["high_signal"]
    elif verdict_param == "all":
        return None  # No filter
    else:
        # Default: high + medium
        return ["high_signal", "medium_signal"]


@bp.route("/")
@bp.route("/dashboard")
def dashboard():
    db = get_db()
    page = request.args.get("page", 1, type=int)
    verdict_param = request.args.get("verdict", "high_medium")
    tag = request.args.get("tag", "") or None
    source = request.args.get("source", "") or None
    date_from = request.args.get("date_from", "") or None
    date_to = request.args.get("date_to", "") or None

    verdict_filter = _parse_verdict_filter(verdict_param)

    items = get_dashboard_items(
        db,
        verdict_filter=verdict_filter,
        tag_filter=tag,
        source_filter=source,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=PER_PAGE,
    )

    total = count_dashboard_items(
        db,
        verdict_filter=verdict_filter,
        tag_filter=tag,
        source_filter=source,
        date_from=date_from,
        date_to=date_to,
    )
    has_more = (page * PER_PAGE) < total

    # Build query string for pagination links
    query_parts = []
    if verdict_param != "high_medium":
        query_parts.append(f"verdict={verdict_param}")
    if tag:
        query_parts.append(f"tag={tag}")
    if source:
        query_parts.append(f"source={source}")
    if date_from:
        query_parts.append(f"date_from={date_from}")
    if date_to:
        query_parts.append(f"date_to={date_to}")
    query_string = "&".join(query_parts)

    all_tags = get_all_tags(db)
    all_sources = get_all_sources(db)

    return render_template(
        "dashboard.html",
        items=items,
        view="dashboard",
        page=page,
        has_more=has_more,
        query_string=query_string,
        now=datetime.now(),
        current_verdict=verdict_param,
        current_tag=tag or "",
        current_source=source or "",
        current_date_from=date_from or "",
        current_date_to=date_to or "",
        all_tags=all_tags,
        all_sources=all_sources,
        bookmarked_only=False,
    )


@bp.route("/dashboard/bookmarks")
def bookmarks():
    db = get_db()
    page = request.args.get("page", 1, type=int)

    items = get_dashboard_items(db, bookmarked_only=True, page=page, per_page=PER_PAGE)
    total = count_dashboard_items(db, bookmarked_only=True)
    has_more = (page * PER_PAGE) < total

    all_tags = get_all_tags(db)
    all_sources = get_all_sources(db)

    return render_template(
        "dashboard.html",
        items=items,
        view="dashboard",
        page=page,
        has_more=has_more,
        query_string="",
        now=datetime.now(),
        current_verdict="all",
        current_tag="",
        current_source="",
        current_date_from="",
        current_date_to="",
        all_tags=all_tags,
        all_sources=all_sources,
        bookmarked_only=True,
    )
