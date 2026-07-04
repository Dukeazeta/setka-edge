# Setka Edge

Daily Setka Cup (table tennis) prediction dashboard. The backend learns from the last 10 days
of official Setka Cup results, matches every unstarted fixture listed on SportyBet NG, prices
each available market, and surfaces the single best option per game.

## Stack

- **Backend** — Python, FastAPI, httpx, APScheduler
- **Frontend** — React (Vite), Tailwind CSS v4, Framer Motion, Phosphor icons
- **Deploy** — Single Docker container on Render (free tier, wakes on visit)

## Run locally

Backend (port 8000):

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

Frontend (port 5173, proxies `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

Production-style (API + built frontend on one port):

```bash
cd frontend && npm run build
cp -r dist ../backend/static
cd ../backend && python -m uvicorn main:app --port 8000
```

Open http://localhost:8000.

## Deploy to Render (Option 3 — free, wake on visit)

This setup uses Render's **free Web Service**. The app sleeps after ~15 minutes of no traffic
and wakes when you open it. First load after sleep can take up to a minute.

### Steps

1. Push this repo to GitHub (private is fine).
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Connect the repo — Render reads `render.yaml` automatically.
4. Deploy. You get one URL like `https://setka-edge.onrender.com`.

That's it. No pingers, no paid plan. Open the URL when you want picks.

### What happens on a cold start

1. Render starts the Docker container (~30–60s).
2. The UI shows **"Waking the server"** and retries automatically.
3. The backend loads any cached snapshot, then fetches fresh SportyBet + Setka data.
4. Predictions appear; while `refreshing` is true the UI polls every 5s.

### Files involved

| File | Purpose |
|------|---------|
| `render.yaml` | Free web service, Docker runtime, health check on `/api/health` |
| `Dockerfile` | Builds React → copies into `backend/static`, runs uvicorn |
| `backend/cache/` | Setka day cache + `predictions.json` snapshot (ephemeral on free tier) |

### If SportyBet blocks Render's IP

The fetchers may fail from datacenter IPs. If predictions come back empty after wake, check
Render logs. Fallback: run the backend on a cheap VPS instead (same Docker image).

## API

- `GET /api/health` — fast liveness check (used by Render)
- `GET /api/predictions` — all upcoming events with ranked picks
- `POST /api/refresh` — force an immediate data refresh

## Notes

- Tiers: **strong** = model probability ≥ 72%; **value** = ≥ 58%; **lean** = below that. Best pick per match = highest probability among match winner, 1st set winner, and 1st set totals.
- Head-to-head results from the sample window are weighted into winner and set-total pricing.
- This is a statistics explorer, not betting advice. These leagues are extremely volatile.
