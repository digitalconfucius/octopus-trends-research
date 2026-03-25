# AI Research & Trend Dashboard

An internal research dashboard for surfacing high-signal AI/tech trends and filtering out hype and clickbait. Built for a small team (CEO + ops person + engineer).

**This is a research input tool** — a wall of high-quality information. It is NOT a content generator, thesis builder, or idea organizer. The CEO's creative process is non-linear; the tool's only job is to maximize the density of genuinely valuable inputs per minute of scanning time.

## Architecture

- **Backend**: Flask (Python 3.11+) with Jinja2 templates
- **Frontend**: HTMX + Tailwind CSS (both via CDN)
- **Database**: SQLite3 (single file at `data/dashboard.db`)
- **LLM Processing**: Model-agnostic (Anthropic/OpenAI providers)
- **Scheduling**: System cron calling `scripts/run_pipeline.py`

## Quick Start

### Prerequisites

- Python 3.11+ (required — the project uses modern Python features)
- An API key for at least one LLM provider (Anthropic or OpenAI)

### Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env — at minimum, add your LLM API key:
#   ANTHROPIC_API_KEY=sk-ant-...
#   or
#   LLM_PROVIDER=openai
#   OPENAI_API_KEY=sk-...

# 4. Run the ingestion + processing pipeline
python scripts/run_pipeline.py

# 5. Start the web server
flask --app app run --debug
```

The dashboard will be available at `http://localhost:5000`.

> **Note:** Always activate the virtual environment (`source .venv/bin/activate`) before running any commands. If you open a new terminal, you'll need to activate it again.

## Project Structure

```
├── app/                        # Flask web application
│   ├── __init__.py             # App factory
│   ├── config.py               # Environment-based configuration
│   ├── database.py             # SQLite3 schema and connection management
│   ├── models.py               # Query helpers (raw SQL, no ORM)
│   ├── routes/
│   │   ├── dashboard.py        # CEO's card grid view
│   │   ├── admin.py            # Ops curation queue
│   │   └── api.py              # HTMX endpoints (bookmark, dismiss, add URL)
│   ├── templates/
│   │   ├── base.html           # Layout (Tailwind + HTMX CDN)
│   │   ├── dashboard.html      # CEO's main view
│   │   ├── admin.html          # Ops curation view
│   │   └── components/
│   │       ├── card.html       # Single topic card (HTMX-swappable)
│   │       ├── card_grid.html  # 3-column responsive grid
│   │       ├── filters.html    # Filter bar (verdict, tag, source, date)
│   │       └── empty_state.html
│   └── static/styles.css
├── pipeline/                   # Data ingestion and LLM processing
│   ├── ingest.py               # Source fetching (HN, Reddit, GitHub, RSS)
│   ├── fetch.py                # URL content extraction (web, YouTube)
│   ├── process.py              # LLM filtering and enrichment
│   ├── sources.py              # Source config loader
│   └── llm/
│       ├── base.py             # Abstract LLM interface + ProcessedResult
│       ├── anthropic_provider.py
│       ├── openai_provider.py
│       └── prompts.py          # THE TASTE FILTER — most important file
├── scripts/
│   └── run_pipeline.py         # Cron entry point: ingest + process
├── config/
│   └── sources.yaml            # Source feed definitions
├── data/                       # SQLite DB lives here (gitignored)
└── logs/                       # Pipeline logs (gitignored)
```

## Core Concepts

### The Taste Filter

The LLM taste filter ([pipeline/llm/prompts.py](pipeline/llm/prompts.py)) is the most important piece of the system. It evaluates every piece of content against our audience's needs and produces:

- **Summary**: 2-3 sentences for quick scanning
- **Relevance score** (1-10): How useful is this to practitioners?
- **Hype score** (1-10): How much does this smell like clickbait?
- **Key stats**: Concrete, quotable numbers extracted from the content
- **Teaching angle**: A lightweight hint (not a directive) about what's teachable
- **Tags**: Topic classification from a fixed set
- **Verdict**: `high_signal`, `medium_signal`, `low_signal`, or `hype`

