"""Prediction engine v2: hall-aware, recency-weighted, H2H-first, calibrated probabilities."""
from __future__ import annotations

import collections
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from halls import location_ids_for_league
import player_cache

CONFIG_PATH = Path(__file__).parent / "config.json"

PRIMARY_MARKETS = {"186", "245", "247"}


def load_config() -> dict:
    defaults = {
        "half_life_days": 3.0,
        "shrinkage_k": 10.0,
        "hall_min_samples": 8,
        "h2h_match_min": 3,
        "h2h_set1_min": 5,
        "h2h_match_weight": 0.8,
        "h2h_set1_weight": 0.8,
    }
    if CONFIG_PATH.exists():
        defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return defaults


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def _variants(s: str) -> set[str]:
    v = {s}
    for a, b in [("y", "i"), ("iy", "y"), ("ii", "iy"), ("ks", "x"), ("ye", "e"), ("ie", "e"), ("kh", "h")]:
        v.add(s.replace(a, b))
        v.add(s.replace(b, a))
    return v


def _parse_ts(raw: str) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _age_days(ts: datetime, ref: datetime | None = None) -> float:
    ref = ref or datetime.now(timezone.utc)
    return max(0.0, (ref - ts).total_seconds() / 86400.0)


def _weight(age_days: float, half_life: float) -> float:
    return 0.5 ** (age_days / half_life) if half_life > 0 else 1.0


def _weighted_rate(samples: list[tuple[datetime, int]], pred, half_life: float, ref: datetime | None = None) -> tuple[float, float]:
    """Return (weighted success rate, effective sample size n_eff)."""
    if not samples:
        return 0.5, 0.0
    w_sum = hit_sum = 0.0
    for ts, val in samples:
        w = _weight(_age_days(ts, ref), half_life)
        w_sum += w
        if pred(val):
            hit_sum += w
    if w_sum <= 0:
        return 0.5, 0.0
    return hit_sum / w_sum, w_sum


def _shrink(raw_p: float, n_eff: float, base: float, k: float) -> float:
    if n_eff <= 0:
        return base
    return (n_eff * raw_p + k * base) / (n_eff + k)


def _confidence(n_eff: float, h2h_n: int, cfg: dict) -> str:
    if n_eff >= 20 and (h2h_n >= cfg["h2h_match_min"] or n_eff >= 30):
        return "high"
    if n_eff >= 12:
        return "medium"
    return "low"


def _bt(pa: float, pb: float) -> float:
    num = pa * (1 - pb)
    den = num + pb * (1 - pa)
    return num / den if den else 0.5


