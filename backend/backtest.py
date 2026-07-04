"""Walk-forward backtest for prediction engine calibration."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from calibration import calibration_key, fit_calibration, save_calibration
from engine import PlayerStats, PRIMARY_MARKETS, evaluate_event, load_config

CACHE_DIR = Path(__file__).parent / "cache"
TOTAL_LINES = (17.5, 18.5, 19.5)


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
    markets = [
        {
            "id": "186",
            "desc": "Winner",
            "specifier": "",
            "outcomes": [
                {"desc": "Home", "odds": 1.85, "isActive": 1, "id": "1"},
                {"desc": "Away", "odds": 1.85, "isActive": 1, "id": "2"},
            ],
        },
        {
            "id": "245",
            "desc": "1st game - winner",
            "specifier": "gamenr=1",
            "outcomes": [
                {"desc": "Home", "odds": 1.85, "isActive": 1, "id": "1"},
                {"desc": "Away", "odds": 1.85, "isActive": 1, "id": "2"},
            ],
        },
    ]
    for line in TOTAL_LINES:
        markets.append({
            "id": "247",
            "desc": "1st game - total points",
            "specifier": f"gamenr=1|total={line}",
            "outcomes": [
                {"desc": f"Over {line}", "odds": 1.90, "isActive": 1, "id": f"o{line}"},
                {"desc": f"Under {line}", "odds": 1.90, "isActive": 1, "id": f"u{line}"},
            ],
        })
    return {
        "markets": markets,
        "_actual": {
            "match_home": row["winner_id"] == row["player1"]["id"],
            "set1_home": row["set1_winner_id"] == row["player1"]["id"],
            "set1_total": row["set1_total"],
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

    m = re.search(r"(Over|Under)\s+([\d.]+)", bet)
    if m and "1st set" in bet:
        direction, line_s = m.group(1), float(m.group(2))
        over = actual["set1_total"] > line_s
        return over if direction == "Over" else not over
    return None


def collect_calibration_samples(
    max_matches: int = 400,
    cfg: dict | None = None,
) -> list[dict]:
    """Walk-forward samples for fitting calibration (pre-calibration shrunk probs)."""
    all_tours = _load_all_tournaments()
    matches = _finished_matches(all_tours)
    if len(matches) > max_matches:
        matches = matches[-max_matches:]

    samples = []
    for row in matches:
        cutoff = row["dt"]
        hist_tours = _tournaments_before(all_tours, cutoff)
        if not hist_tours:
            continue

        stats = PlayerStats(hist_tours, ref_time=cutoff, cfg=cfg)
        event = _synthetic_event(row)
        hid = stats.find(event["home"])
        aid = stats.find(event["away"])
        if hid is None or aid is None:
            continue

        from halls import location_ids_for_league

        locs = location_ids_for_league(event.get("league", ""))
        key_h2h = tuple(sorted((hid, aid)))
        h2h_m = stats.h2h_match.get(key_h2h, [])
        h2h_s1w = stats.h2h_set1_winner.get(key_h2h, [])
        h2h_s1t = stats.h2h_set1_total.get(key_h2h, [])
        actual = {
            "match_home": row["winner_id"] == row["player1"]["id"],
            "set1_home": row["set1_winner_id"] == row["player1"]["id"],
            "set1_total": row["set1_total"],
        }

        # Match winner — pick higher-prob side
        cal, _, _ = stats.match_win_prob(hid, aid, locs, h2h_m)
        p_home = cal
        if p_home >= 0.5:
            samples.append({"key": "186", "prob": p_home, "hit": actual["match_home"]})
        else:
            samples.append({"key": "186", "prob": 1 - p_home, "hit": not actual["match_home"]})

        # Set 1 winner
        cal, _, _ = stats.set1_win_prob(hid, aid, locs, h2h_s1w)
        p_home = cal
        if p_home >= 0.5:
            samples.append({"key": "245", "prob": p_home, "hit": actual["set1_home"]})
        else:
            samples.append({"key": "245", "prob": 1 - p_home, "hit": not actual["set1_home"]})

        # Totals per line — pick higher-prob side
        for line in TOTAL_LINES:
            over_cal, _, _ = stats.set1_total_prob(hid, aid, locs, line, True, h2h_s1t, key_h2h)
            under_cal = 1 - over_cal  # approximate; engine computes separately per side
            under_cal2, _, _ = stats.set1_total_prob(hid, aid, locs, line, False, h2h_s1t, key_h2h)
            over = actual["set1_total"] > line
            ckey = calibration_key("247", line)
            if over_cal >= under_cal2:
                samples.append({"key": ckey, "prob": over_cal, "hit": over})
            else:
                samples.append({"key": ckey, "prob": under_cal2, "hit": not over})

    return samples


def run_backtest(
    max_matches: int = 400,
    cfg: dict | None = None,
    use_calibration: bool = True,
) -> dict:
    all_tours = _load_all_tournaments()
    matches = _finished_matches(all_tours)
    if len(matches) > max_matches:
        matches = matches[-max_matches:]

    results = []
    bins: dict[int, list] = defaultdict(list)
    by_market: dict = defaultdict(lambda: {"n": 0, "hits": 0})
    by_line: dict = defaultdict(lambda: {"n": 0, "hits": 0})
    best_source: dict = defaultdict(lambda: {"n": 0, "hits": 0})

    for row in matches:
        cutoff = row["dt"]
        hist_tours = _tournaments_before(all_tours, cutoff)
        if not hist_tours:
            continue

        stats = PlayerStats(hist_tours, ref_time=cutoff, cfg=cfg)
        mkts = _synthetic_markets(row)
        actual = mkts.pop("_actual")
        pred = evaluate_event(
            stats,
            _synthetic_event(row),
            mkts,
            use_calibration=use_calibration,
        )
        best = pred.get("best")
        if not best:
            continue

        hit = _resolve_hit(best, row, actual)
        if hit is None:
            continue

        mid = best.get("marketId", "?")
        results.append({
            "prob": best["prob"],
            "tier": best["tier"],
            "hit": hit,
            "bet": best["bet"],
            "marketId": mid,
            "qualified": best.get("qualified", False),
        })
        bins[int(best["prob"] * 10) * 10].append(hit)
        by_market[mid]["n"] += 1
        by_market[mid]["hits"] += int(hit)
        best_source[mid]["n"] += 1
        best_source[mid]["hits"] += int(hit)

        m = re.search(r"(Over|Under)\s+([\d.]+)", best["bet"])
        if m and mid == "247":
            line = m.group(2)
            by_line[line]["n"] += 1
            by_line[line]["hits"] += int(hit)

    if not results:
        return {"error": "no results", "n": 0}

    by_tier: dict = defaultdict(lambda: {"n": 0, "hits": 0})
    brier = 0.0
    for r in results:
        by_tier[r["tier"]]["n"] += 1
        by_tier[r["tier"]]["hits"] += int(r["hit"])
        brier += (r["prob"] - float(r["hit"])) ** 2

    from calibration import calibration_version

    return {
        "n": len(results),
        "hit_rate": round(sum(r["hit"] for r in results) / len(results), 3),
        "brier": round(brier / len(results), 4),
        "by_tier": {k: {**v, "rate": round(v["hits"] / v["n"], 3)} for k, v in by_tier.items()},
        "by_market": {
            k: {"n": v["n"], "hits": v["hits"], "rate": round(v["hits"] / v["n"], 3)}
            for k, v in by_market.items()
        },
        "by_line": {
            k: {"n": v["n"], "hits": v["hits"], "rate": round(v["hits"] / v["n"], 3)}
            for k, v in by_line.items()
        },
        "best_pick_source": {
            k: {"n": v["n"], "hits": v["hits"], "rate": round(v["hits"] / v["n"], 3)}
            for k, v in best_source.items()
        },
        "calibration": {
            f"{b}%": {"predicted": b / 100, "actual": round(sum(h) / len(h), 3), "n": len(h)}
            for b, h in sorted(bins.items())
        },
        "calibration_version": calibration_version(),
        "config": cfg or load_config(),
    }


def rebuild_calibration(max_matches: int = 400, cfg: dict | None = None) -> dict:
    """Fit and persist calibration table from walk-forward samples."""
    samples = collect_calibration_samples(max_matches=max_matches, cfg=cfg)
    if not samples:
        return {"error": "no calibration samples"}
    table = fit_calibration(samples)
    save_calibration(table)
    return table


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Config:", load_config())
    rebuild_calibration()
    print(json.dumps(run_backtest(), indent=2))
