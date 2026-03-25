import json
import logging
import os

import openai

from pipeline.llm.base import LLMProvider, ProcessedResult
from pipeline.llm.prompts import TASTE_FILTER_PROMPT

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = os.environ.get("LLM_MODEL", "gpt-4o")

    def process_item(self, title: str, content: str, source: str, url: str) -> ProcessedResult:
        prompt = TASTE_FILTER_PROMPT.format(
            title=title,
            content=content[:8000],  # Truncate very long content
            source=source,
            url=url,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )

        raw_text = response.choices[0].message.content.strip()
        return self._parse_response(raw_text)

    def _parse_response(self, raw_text: str) -> ProcessedResult:
        """Parse JSON response into ProcessedResult. Raises on malformed JSON."""
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
