# hunter

Discover **Key Opinion Leaders** on YouTube: configurable **topics** (each with a list of YouTube search queries) drive discovery and scoring. Data comes from the official [YouTube Data API v3](https://developers.google.com/youtube/v3), stored in **SQLite**, with heuristic **ranking**, **REST + CSV**, and a React UI.

## Repository layout

| Path | Role |
|------|------|
| [`backend/`](backend/) | Python package `hunter`: discovery pipeline, SQLite, FastAPI, CLI |
| [`frontend/`](frontend/) | Vite + React: table, dynamic topics, discovery trigger, CSV download |

## Prerequisites

- **Python 3.11+**
- **Node.js** (for the frontend dev server)
- A **Google Cloud** project with **YouTube Data API v3** enabled and an **API key** ([console](https://console.cloud.google.com/apis/library/youtube.googleapis.com))

## Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy `backend/.env.example` to `backend/.env` and set:

- `YOUTUBE_API_KEY` — required for `hunter discover`
- `HUNTER_DB_PATH` — optional; default is `backend/data/hunter.db` (gitignored)

### Run API

```powershell
uvicorn hunter.api.main:app --reload --port 8000
```

- `GET /health` — liveness
- `GET /api/kols?topic=&sort=score|subscribers|title|contact&search=&limit=` — ranked channels (`topic` omit or `all` for every topic)
- `GET /api/kols/export.csv` — same filters as CSV download
- `GET /api/topics` — topic keys with query lists (for the UI)
- `PUT /api/topics/{topic}` — create or replace a topic’s YouTube search queries (`topic` must match `^[a-z0-9_]{1,64}$`)
- `DELETE /api/topics/{topic}` — remove a topic definition (fails if any `channel_topics` rows still use it)
- `POST /api/discover` — JSON body `{ "topic", "max_queries"?, "max_results_per_query"?, "max_total_videos"? }`; returns **202** and runs discovery in a background task
- `GET /api/discover/status` — recent discovery runs (`discovery_runs` table)

**Topics storage:** Query lists live in the SQLite table `topic_queries`. On first startup, if that table is empty, it is **seeded** from [`backend/hunter/config/keywords.yaml`](backend/hunter/config/keywords.yaml). Editing the yaml after seeding does not change the DB until you re-seed or update rows via the API/UI.

**Security (important):** `PUT` / `DELETE` / `POST /api/discover` are **unauthenticated**. Use only on trusted networks; add auth before exposing the API publicly.

### Run discovery (CLI)

Uses the same topic definitions as the API (from `topic_queries` in SQLite).

```powershell
hunter discover --topic football_equipment
hunter discover --topic smart_wearables --max-queries 4 --verbose
```

Options: `--max-queries`, `--max-per-query` (1–50), `--max-videos` (quota guard), `-v`.

**Quota:** Each `search.list` costs **100 units**; `videos.list` / `channels.list` are cheaper. Defaults cap queries and video volume; adjust if your daily quota allows.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 with the API on port **8000** (Vite proxies `/api` and `/health`). Use **Manage topics** to add or edit topics and **Run discovery** (with a single topic selected) to queue a background job on the API.

## Compliance & later platforms

- Use only **official APIs** and respect [YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service).
- **Instagram** and **TikTok** need separate approved API programs; do not rely on brittle scraping for production discovery.

## Development

```powershell
cd backend
.\.venv\Scripts\ruff.exe check hunter
```

### API automated tests (pytest)

From `backend/` with the dev venv active:

```powershell
pip install -e ".[dev]"
python run_tests_and_report.py
```

This runs all tests under `backend/tests/`, prints results, and writes a **timestamped Markdown report** to `backend/reports/api_test_report_YYYYMMDD_HHMMSS.md` (summary + per-case results + **interface coverage** table). To run tests without generating the report:

```powershell
pytest tests -v
```
