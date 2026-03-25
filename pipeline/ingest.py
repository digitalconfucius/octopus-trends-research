"""Ingestion pipeline — fetch items from configured sources into raw_items."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timedelta

import feedparser
import httpx

from pipeline.sources import Source, load_sources

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "ResearchDashboard/1.0 (internal tool; contact: admin@example.com)"
}
TIMEOUT = 30


def run_ingest(db: sqlite3.Connection, sources: list[Source] | None = None):
    """Fetch items from all configured sources and insert into raw_items."""
    if sources is None:
        sources = load_sources()

    total_new = 0
    total_skipped = 0

    for source in sources:
        try:
            logger.info(f"Ingesting from {source.name} ({source.type})...")
            new, skipped = _ingest_source(db, source)
            total_new += new
            total_skipped += skipped
            logger.info(f"  {source.name}: {new} new, {skipped} duplicates")
            time.sleep(1)  # Basic rate limiting between sources
        except Exception as e:
            logger.error(f"  {source.name} FAILED: {e}")
            continue

    logger.info(f"Ingestion complete: {total_new} new items, {total_skipped} duplicates")
    return total_new, total_skipped


def _ingest_source(db: sqlite3.Connection, source: Source) -> tuple[int, int]:
    """Ingest items from a single source. Returns (new_count, skipped_count)."""
    if source.name.startswith("hackernews"):
        return _ingest_hackernews(db, source)
    elif source.name.startswith("reddit"):
        return _ingest_reddit(db, source)
    elif source.name == "github_trending":
        return _ingest_github(db, source)
    elif source.type == "rss":
        return _ingest_rss(db, source)
    else:
        logger.warning(f"Unknown source type for {source.name}: {source.type}")
        return 0, 0


# --- Hacker News ---

def _ingest_hackernews(db: sqlite3.Connection, source: Source) -> tuple[int, int]:
    """Fetch top/best stories from HN Firebase API."""
    resp = httpx.get(source.url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    story_ids = resp.json()[:source.fetch_limit]

    new = 0
    skipped = 0

    # Fetch stories in batches of 10
    for i in range(0, len(story_ids), 10):
        batch = story_ids[i:i + 10]
        for story_id in batch:
            try:
                item_resp = httpx.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    headers=HEADERS,
                    timeout=TIMEOUT,
                )
                item_resp.raise_for_status()
                item = item_resp.json()

                if not item or item.get("type") != "story":
                    continue

                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                external_id = str(story_id)
                author = item.get("by", "")
                content = item.get("text", "")  # For Ask HN / Show HN posts

                inserted = _insert_raw_item(
                    db, source.name, source.type, external_id, title, url, content, author
                )
                if inserted:
                    new += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Failed to fetch HN story {story_id}: {e}")
                continue

        if i + 10 < len(story_ids):
            time.sleep(0.5)  # Brief pause between batches

    db.commit()
    return new, skipped


# --- Reddit ---

def _ingest_reddit(db: sqlite3.Connection, source: Source) -> tuple[int, int]:
    """Fetch top posts from a subreddit via Reddit JSON API."""
    resp = httpx.get(
        source.url,
        headers={**HEADERS, "User-Agent": "ResearchDashboard/1.0"},
        timeout=TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()

    posts = data.get("data", {}).get("children", [])[:source.fetch_limit]

    new = 0
    skipped = 0

    for post in posts:
        post_data = post.get("data", {})
        title = post_data.get("title", "")
        url = post_data.get("url", "")
        external_id = post_data.get("id", "")
        author = post_data.get("author", "")
        content = post_data.get("selftext", "")

        # If it's a link post, use the URL; if self post, link to Reddit
        if post_data.get("is_self"):
            url = f"https://reddit.com{post_data.get('permalink', '')}"

        inserted = _insert_raw_item(
            db, source.name, "api", external_id, title, url, content, author
        )
        if inserted:
            new += 1
        else:
            skipped += 1

    db.commit()
    return new, skipped


# --- GitHub Trending ---

def _ingest_github(db: sqlite3.Connection, source: Source) -> tuple[int, int]:
    """Fetch trending repos from GitHub Search API."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = source.url.replace("{yesterday}", yesterday)

    resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    repos = data.get("items", [])[:source.fetch_limit]

    new = 0
    skipped = 0

    for repo in repos:
        title = f"{repo.get('full_name', '')} — {repo.get('description', '') or 'No description'}"
        repo_url = repo.get("html_url", "")
        external_id = str(repo.get("id", ""))
        author = repo.get("owner", {}).get("login", "")
        content = (
            f"Stars: {repo.get('stargazers_count', 0)}, "
            f"Language: {repo.get('language', 'N/A')}, "
            f"Created: {repo.get('created_at', '')}\n"
            f"{repo.get('description', '')}"
        )

        inserted = _insert_raw_item(
            db, source.name, source.type, external_id, title, repo_url, content, author
        )
        if inserted:
            new += 1
        else:
            skipped += 1

    db.commit()
    return new, skipped


# --- RSS Feeds ---

def _ingest_rss(db: sqlite3.Connection, source: Source) -> tuple[int, int]:
    """Fetch items from an RSS/Atom feed."""
    feed = feedparser.parse(source.url, agent=HEADERS["User-Agent"])

    entries = feed.entries[:source.fetch_limit]

    new = 0
    skipped = 0

    for entry in entries:
        title = entry.get("title", "")
        url = entry.get("link", "")
        external_id = entry.get("id", url)
        author = entry.get("author", "")
        content = entry.get("summary", "") or entry.get("description", "")

        inserted = _insert_raw_item(
            db, source.name, "rss", external_id, title, url, content, author
        )
        if inserted:
            new += 1
        else:
            skipped += 1

    db.commit()
    return new, skipped


# --- Shared insert helper ---

def _insert_raw_item(
    db: sqlite3.Connection,
    source_name: str,
    source_type: str,
    external_id: str,
    title: str,
    url: str,
    content: str | None,
    author: str | None,
) -> bool:
    """Insert a raw item, returning True if inserted, False if duplicate."""
    try:
        db.execute(
            """INSERT INTO raw_items (source_name, source_type, external_id, title, url, raw_content, author)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [source_name, source_type, external_id, title, url, content, author],
        )
        return True
    except sqlite3.IntegrityError:
        return False
