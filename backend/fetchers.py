"""Data fetchers: official Setka Cup API (results history) and SportyBet NG (fixtures + odds)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from pathlib import Path

import httpx

log = logging.getLogger("setka.fetchers")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
SETKA_BASE = "https://tabletennis.setkacup.com/api"
SPORTY_BASE = "https://www.sportybet.com/api/ng/factsCenter"
TT_SPORT_ID = "sr:sport:20"

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

HISTORY_DAYS = 10


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None, retries: int = 3):
    """GET with retry/backoff; DNS on this host is flaky for setkacup.com."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = await client.get(url, params=params, headers=UA, timeout=25)
            r.raise_for_status()
            return r.json()
        except Exception as ex:  # noqa: BLE001
            last_exc = ex
            if attempt < retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
    raise last_exc


async def fetch_setka_day(client: httpx.AsyncClient, day: dt.date) -> list:
    """One day of Setka tournaments (all halls) with set-by-set scores."""
    cache = CACHE_DIR / f"setka_{day.isoformat()}.json"
    # past days never change: reuse cache. Today is always refetched.
    if cache.exists() and day < dt.date.today():
        return json.loads(cache.read_text(encoding="utf-8"))
    data = await _get_json(client, f"{SETKA_BASE}/Tournaments/en", {"date": day.isoformat()})
    data = data or []
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


async def fetch_history() -> list:
    """Last HISTORY_DAYS days of results, flattened to one list of tournaments."""
    today = dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(HISTORY_DAYS)]
    out: list = []
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_setka_day(client, d) for d in days), return_exceptions=True
        )
    for d, res in zip(days, results):
        if isinstance(res, Exception):
            log.warning("setka day %s failed: %s", d, res)
            continue
        out.extend(res)
    return out


async def fetch_sporty_events() -> list[dict]:
    """Upcoming Setka Cup events on SportyBet with tournament names."""
    async with httpx.AsyncClient() as client:
        data = await _get_json(
            client,
            f"{SPORTY_BASE}/pcUpcomingEvents",
            {"sportId": TT_SPORT_ID, "marketId": "1", "pageSize": "100", "pageNum": "1", "option": "1"},
        )
    events = []
    for t in data.get("data", {}).get("tournaments", []):
        if "Setka" not in t.get("name", ""):
            continue
        for e in t.get("events", []):
            events.append(
                {
                    "eventId": e["eventId"],
                    "league": t["name"],
                    "startTime": e["estimateStartTime"],
                    "home": e["homeTeamName"],
                    "away": e["awayTeamName"],
                    "matchStatus": e.get("matchStatus", ""),
                }
            )
    return events


async def fetch_event_markets(event_ids: list[str]) -> dict[str, dict]:
    """Full market board per event."""
    out: dict[str, dict] = {}

    async with httpx.AsyncClient() as client:

        async def one(eid: str):
            try:
                data = await _get_json(client, f"{SPORTY_BASE}/event", {"eventId": eid, "productId": "3"})
                out[eid] = data.get("data", {})
            except Exception as ex:  # noqa: BLE001
                log.warning("markets for %s failed: %s", eid, ex)

        # small batches to stay polite
        for i in range(0, len(event_ids), 5):
            await asyncio.gather(*(one(e) for e in event_ids[i : i + 5]))
            await asyncio.sleep(0.3)
    return out
