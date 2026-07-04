"""Prediction engine: builds player stats from Setka history and prices SportyBet markets."""
from __future__ import annotations

import collections
import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def _variants(s: str) -> set[str]:
    v = {s}
    for a, b in [("y", "i"), ("iy", "y"), ("ii", "iy"), ("ks", "x"), ("ye", "e"), ("ie", "e"), ("kh", "h")]:
        v.add(s.replace(a, b))
        v.add(s.replace(b, a))
    return v


class PlayerStats:
    """Aggregated per-player first-set and match stats from Setka history."""

    def __init__(self, tournaments: list):
        self.first_totals = collections.defaultdict(list)
        self.own_pts = collections.defaultdict(list)
        self.opp_pts = collections.defaultdict(list)
        self.set1_wins = collections.defaultdict(list)
        self.match_wins = collections.defaultdict(list)
        self.deuce = collections.defaultdict(list)
        self.h2h = collections.defaultdict(list)  # sorted pair -> [winner ids]
        self.h2h_set1 = collections.defaultdict(list)  # sorted pair -> [set1 totals]
        self.names: dict[int, str] = {}
        self._ingest(tournaments)
        self.by_last = collections.defaultdict(list)
        for pid, full in self.names.items():
            self.by_last[_norm(full.split()[-1])].append(pid)

    def _ingest(self, tournaments: list):
        for tour in tournaments or []:
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
                p1, p2 = m["player1"], m["player2"]
                id1, id2 = p1["id"], p2["id"]
                self.names[id1] = f'{p1["firstName"]} {p1["lastName"]}'
                self.names[id2] = f'{p2["firstName"]} {p2["lastName"]}'
                tot = a + b
                self.first_totals[id1].append(tot)
                self.first_totals[id2].append(tot)
                self.own_pts[id1].append(a)
                self.own_pts[id2].append(b)
                self.opp_pts[id1].append(b)
                self.opp_pts[id2].append(a)
                self.set1_wins[id1].append(1 if a > b else 0)
                self.set1_wins[id2].append(1 if b > a else 0)
                d = 1 if min(a, b) >= 10 else 0
                self.deuce[id1].append(d)
                self.deuce[id2].append(d)
                w = m.get("winner")
                if w:
                    self.match_wins[id1].append(1 if w["id"] == id1 else 0)
                    self.match_wins[id2].append(1 if w["id"] == id2 else 0)
                    key = tuple(sorted((id1, id2)))
                    self.h2h[key].append(w["id"])
                    self.h2h_set1[key].append(tot)

    def find(self, sporty_name: str) -> int | None:
        """Match 'Last, First' SportyBet naming to a Setka player id (translit-tolerant)."""
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
        for pid in set(cands):
            f = _norm(self.names[pid].split()[0])
            if f == first or (f and first and f[0] == first[0]):
                return pid
        uniq = set(cands)
        return uniq.pop() if len(uniq) == 1 else None


def _prob(samples, pred, prior=0.5, prior_n=4.0) -> float:
    k = sum(1 for x in samples if pred(x))
    return (k + prior * prior_n) / (len(samples) + prior_n)


def _bt(pa: float, pb: float) -> float:
    """Bradley-Terry style combination of two independent success rates."""
    num = pa * (1 - pb)
    den = num + pb * (1 - pa)
    return num / den if den else 0.5


# Markets eligible for the headline "best pick" — excludes deuce/No at ~85% which always wins on prob.
PRIMARY_MARKETS = {"186", "245", "247"}


