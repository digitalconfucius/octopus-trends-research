import json
import logging
import os

from google import genai
from google.genai import types

from pipeline.llm.base import LLMProvider, ProcessedResult
from pipeline.llm.prompts import TASTE_FILTER_PROMPT, BATCH_TASTE_FILTER_PROMPT

logger = logging.getLogger(__name__)


class GoogleProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        self.model = os.environ.get("LLM_MODEL", "gemini-3-flash-preview")

    def process_item(self, title: str, content: str, source: str, url: str) -> ProcessedResult:
        prompt = TASTE_FILTER_PROMPT.format(
            title=title,
            content=content[:4000],
            source=source,
            url=url,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=2048,
            ),
        )

        raw_text = response.text.strip()
        return _parse_single(raw_text)

    def process_batch(self, items: list[dict]) -> list[dict]:
        # Truncate content per item to keep total prompt manageable
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

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=8192,
            ),
        )

        raw_text = response.text.strip()
        return _parse_batch(raw_text)


def _parse_single(raw_text: str) -> ProcessedResult:
    """Parse single-item JSON response into ProcessedResult."""
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
    """Parse batch JSON response into list of result dicts."""
    raw_text = _strip_fences(raw_text)
    data = json.loads(raw_text)
    # Handle case where LLM wraps array in an object
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
