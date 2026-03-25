"""Source registry — loads and validates source configs from YAML."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"


@dataclass
class Source:
    name: str
    type: str       # "rss", "api"
    url: str
    fetch_limit: int
    schedule: str   # "daily" etc.


def load_sources(config_path: Path | None = None) -> list[Source]:
    """Load source definitions from sources.yaml."""
    path = config_path or CONFIG_PATH
    with open(path) as f:
        data = yaml.safe_load(f)

    sources = []
    for s in data.get("sources", []):
        sources.append(Source(
            name=s["name"],
            type=s["type"],
            url=s["url"],
            fetch_limit=s.get("fetch_limit", 10),
            schedule=s.get("schedule", "daily"),
        ))

    logger.info(f"Loaded {len(sources)} sources from {path}")
    return sources
