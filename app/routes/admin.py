"""Admin routes — ops curation queue."""

from datetime import datetime

from flask import Blueprint, render_template, request

from app.database import get_db
from app.models import get_admin_items

bp = Blueprint("admin", __name__)

PER_PAGE = 50


@bp.route("/admin")
def admin():
    db = get_db()
    page = request.args.get("page", 1, type=int)

    items = get_admin_items(db, page=page, per_page=PER_PAGE)

    # Simple count for has_more
    total_row = db.execute("SELECT COUNT(*) as cnt FROM processed_items").fetchone()
    total = total_row["cnt"]
    has_more = (page * PER_PAGE) < total

    return render_template(
        "admin.html",
        items=items,
        view="admin",
        page=page,
        has_more=has_more,
        query_string="",
        now=datetime.now(),
    )
