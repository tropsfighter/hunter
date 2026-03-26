# hunter frontend

Vite + React + TypeScript. Proxies `/api` and `/health` to the backend (port 8000).

## Setup (requires Node.js + npm)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — start the backend separately (`uvicorn` in `backend/`).