def evaluate_event(stats: PlayerStats, event: dict, market_data: dict) -> dict:
    """Price every supported market for one event and pick the best options."""
    hid = stats.find(event["home"])
    aid = stats.find(event["away"])
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
        out["note"] = "No recent history found for one or both players."
        return out

    pooled_totals = stats.first_totals[hid] + stats.first_totals[aid]
    pooled_deuce = stats.deuce[hid] + stats.deuce[aid]
    n = len(pooled_totals)
    out["dataQuality"] = n

    key = tuple(sorted((hid, aid)))
    hh = stats.h2h.get(key, [])
    if hh:
        hw = sum(1 for w in hh if w == hid)
        out["h2h"] = {"home": hw, "away": len(hh) - hw}

    picks = []
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
            p = label = None
            if mid == "186":  # match winner
                ph = _bt(_prob(stats.match_wins[hid], lambda x: x == 1),
                         _prob(stats.match_wins[aid], lambda x: x == 1))
                if len(hh) >= 2:
                    ph = 0.5 * ph + 0.5 * (sum(1 for w in hh if w == hid) / len(hh))
                p = ph if o["desc"] == "Home" else 1 - ph
                label = f'Match winner: {event["home"] if o["desc"] == "Home" else event["away"]}'
            elif mid == "245":  # 1st set winner
                ph = _bt(_prob(stats.set1_wins[hid], lambda x: x == 1),
                         _prob(stats.set1_wins[aid], lambda x: x == 1))
                if len(hh) >= 2:  # temper with h2h match record
                    ph = 0.65 * ph + 0.35 * (sum(1 for w in hh if w == hid) / len(hh))
                p = ph if o["desc"] == "Home" else 1 - ph
                label = f'1st set winner: {event["home"] if o["desc"] == "Home" else event["away"]}'
            elif mid == "247" and "total=" in spec:  # 1st set total points
                line = float(spec.split("total=")[1])
                samples = pooled_totals
                hh_tot = stats.h2h_set1.get(key, [])
                if len(hh_tot) >= 3:
                    samples = samples + hh_tot * 2  # h2h sets weigh double
                if o["desc"].startswith("Over"):
                    p = _prob(samples, lambda x: x > line, prior=0.40)
                    label = f"1st set Over {line}"
                else:
                    p = _prob(samples, lambda x: x < line, prior=0.60)
                    label = f"1st set Under {line}"
            elif mid == "900111":  # extra points (deuce) in 1st set
                if o["desc"] == "No":
                    p = _prob(pooled_deuce, lambda x: x == 0, prior=0.85)
                    label = "1st set without deuce (No extra points)"
                else:
                    p = _prob(pooled_deuce, lambda x: x == 1, prior=0.15)
                    label = "1st set reaches deuce (Yes extra points)"
            elif mid in ("900106", "900107") and "total=" in spec:
                line = float(spec.split("total=")[1].split("|")[0])
                if mid == "900106":
                    samples = stats.own_pts[hid] + stats.opp_pts[aid]
                    who = event["home"]
                else:
                    samples = stats.own_pts[aid] + stats.opp_pts[hid]
                    who = event["away"]
                if o["desc"].startswith("Over"):
                    p = _prob(samples, lambda x: x > line)
                    label = f"{who}: 1st-set points Over {line}"
                else:
                    p = _prob(samples, lambda x: x < line)
                    label = f"{who}: 1st-set points Under {line}"
            if p is None:
                continue
            ev = p * odds - 1
            picks.append({
                "market": mkt.get("desc", ""),
                "bet": label,
                "odds": odds,
                "prob": round(p, 3),
                "ev": round(ev, 3),
                "mid": mid,
            })

    picks.sort(key=lambda r: (-r["prob"], -r["ev"]))
    out["picks"] = [{k: v for k, v in p.items() if k != "mid"} for p in picks[:8]]

    eligible = [p for p in picks if p["mid"] in PRIMARY_MARKETS] or picks
    eligible.sort(key=lambda r: (-r["prob"], -r["ev"]))
    if eligible:
        best = eligible[0]
        tier = (
            "strong"
            if best["prob"] >= 0.72
            else "value"
            if best["prob"] >= 0.58
            else "lean"
        )
        out["best"] = {
            "market": best["market"],
            "bet": best["bet"],
            "odds": best["odds"],
            "prob": best["prob"],
            "ev": best["ev"],
            "tier": tier,
        }
    return out
