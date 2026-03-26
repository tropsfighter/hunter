# hunter

Discover **Key Opinion Leaders** on YouTube for **football equipment** and **smart wearables**: keyword search via the official [YouTube Data API v3](https://developers.google.com/youtube/v3), channel + video metadata in **SQLite**, heuristic **ranking**, **REST + CSV** for the UI.

## Repository layout

| Path | Role |
|------|------|
| [`backend/`](backend/) | Python package `hunter`: discovery pipeline, SQLite, FastAPI, CLI |
| [`frontend/`](frontend/) | Vite + React: table, topic/sort filters, CSV download link |

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
- `GET /api/kols?topic=&sort=score|subscribers|title&limit=` — ranked channels (`topic` omit or `all` for every topic)
- `GET /api/kols/export.csv` — same filters as CSV download

### Run discovery (CLI)

Uses queries from [`backend/hunter/config/keywords.yaml`](backend/hunter/config/keywords.yaml).

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

Open http://localhost:5173 with the API on port **8000** (Vite proxies `/api` and `/health`).

## Compliance & later platforms

- Use only **official APIs** and respect [YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service).
- **Instagram** and **TikTok** need separate approved API programs; do not rely on brittle scraping for production discovery.

## Development

```powershell
cd backend
.\.venv\Scripts\ruff.exe check hunter
```
