from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProcessedResult:
    summary: str
    relevance_score: int          # 1-10
    hype_score: int               # 1-10
    teaching_angle: str | None    # Lightweight suggestion, not a directive
    key_stats: list[str]          # Concrete quotable numbers/facts extracted from the content
    tags: list[str]
    verdict: str                  # "high_signal", "medium_signal", "low_signal", "hype"
    reasoning: str


class LLMProvider(ABC):
    @abstractmethod
    def process_item(self, title: str, content: str, source: str, url: str) -> ProcessedResult:
        """Process a single raw item through the taste filter."""
        pass

    @abstractmethod
    def process_batch(self, items: list[dict]) -> list[dict]:
        """Process a batch of items in a single LLM call.

        Args:
            items: List of dicts with keys: id, title, source, url, content

        Returns:
            List of dicts with keys: id, summary, relevance_score, hype_score,
            teaching_angle, key_stats, tags, verdict, reasoning
        """
        pass
