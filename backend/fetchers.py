"""Data fetchers: official Setka Cup API (results history) and SportyBet NG (fixtures + odds)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import httpx

log = logging.getLogger("setka.fetchers")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.sportybet.com/ng/sport/table_tennis",
}
SETKA_BASE = "https://tabletennis.setkacup.com/api"
SPORTY_BASE = "https://www.sportybet.com/api/ng/factsCenter"
SPORTY_SHARE_URL = "https://www.sportybet.com/api/ng/orders/share"
TT_SPORT_ID = "sr:sport:20"

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
SPORTY_EVENTS_CACHE = CACHE_DIR / "sporty_events.json"
SPORTY_MARKETS_CACHE = CACHE_DIR / "sporty_markets.json"

HISTORY_DAYS = 14


def _curl_json(url: str, params: dict | None = None) -> dict | list:
    """SportyBet blocks Python TLS fingerprints; curl works on this host."""
    if params:
        url = f"{url}?{urlencode(params)}"
    proc = subprocess.run(
        ["curl", "-sS", "-L", "-H", f"User-Agent: {UA['User-Agent']}", "-H", f"Referer: {UA['Referer']}", url],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl failed ({proc.returncode})")
    body = proc.stdout.strip()
    if not body:
        raise ValueError("empty curl response")
    return json.loads(body)


def _sporty_host(url: str) -> bool:
    return "sportybet.com" in url


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None, retries: int = 3):
    """GET with retry/backoff; SportyBet sometimes returns 202 with an empty body to Python clients."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            if _sporty_host(url):
                return await asyncio.to_thread(_curl_json, url, params)
            r = await client.get(url, params=params, headers=UA, timeout=25)
            if r.status_code == 202 or not r.content.strip():
                raise ValueError(f"empty or pending response ({r.status_code})")
            r.raise_for_status()
            return r.json()
        except Exception as ex:  # noqa: BLE001
            last_exc = ex
            if attempt < retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
    raise last_exc


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict, retries: int = 3):
    """POST with retry/backoff; SportyBet sometimes returns 202 with an empty body."""
    headers = {**UA, "Content-Type": "application/json", "Origin": "https://www.sportybet.com"}
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=25)
            if r.status_code == 202 or not r.content.strip():
                raise ValueError(f"empty or pending response ({r.status_code})")
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


def _parse_sporty_events(data: dict) -> list[dict]:
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


def _load_sporty_events_cache() -> list[dict]:
    if not SPORTY_EVENTS_CACHE.exists():
        return []
    try:
        return json.loads(SPORTY_EVENTS_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save_sporty_events_cache(events: list[dict]) -> None:
    SPORTY_EVENTS_CACHE.write_text(json.dumps(events), encoding="utf-8")


async def fetch_sporty_events() -> list[dict]:
    """Upcoming Setka Cup events on SportyBet with tournament names."""
    async with httpx.AsyncClient() as client:
        try:
            data = await _get_json(
                client,
                f"{SPORTY_BASE}/pcUpcomingEvents",
                {"sportId": TT_SPORT_ID, "marketId": "1", "pageSize": "100", "pageNum": "1", "option": "1"},
                retries=5,
            )
            events = _parse_sporty_events(data)
            if events:
                _save_sporty_events_cache(events)
            return events
        except Exception as ex:  # noqa: BLE001
            cached = _load_sporty_events_cache()
            if cached:
                log.warning("sporty events fetch failed (%s); using %d cached events", ex, len(cached))
                return cached
            raise


def _load_markets_cache() -> dict[str, dict]:
    if not SPORTY_MARKETS_CACHE.exists():
        return {}
    try:
        return json.loads(SPORTY_MARKETS_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_markets_cache(markets: dict[str, dict]) -> None:
    SPORTY_MARKETS_CACHE.write_text(json.dumps(markets), encoding="utf-8")


async def fetch_event_markets(event_ids: list[str]) -> dict[str, dict]:
    """Full market board per event."""
    cached = _load_markets_cache()
    out: dict[str, dict] = {eid: cached[eid] for eid in event_ids if eid in cached}
    missing = [eid for eid in event_ids if eid not in out]

    async with httpx.AsyncClient() as client:

        async def one(eid: str):
            try:
                data = await _get_json(client, f"{SPORTY_BASE}/event", {"eventId": eid, "productId": "3"})
                board = data.get("data", {})
                if board:
                    out[eid] = board
            except Exception as ex:  # noqa: BLE001
                log.warning("markets for %s failed: %s", eid, ex)

        for i in range(0, len(missing), 5):
            await asyncio.gather(*(one(e) for e in missing[i : i + 5]))
            await asyncio.sleep(0.3)

    if out:
        merged = {**cached, **out}
        _save_markets_cache(merged)
    return out


def _curl_post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload)
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-L",
            "-X",
            "POST",
            "-H",
            f"User-Agent: {UA['User-Agent']}",
            "-H",
            f"Referer: {UA['Referer']}",
            "-H",
            "Content-Type: application/json",
            "-H",
            "Origin: https://www.sportybet.com",
            "-d",
            body,
            url,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl failed ({proc.returncode})")
    raw = proc.stdout.strip()
    if not raw:
        raise ValueError("empty curl response")
    return json.loads(raw)


def _normalize_selection(sel: dict) -> dict:
    """SportyBet share API expects string ids and optional specifier."""
    out = {
        "eventId": sel["eventId"],
        "marketId": str(sel["marketId"]),
        "outcomeId": str(sel["outcomeId"]),
    }
    spec = (sel.get("specifier") or "").strip()
    if spec:
        out["specifier"] = spec
    return out


async def create_booking_code(selections: list[dict]) -> dict:
    """Book an accumulator on SportyBet and return shareCode + shareURL.

    POST /api/ng/orders/share with {"selections": [...]} — no auth required.
    """
    if not selections:
        return {"bookingCode": None, "shareUrl": None, "bookingError": "no selections"}

    payload = {"selections": [_normalize_selection(s) for s in selections]}
    try:
        if _sporty_host(SPORTY_SHARE_URL):
            data = await asyncio.to_thread(_curl_post_json, SPORTY_SHARE_URL, payload)
        else:
            async with httpx.AsyncClient() as client:
                data = await _post_json(client, SPORTY_SHARE_URL, payload, retries=5)
    except Exception as ex:  # noqa: BLE001
        log.warning("booking code failed: %s", ex)
        return {"bookingCode": None, "shareUrl": None, "bookingError": str(ex)}

    if data.get("bizCode") not in (None, 10000, "10000"):
        msg = data.get("message") or data.get("innerMsg") or "SportyBet rejected booking"
        return {"bookingCode": None, "shareUrl": None, "bookingError": msg}

    inner = data.get("data") or data
    code = inner.get("shareCode") or inner.get("bookingCode")
    url = inner.get("shareURL") or inner.get("shareUrl")
    if code and not url:
        url = f"https://www.sportybet.com/ng/?shareCode={code}"
    if not code:
        return {"bookingCode": None, "shareUrl": None, "bookingError": "no shareCode in response"}

    return {
        "bookingCode": code,
        "shareUrl": url,
        "bookingDeadline": inner.get("deadline"),
        "bookingError": None,
    }
