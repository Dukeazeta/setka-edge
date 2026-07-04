"""Setka Edge API: daily-refreshed Setka Cup predictions priced against SportyBet markets."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import fetchers
from engine import PlayerStats, evaluate_event

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("setka.api")

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
SNAPSHOT_PATH = CACHE_DIR / "predictions.json"
METRICS_PATH = CACHE_DIR / "metrics.json"

STATE: dict = {
    "predictions": [],
    "updatedAt": None,
    "historyMatches": 0,
    "refreshing": False,
    "error": None,
    "slip": None,
}
REFRESH_INTERVAL_MIN = 20


def _slip_picks(predictions: list[dict]) -> list[dict]:
    from engine import load_config

    cfg = load_config()
    slip_min = cfg.get("slip_min_prob", 0.60)
    now_ms = int(time.time() * 1000)
    picks = [
        e
        for e in predictions
        if e.get("best")
        and e["best"].get("tier") != "lean"
        and e["best"].get("qualified", True)
        and e["best"].get("prob", 0) >= slip_min
        and e["best"].get("confidence") != "low"
        and e.get("startTime", 0) > now_ms
        and e["best"].get("selection")
    ]
    picks.sort(key=lambda e: e["best"]["prob"], reverse=True)
    return picks[:6]


def _slip_leg(event: dict) -> dict:
    best = event["best"]
    return {
        "eventId": event["eventId"],
        "startTime": event["startTime"],
        "home": event["home"],
        "away": event["away"],
        "league": event.get("league"),
        "best": {k: v for k, v in best.items() if k != "selection"},
    }


async def _build_slip(predictions: list[dict]) -> dict:
    picks = _slip_picks(predictions)
    acca = 1.0
    for e in picks:
        acca *= e["best"]["odds"]
    selections = [e["best"]["selection"] for e in picks]
    booking = await fetchers.create_booking_code(selections)
    return {
        "pickCount": len(picks),
        "accaOdds": round(acca, 2) if picks else None,
        "legs": [_slip_leg(e) for e in picks],
        **booking,
    }


def _load_metrics() -> None:
    if not METRICS_PATH.exists():
        return
    try:
        STATE["_metrics"] = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        log.info("loaded metrics snapshot")
    except Exception:  # noqa: BLE001
        log.exception("failed to load metrics")


def _save_metrics(data: dict) -> None:
    try:
        METRICS_PATH.write_text(json.dumps(data), encoding="utf-8")
    except Exception:  # noqa: BLE001
        log.exception("failed to save metrics")


def _load_snapshot() -> None:
    if not SNAPSHOT_PATH.exists():
        return
    try:
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        STATE["predictions"] = data.get("predictions", [])
        STATE["updatedAt"] = data.get("updatedAt")
        STATE["historyMatches"] = data.get("historyMatches", 0)
        STATE["slip"] = data.get("slip")
        log.info("loaded snapshot: %d events from %s", len(STATE["predictions"]), STATE["updatedAt"])
    except Exception:  # noqa: BLE001
        log.exception("failed to load snapshot")


def _save_snapshot() -> None:
    try:
        SNAPSHOT_PATH.write_text(
            json.dumps(
                {
                    "predictions": STATE["predictions"],
                    "updatedAt": STATE["updatedAt"],
                    "historyMatches": STATE["historyMatches"],
                    "slip": STATE.get("slip"),
                }
            ),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to save snapshot")


async def refresh():
    if STATE["refreshing"]:
        return
    STATE["refreshing"] = True
    STATE["error"] = None
    try:
        t0 = time.time()
        history, events = await asyncio.gather(fetchers.fetch_history(), fetchers.fetch_sporty_events())
        stats = PlayerStats(history)
        # keep last good stats if this refresh got a degraded history fetch
        n_matches = sum(len(v) for v in stats.match_wins.values()) // 2
        if n_matches < 200 and STATE.get("_stats") and STATE.get("historyMatches", 0) > n_matches:
            log.warning("degraded history (%d matches); keeping previous stats", n_matches)
            stats = STATE["_stats"]
        else:
            STATE["_stats"] = stats
        pending = [e for e in events if e.get("matchStatus") == "Not start"]
        markets = await fetchers.fetch_event_markets([e["eventId"] for e in pending])
        preds = [evaluate_event(stats, e, markets.get(e["eventId"], {})) for e in pending]
        preds.sort(key=lambda p: p["startTime"])
        STATE["predictions"] = preds
        STATE["slip"] = await _build_slip(preds)
        STATE["historyMatches"] = sum(len(v) for v in stats.match_wins.values()) // 2
        STATE["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        _save_snapshot()
        log.info("refresh done: %d events, %.1fs", len(preds), time.time() - t0)
    except Exception as ex:  # noqa: BLE001
        STATE["error"] = str(ex)
        log.exception("refresh failed")
    finally:
        STATE["refreshing"] = False


async def _warm_metrics():
    if STATE.get("_metrics"):
        return
    try:
        from backtest import rebuild_calibration, run_backtest

        await asyncio.to_thread(rebuild_calibration, 250)
        data = await asyncio.to_thread(run_backtest, 250)
        STATE["_metrics"] = data
        _save_metrics(data)
        log.info("backtest warm-up done: %.1f%% hit rate", data.get("hit_rate", 0) * 100)
    except Exception:  # noqa: BLE001
        log.exception("metrics warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_snapshot()
    _load_metrics()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh, "interval", minutes=REFRESH_INTERVAL_MIN)
    scheduler.start()
    asyncio.create_task(refresh())
    asyncio.create_task(_warm_metrics())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Setka Edge", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    """Fast health check — Render uses this to confirm the container is up."""
    return {
        "ok": True,
        "updatedAt": STATE["updatedAt"],
        "events": len(STATE["predictions"]),
        "refreshing": STATE["refreshing"],
    }


@app.get("/api/predictions")
async def predictions():
    return {
        "updatedAt": STATE["updatedAt"],
        "refreshing": STATE["refreshing"],
        "error": STATE["error"],
        "historyMatches": STATE["historyMatches"],
        "events": STATE["predictions"],
        "slip": STATE.get("slip"),
        "metrics": STATE.get("_metrics"),
    }


@app.post("/api/refresh")
async def force_refresh():
    asyncio.create_task(refresh())
    return {"ok": True}


@app.get("/api/metrics")
async def metrics():
    return STATE.get("_metrics") or {"note": "Run POST /api/metrics/refresh to compute backtest"}


@app.post("/api/metrics/refresh")
async def refresh_metrics():
    from tune import run_tune

    data = await asyncio.to_thread(run_tune, 300)
    STATE["_metrics"] = data
    _save_metrics(data)
    return data


# Serve the built frontend (production single-service deploy). In dev, Vite proxies instead.
_dist = Path(__file__).parent / "static"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