class PlayerStats:
    """Per-player timed samples, global + per-hall, with H2H stores."""

    def __init__(self, tournaments: list, ref_time: datetime | None = None):
        self.ref_time = ref_time or datetime.now(timezone.utc)
        self.cfg = load_config()
        self.names: dict[int, str] = {}

        # global timed samples
        self.first_totals: dict[int, list] = collections.defaultdict(list)
        self.own_pts: dict[int, list] = collections.defaultdict(list)
        self.opp_pts: dict[int, list] = collections.defaultdict(list)
        self.set1_wins: dict[int, list] = collections.defaultdict(list)
        self.match_wins: dict[int, list] = collections.defaultdict(list)
        self.deuce: dict[int, list] = collections.defaultdict(list)

        # per (player_id, location_id)
        self.hall_first_totals: dict[tuple[int, int], list] = collections.defaultdict(list)
        self.hall_set1_wins: dict[tuple[int, int], list] = collections.defaultdict(list)
        self.hall_match_wins: dict[tuple[int, int], list] = collections.defaultdict(list)
        self.hall_own_pts: dict[tuple[int, int], list] = collections.defaultdict(list)

        self.h2h_match: dict[tuple[int, int], list] = collections.defaultdict(list)  # -> winner id
        self.h2h_set1_total: dict[tuple[int, int], list] = collections.defaultdict(list)
        self.h2h_set1_winner: dict[tuple[int, int], list] = collections.defaultdict(list)  # winner id set1

        self.by_last: dict[str, list[int]] = collections.defaultdict(list)
        self._ingest(tournaments)
        for pid, full in self.names.items():
            self.by_last[_norm(full.split()[-1])].append(pid)

    def _ingest(self, tournaments: list):
        hl = self.cfg["half_life_days"]
        for tour in tournaments or []:
            loc = tour.get("locationId")
            for m in tour.get("matches", []):
                ss = m.get("setScores") or []
                s1 = next((s for s in ss if s.get("number") == 1), None)
                if not s1:
                    continue
                try:
                    a, b = int(s1["p1Score"]), int(s1["p2Score"])
                except (KeyError, TypeError, ValueError):
                    continue
                if a + b < 11 or max(a, b) < 11:
                    continue

                ts = _parse_ts(m.get("startDate", ""))
                p1, p2 = m["player1"], m["player2"]
                id1, id2 = p1["id"], p2["id"]
                loc = m.get("locationId") or loc
                self.names[id1] = f'{p1["firstName"]} {p1["lastName"]}'
                self.names[id2] = f'{p2["firstName"]} {p2["lastName"]}'
                tot = a + b
                s1w1 = 1 if a > b else 0
                s1w2 = 1 if b > a else 0
                d = 1 if min(a, b) >= 10 else 0

                for pid, own, opp, s1w in ((id1, a, b, s1w1), (id2, b, a, s1w2)):
                    self.first_totals[pid].append((ts, tot))
                    self.own_pts[pid].append((ts, own))
                    self.opp_pts[pid].append((ts, opp))
                    self.set1_wins[pid].append((ts, s1w))
                    self.deuce[pid].append((ts, d))
                    if loc is not None:
                        self.hall_first_totals[(pid, loc)].append((ts, tot))
                        self.hall_set1_wins[(pid, loc)].append((ts, s1w))
                        self.hall_own_pts[(pid, loc)].append((ts, own))

                w = m.get("winner")
                if w:
                    wid = w["id"]
                    self.match_wins[id1].append((ts, 1 if wid == id1 else 0))
                    self.match_wins[id2].append((ts, 1 if wid == id2 else 0))
                    if loc is not None:
                        self.hall_match_wins[(id1, loc)].append((ts, 1 if wid == id1 else 0))
                        self.hall_match_wins[(id2, loc)].append((ts, 1 if wid == id2 else 0))
                    key = tuple(sorted((id1, id2)))
                    self.h2h_match[key].append((ts, wid))
                    self.h2h_set1_total[key].append((ts, tot))
                    self.h2h_set1_winner[key].append((ts, id1 if a > b else id2))

    def _resolve_candidates(self, sporty_name: str) -> list[int]:
        cached = player_cache.lookup(sporty_name)
        if cached is not None:
            return [cached]
        parts = [p.strip() for p in sporty_name.split(",")]
        last = _norm(parts[0])
        first = _norm(parts[1]) if len(parts) > 1 else ""
        cands: list[int] = []
        for lv in _variants(last):
            cands += self.by_last.get(lv, [])
        if not cands:
            for nl, pids in self.by_last.items():
                if last[:5] and (last[:5] in nl or nl[:5] in last):
                    cands += pids
        matched = []
        for pid in set(cands):
            f = _norm(self.names.get(pid, "").split()[0])
            if f == first or (f and first and f[0] == first[0]):
                matched.append(pid)
        return matched

    def find(self, sporty_name: str) -> int | None:
        matched = self._resolve_candidates(sporty_name)
        if len(matched) == 1:
            player_cache.remember(sporty_name, matched[0])
            return matched[0]
        if len(matched) == 0:
            return None
        return None  # ambiguous — do not guess

    def _hall_samples(self, store: dict, pid: int, locs: list[int]) -> list:
        out = []
        for loc in locs:
            out.extend(store.get((pid, loc), []))
        return out

    def _blend_samples(self, global_s: list, hall_s: list, hall_min: int) -> list:
        if len(hall_s) >= hall_min:
            # 70% hall-weighted duplication for emphasis
            return hall_s + hall_s + global_s
        return global_s

    def match_win_prob(self, hid: int, aid: int, locs: list[int], h2h: list) -> tuple[float, float, float]:
        """Return (calibrated_p_home, raw_p_home, n_eff)."""
        cfg = self.cfg
        hl = cfg["half_life_days"]
        base = 0.5

        ind_h, n_h = _weighted_rate(
            self._blend_samples(self.match_wins[hid], self._hall_samples(self.hall_match_wins, hid, locs), cfg["hall_min_samples"]),
            lambda x: x == 1, hl, self.ref_time,
        )
        ind_a, n_a = _weighted_rate(
            self._blend_samples(self.match_wins[aid], self._hall_samples(self.hall_match_wins, aid, locs), cfg["hall_min_samples"]),
            lambda x: x == 1, hl, self.ref_time,
        )
        raw = _bt(ind_h, ind_a)
        n_eff = min(n_h, n_a)

        if len(h2h) >= cfg["h2h_match_min"]:
            hw = sum(1 for _, w in h2h if w == hid)
            h2h_p = hw / len(h2h)
            w = cfg["h2h_match_weight"]
            raw = w * h2h_p + (1 - w) * raw
            n_eff = max(n_eff, len(h2h) * 2)

        cal = _shrink(raw, n_eff, base, cfg["shrinkage_k"])
        return cal, raw, n_eff

    def set1_win_prob(self, hid: int, aid: int, locs: list[int], h2h_s1: list) -> tuple[float, float, float]:
        cfg = self.cfg
        hl = cfg["half_life_days"]

        ind_h, n_h = _weighted_rate(
            self._blend_samples(self.set1_wins[hid], self._hall_samples(self.hall_set1_wins, hid, locs), cfg["hall_min_samples"]),
            lambda x: x == 1, hl, self.ref_time,
        )
        ind_a, n_a = _weighted_rate(
            self._blend_samples(self.set1_wins[aid], self._hall_samples(self.hall_set1_wins, aid, locs), cfg["hall_min_samples"]),
            lambda x: x == 1, hl, self.ref_time,
        )
        raw = _bt(ind_h, ind_a)
        n_eff = min(n_h, n_a)

        if len(h2h_s1) >= cfg["h2h_match_min"]:
            hw = sum(1 for _, w in h2h_s1 if w == hid)
            h2h_p = hw / len(h2h_s1)
            w = cfg["h2h_match_weight"]
            raw = w * h2h_p + (1 - w) * raw
            n_eff = max(n_eff, len(h2h_s1) * 2)

        cal = _shrink(raw, n_eff, 0.5, cfg["shrinkage_k"])
        return cal, raw, n_eff

    def set1_total_prob(self, hid: int, aid: int, locs: list[int], line: float, over: bool,
                        h2h_totals: list, key: tuple[int, int]) -> tuple[float, float, float]:
        cfg = self.cfg
        hl = cfg["half_life_days"]
        pred = (lambda x: x > line) if over else (lambda x: x < line)

        global_s = self.first_totals[hid] + self.first_totals[aid]
        hall_s = self._hall_samples(self.hall_first_totals, hid, locs) + self._hall_samples(self.hall_first_totals, aid, locs)
        samples = self._blend_samples(global_s, hall_s, cfg["hall_min_samples"])

        # league base rate for shrinkage anchor
        base_vals = [v for _, v in samples]
        base = sum(1 for v in base_vals if pred(v)) / len(base_vals) if base_vals else (0.4 if over else 0.6)

        if len(h2h_totals) >= cfg["h2h_set1_min"]:
            h2h_vals = [(ts, v) for ts, v in h2h_totals]
            samples = h2h_vals * 3 + samples

        raw, n_eff = _weighted_rate(samples, pred, hl, self.ref_time)
        cal = _shrink(raw, n_eff, base, cfg["shrinkage_k"])
        return cal, raw, n_eff


