import json
import logging
import os

import anthropic

from pipeline.llm.base import LLMProvider, ProcessedResult
from pipeline.llm.prompts import TASTE_FILTER_PROMPT, BATCH_TASTE_FILTER_PROMPT

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")

    def process_item(self, title: str, content: str, source: str, url: str) -> ProcessedResult:
        prompt = TASTE_FILTER_PROMPT.format(
            title=title,
            content=content[:4000],
            source=source,
            url=url,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()
        return _parse_single(raw_text)

    def process_batch(self, items: list[dict]) -> list[dict]:
        compact = []
        for item in items:
            compact.append({
                "id": item["id"],
                "title": item["title"],
                "source": item["source"],
                "url": item["url"],
                "content": (item.get("content") or "")[:1500],
            })

        prompt = BATCH_TASTE_FILTER_PROMPT.format(
            items_json=json.dumps(compact, ensure_ascii=False)
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()
        return _parse_batch(raw_text)


def _parse_single(raw_text: str) -> ProcessedResult:
    raw_text = _strip_fences(raw_text)
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


def _parse_batch(raw_text: str) -> list[dict]:
    raw_text = _strip_fences(raw_text)
    data = json.loads(raw_text)
    if isinstance(data, dict):
        for key in ("results", "items", "evaluations"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")
    return data


def _strip_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text
