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