The prompt is a living document. Edit it frequently based on CEO feedback.

### Data Flow

1. **Ingest** (`pipeline/ingest.py`): Fetch items from configured sources (HN, Reddit, GitHub, RSS feeds) into `raw_items` table. Deduplicates by `(source_name, external_id)`.

2. **Process** (`pipeline/process.py`): Run unprocessed raw items through the LLM taste filter. Store enriched results in `processed_items`.

3. **Display**: Flask serves the processed items as a flat card grid. No ranking, no clustering, no algorithmic grouping — the CEO's brain does that.

### Ingestion Sources

Configured in [config/sources.yaml](config/sources.yaml):

| Source | Type | Items/day |
|--------|------|-----------|
| Hacker News (top) | API | 30 |
| Hacker News (best) | API | 20 |
| r/MachineLearning | Reddit JSON | 15 |
| r/LocalLLaMA | Reddit JSON | 15 |
| r/artificial | Reddit JSON | 10 |
| GitHub Trending | API | 15 |
| TechCrunch AI | RSS | 10 |
| Ars Technica | RSS | 10 |

The ops person can also submit individual URLs (articles, YouTube videos, GitHub repos) via the admin UI.

### LLM Provider Abstraction

The system is not coupled to any single LLM provider. Set via environment variables:

```bash
LLM_PROVIDER=anthropic   # or "openai"
LLM_MODEL=claude-sonnet-4-20250514  # or any model string
```

Both providers request structured JSON output and parse it into the same `ProcessedResult` dataclass. Malformed LLM responses are logged and skipped.

## Users & Views

### Dashboard (`/`) — CEO View
- 3-column card grid, newest first (chronological, not ranked)
- Filters: verdict, tag, source, date range
- Single action: **bookmark** (that's it — no rating, no categorizing)
- Bookmarks view at `/dashboard/bookmarks`

### Admin (`/admin`) — Ops View
- Shows ALL items including low_signal and hype
- Promote: force an item into the CEO's view regardless of verdict
- Dismiss: hide an item from the CEO's view
- Add URL: paste any URL, system fetches content and runs it through the LLM
- Manual entry: fallback form for when URL fetching fails (tweets, PDFs)

## Pipeline Scheduling

Run the pipeline daily via cron (use the venv's Python):

```cron
0 6 * * * cd /path/to/project && .venv/bin/python scripts/run_pipeline.py >> logs/pipeline.log 2>&1
```

Or run manually (with the venv activated):

```bash
python scripts/run_pipeline.py
```

## Configuration

All config via environment variables (`.env` file in development):

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `dev-secret-key...` | Flask session secret |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model identifier |
| `ANTHROPIC_API_KEY` | — | Required if provider is anthropic |
| `OPENAI_API_KEY` | — | Required if provider is openai |
| `DATABASE_PATH` | `data/dashboard.db` | SQLite database file path |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Database Schema

Three tables, raw SQL, no ORM:

- **`raw_items`**: Ingested items before LLM processing. Deduplicated by `(source_name, external_id)`.
- **`processed_items`**: LLM-enriched items with scores, summary, verdict, tags.
- **`item_actions`**: User actions (bookmarked, promoted, dismissed).

Manual URL submissions enter through `raw_items` with `source_type = "manual"` and flow through the same pipeline as automated items.

## Design Principles

- **No imposed structure**: The dashboard is a flat wall of cards. No clustering, grouping, related-items sidebars, or AI-generated themes. The CEO's brain does all the organizing.
- **Simple and transparent**: Raw SQL, small files, minimal abstractions. Easy for anyone (including LLMs) to read and modify.
- **Prompts are product**: The taste filter prompt is the most important file. Treat it with care.
- **Fail gracefully**: Pipeline never crashes entirely because one source is down or one LLM call returns garbage.
- **No premature features**: If it's not in the spec, don't build it.