def evaluate_event(stats: PlayerStats, event: dict, market_data: dict) -> dict:
    cfg = stats.cfg
    hid = stats.find(event["home"])
    aid = stats.find(event["away"])
    locs = location_ids_for_league(event.get("league", ""))

    out = {
        "eventId": event["eventId"],
        "league": event["league"],
        "startTime": event["startTime"],
        "home": event["home"],
        "away": event["away"],
        "matchStatus": event.get("matchStatus", ""),
        "dataQuality": 0,
        "picks": [],
        "h2h": None,
    }

    if hid is None or aid is None:
        home_cands = stats._resolve_candidates(event["home"])
        away_cands = stats._resolve_candidates(event["away"])
        if len(home_cands) > 1 or len(away_cands) > 1:
            out["note"] = "Ambiguous player name match — skipped."
        else:
            out["note"] = "No recent history found for one or both players."
        return out

    key = tuple(sorted((hid, aid)))
    h2h_m = stats.h2h_match.get(key, [])
    h2h_s1w = stats.h2h_set1_winner.get(key, [])
    h2h_s1t = stats.h2h_set1_total.get(key, [])

    if h2h_m:
        hw = sum(1 for _, w in h2h_m if w == hid)
        out["h2h"] = {"home": hw, "away": len(h2h_m) - hw}

    n_home = len(stats.first_totals[hid])
    n_away = len(stats.first_totals[aid])
    out["dataQuality"] = min(n_home, n_away, len(h2h_s1t) or 999)

    picks = []
    totals_by_line: dict[float, list] = collections.defaultdict(list)

    for mkt in market_data.get("markets", []):
        mid = str(mkt.get("id"))
        spec = mkt.get("specifier", "") or ""
        for o in mkt.get("outcomes", []):
            if not o.get("isActive"):
                continue
            try:
                odds = float(o["odds"])
            except (KeyError, ValueError):
                continue

            p = raw_p = n_eff = label = None

            if mid == "186":
                cal, raw_p, n_eff = stats.match_win_prob(hid, aid, locs, h2h_m)
                p = cal if o["desc"] == "Home" else 1 - cal
                raw_p = raw_p if o["desc"] == "Home" else 1 - raw_p
                label = f'Match winner: {event["home"] if o["desc"] == "Home" else event["away"]}'

            elif mid == "245":
                cal, raw_p, n_eff = stats.set1_win_prob(hid, aid, locs, h2h_s1w)
                p = cal if o["desc"] == "Home" else 1 - cal
                raw_p = raw_p if o["desc"] == "Home" else 1 - raw_p
                label = f'1st set winner: {event["home"] if o["desc"] == "Home" else event["away"]}'

            elif mid == "247" and "total=" in spec:
                line = float(spec.split("total=")[1])
                over = o["desc"].startswith("Over")
                cal, raw_p, n_eff = stats.set1_total_prob(hid, aid, locs, line, over, h2h_s1t, key)
                p, raw_p = cal, raw_p
                label = f"1st set {'Over' if over else 'Under'} {line}"

            elif mid == "900111":
                pooled = stats.deuce[hid] + stats.deuce[aid]
                hl = cfg["half_life_days"]
                if o["desc"] == "No":
                    raw_p, n_eff = _weighted_rate(pooled, lambda x: x == 0, hl, stats.ref_time)
                    base = 0.85
                else:
                    raw_p, n_eff = _weighted_rate(pooled, lambda x: x == 1, hl, stats.ref_time)
                    base = 0.15
                p = _shrink(raw_p, n_eff, base, cfg["shrinkage_k"])
                label = "1st set without deuce (No extra points)" if o["desc"] == "No" else "1st set reaches deuce (Yes extra points)"

            elif mid in ("900106", "900107") and "total=" in spec:
                line = float(spec.split("total=")[1].split("|")[0])
                hl = cfg["half_life_days"]
                if mid == "900106":
                    samples = stats.own_pts[hid] + stats.opp_pts[aid]
                    who = event["home"]
                else:
                    samples = stats.own_pts[aid] + stats.opp_pts[hid]
                    who = event["away"]
                over = o["desc"].startswith("Over")
                pred = (lambda x: x > line) if over else (lambda x: x < line)
                raw_p, n_eff = _weighted_rate(samples, pred, hl, stats.ref_time)
                p = _shrink(raw_p, n_eff, 0.5, cfg["shrinkage_k"])
                label = f"{who}: 1st-set points {'Over' if over else 'Under'} {line}"

            if p is None:
                continue

            h2h_n = len(h2h_m)
            conf = _confidence(n_eff, h2h_n, cfg)
            ev = p * odds - 1
            entry = {
                "market": mkt.get("desc", ""),
                "bet": label,
                "odds": odds,
                "prob": round(p, 3),
                "rawProb": round(raw_p, 3),
                "ev": round(ev, 3),
                "sampleN": round(n_eff, 1),
                "confidence": conf,
                "mid": mid,
                "outcomeId": str(o["id"]),
                "specifier": spec,
            }
            picks.append(entry)
            if mid == "247" and "total=" in spec:
                totals_by_line[float(spec.split("total=")[1])].append(entry)

    picks.sort(key=lambda r: (-r["prob"], -r["ev"]))

    # Best per O/U line, then best primary market
    best_247 = []
    for line, group in totals_by_line.items():
        group.sort(key=lambda r: -r["prob"])
        best_247.append(group[0])

    primary = [p for p in picks if p["mid"] in ("186", "245")] + best_247
    primary.sort(key=lambda r: (-r["prob"], -r["ev"]))

    out["picks"] = [
        {k: v for k, v in p.items() if k not in ("mid", "outcomeId", "specifier")} for p in picks[:8]
    ]

    if primary:
        best = primary[0]
        tier = (
            "strong"
            if best["prob"] >= 0.72 and best["sampleN"] >= 20 and best["confidence"] == "high"
            else "value"
            if best["prob"] >= 0.58 and best["sampleN"] >= 12
            else "lean"
        )
        out["best"] = {
            "market": best["market"],
            "bet": best["bet"],
            "odds": best["odds"],
            "prob": best["prob"],
            "rawProb": best["rawProb"],
            "ev": best["ev"],
            "sampleN": best["sampleN"],
            "confidence": best["confidence"],
            "tier": tier,
            "selection": {
                "eventId": event["eventId"],
                "marketId": best["mid"],
                "outcomeId": best["outcomeId"],
                "specifier": best.get("specifier", "") or "",
            },
        }
    return out
