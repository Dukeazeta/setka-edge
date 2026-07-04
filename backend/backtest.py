"""Walk-forward backtest for prediction engine calibration."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine import PlayerStats, evaluate_event, load_config

CACHE_DIR = Path(__file__).parent / "cache"


def _load_all_tournaments() -> list[dict]:
    out = []
    for f in sorted(CACHE_DIR.glob("setka_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        out.extend(data or [])
    return out


def _finished_matches(tournaments: list) -> list[dict]:
    rows = []
    for tour in tournaments:
        loc = tour.get("locationId")
        for m in tour.get("matches", []):
            if not m.get("winner") or not m.get("setScores"):
                continue
            s1 = next((s for s in (m.get("setScores") or []) if s.get("number") == 1), None)
            if not s1:
                continue
            try:
                a, b = int(s1["p1Score"]), int(s1["p2Score"])
            except (TypeError, ValueError):
                continue
            if a + b < 11:
                continue
            ts = m.get("startDate", "")
            rows.append({
                "ts": ts,
                "dt": datetime.fromisoformat(ts.replace("Z", "+00:00")),
                "locationId": m.get("locationId") or loc,
                "tournamentName": m.get("tournamentName", ""),
                "player1": m["player1"],
                "player2": m["player2"],
                "winner_id": m["winner"]["id"],
                "set1_total": a + b,
                "set1_winner_id": m["player1"]["id"] if a > b else m["player2"]["id"],
            })
    rows.sort(key=lambda r: r["dt"])
    return rows


def _tournaments_before(all_tours: list, cutoff: datetime) -> list:
    kept = []
    for tour in all_tours:
        ms = []
        for m in tour.get("matches", []):
            try:
                dt = datetime.fromisoformat(m.get("startDate", "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt < cutoff:
                ms.append(m)
        if ms:
            kept.append({**tour, "matches": ms})
    return kept


def _synthetic_event(row: dict) -> dict:
    p1, p2 = row["player1"], row["player2"]
    tn = row.get("tournamentName", "")
    if "Prague" in tn or "Paris" in tn:
        league = "Setka Cup Czech Republic"
    elif "Rio" in tn or "Mexico" in tn:
        league = "Setka Cup Moldova"
    else:
        league = "Setka Cup"
    return {
        "eventId": f"bt-{p1['id']}-{p2['id']}",
        "league": league,
        "startTime": int(row["dt"].timestamp() * 1000),
        "home": f"{p1['lastName']}, {p1['firstName']}",
        "away": f"{p2['lastName']}, {p2['firstName']}",
        "matchStatus": "Not start",
    }


def _synthetic_markets(row: dict) -> dict:
    return {
        "markets": [
            {
                "id": "186", "desc": "Winner", "specifier": "",
                "outcomes": [
                    {"desc": "Home", "odds": 1.85, "isActive": 1},
                    {"desc": "Away", "odds": 1.85, "isActive": 1},
                ],
            },
            {
                "id": "245", "desc": "1st game - winner", "specifier": "gamenr=1",
                "outcomes": [
                    {"desc": "Home", "odds": 1.85, "isActive": 1},
                    {"desc": "Away", "odds": 1.85, "isActive": 1},
                ],
            },
            {
                "id": "247", "desc": "1st game - total points", "specifier": "gamenr=1|total=19.5",
                "outcomes": [
                    {"desc": "Over 19.5", "odds": 1.90, "isActive": 1},
                    {"desc": "Under 19.5", "odds": 1.90, "isActive": 1},
                ],
            },
        ],
        "_actual": {
            "match_home": row["winner_id"] == row["player1"]["id"],
            "set1_home": row["set1_winner_id"] == row["player1"]["id"],
            "over_19_5": row["set1_total"] > 19.5,
        },
    }


def _resolve_hit(best: dict, row: dict, actual: dict) -> bool | None:
    bet = best["bet"]
    p1 = row["player1"]
    is_home_pick = p1["lastName"] in bet

    if bet.startswith("Match winner"):
        return actual["match_home"] if is_home_pick else not actual["match_home"]
    if bet.startswith("1st set winner"):
        return actual["set1_home"] if is_home_pick else not actual["set1_home"]
    if "Over 19.5" in bet:
        return actual["over_19_5"]
    if "Under 19.5" in bet:
        return not actual["over_19_5"]
    return None


def run_backtest(max_matches: int = 400) -> dict:
    all_tours = _load_all_tournaments()
    matches = _finished_matches(all_tours)
    if len(matches) > max_matches:
        matches = matches[-max_matches:]

    results = []
    bins: dict[int, list] = defaultdict(list)

    for row in matches:
        cutoff = row["dt"]
        hist_tours = _tournaments_before(all_tours, cutoff)
        if not hist_tours:
            continue

        stats = PlayerStats(hist_tours, ref_time=cutoff)
        mkts = _synthetic_markets(row)
        actual = mkts.pop("_actual")
        pred = evaluate_event(stats, _synthetic_event(row), mkts)
        best = pred.get("best")
        if not best:
            continue

        hit = _resolve_hit(best, row, actual)
        if hit is None:
            continue

        results.append({"prob": best["prob"], "tier": best["tier"], "hit": hit, "bet": best["bet"]})
        bins[int(best["prob"] * 10) * 10].append(hit)

    if not results:
        return {"error": "no results", "n": 0}

    by_tier: dict = defaultdict(lambda: {"n": 0, "hits": 0})
    brier = 0.0
    for r in results:
        by_tier[r["tier"]]["n"] += 1
        by_tier[r["tier"]]["hits"] += int(r["hit"])
        brier += (r["prob"] - float(r["hit"])) ** 2

    return {
        "n": len(results),
        "hit_rate": round(sum(r["hit"] for r in results) / len(results), 3),
        "brier": round(brier / len(results), 4),
        "by_tier": {k: {**v, "rate": round(v["hits"] / v["n"], 3)} for k, v in by_tier.items()},
        "calibration": {
            f"{b}%": {"predicted": b / 100, "actual": round(sum(h) / len(h), 3), "n": len(h)}
            for b, h in sorted(bins.items())
        },
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Config:", load_config())
    print(json.dumps(run_backtest(), indent=2))
