import json
import logging
import os

import anthropic

from pipeline.llm.base import LLMProvider, ProcessedResult
from pipeline.llm.prompts import TASTE_FILTER_PROMPT

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")

    def process_item(self, title: str, content: str, source: str, url: str) -> ProcessedResult:
        prompt = TASTE_FILTER_PROMPT.format(
            title=title,
            content=content[:8000],  # Truncate very long content
            source=source,
            url=url,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()
        return self._parse_response(raw_text)

    def _parse_response(self, raw_text: str) -> ProcessedResult:
        """Parse JSON response into ProcessedResult. Raises on malformed JSON."""
        # Strip markdown fences if the model includes them despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        data = json.loads(raw_text)

        return ProcessedResult(
            summary=data["summary"],
            relevance_score=int(data["relevance_score"]),
            hype_score=int(data["hype_score"]),
            teaching_angle=data.get("teaching_angle"),
            key_stats=data.get("key_stats", []),
            tags=data.get("tags", []),
            verdict=data["verdict"],
            reasoning=data["reasoning"],
        )
