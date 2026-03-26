# hunter backend

Python package: YouTube discovery → SQLite → FastAPI + Typer CLI.

## Install

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Environment

Copy `.env.example` to `.env` in this directory (`backend/.env`).

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | For discovery | YouTube Data API v3 key |
| `HUNTER_DB_PATH` | No | SQLite file (default: `data/hunter.db`) |

## Commands

```powershell
# Ingest + score (requires API key)
hunter discover --topic football_equipment
hunter discover --topic smart_wearables --max-queries 4 -v

hunter version

uvicorn hunter.api.main:app --reload --port 8000
```

## Package layout

- `hunter/config/` — `settings.py`, `keywords.yaml`
- `hunter/clients/youtube.py` — API client + retries
- `hunter/pipeline/discover.py` — orchestration
- `hunter/storage/` — SQLite schema + queries
- `hunter/scoring/rank.py` — heuristic score
- `hunter/api/main.py` — FastAPI
