"""URL content extraction — web pages, YouTube transcripts."""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Shared HTTP client settings
TIMEOUT = 30
HEADERS = {
    "User-Agent": "ResearchDashboard/1.0 (internal tool; contact: admin@example.com)"
}


def fetch_url_content(url: str) -> dict:
    """Fetch and extract content from a URL. Returns dict with title and content.

    Handles:
    - Regular web pages (HTML → text extraction)
    - YouTube videos (transcript extraction)
    - Falls back gracefully on errors
    """
    if _is_youtube_url(url):
        return _fetch_youtube(url)
    return _fetch_webpage(url)


def _is_youtube_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com/watch|youtu\.be/)", url))


def _extract_youtube_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
    patterns = [
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtu\.be/([^?]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _fetch_youtube(url: str) -> dict:
    """Extract content from YouTube video via transcript API."""
    video_id = _extract_youtube_id(url)
    if not video_id:
        return {"title": url, "content": ""}

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(["en"])
        entries = transcript.fetch()
        text = " ".join(entry["text"] for entry in entries)

        # Also try to get the title from the page
        title = _get_youtube_title(url) or f"YouTube: {video_id}"
        return {"title": title, "content": text[:10000]}
    except Exception as e:
        logger.warning(f"YouTube transcript fetch failed for {url}: {e}")
        # Fallback: fetch page metadata
        title = _get_youtube_title(url) or f"YouTube: {video_id}"
        return {"title": title, "content": ""}


def _get_youtube_title(url: str) -> str | None:
    """Get YouTube video title from page metadata."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().replace(" - YouTube", "").strip()
            return title
    except Exception:
        pass
    return None


def _fetch_webpage(url: str) -> dict:
    """Fetch a web page and extract its main text content."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Try to find main content area
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)

        return {"title": title, "content": content[:10000]}
    except Exception as e:
        logger.warning(f"Webpage fetch failed for {url}: {e}")
        return {"title": "", "content": ""}
