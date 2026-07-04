"""Per-market probability calibration from walk-forward backtest samples."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
CALIBRATION_PATH = CACHE_DIR / "calibration.json"

# 5% probability bins for step-map calibration
BIN_WIDTH = 0.05
BIN_START = 0.50


def calibration_key(mid: str, line: float | None = None) -> str:
    if mid == "247":
        if line is not None and line <= 17.5:
            return "247_17.5"
        if line is not None and line <= 18.5:
            return "247_18.5"
        return "247_19.5"
    return mid


def _bin_index(prob: float) -> int:
    p = max(BIN_START, min(0.99, prob))
    return int((p - BIN_START) // BIN_WIDTH)


def fit_calibration(samples: list[dict]) -> dict:
    """Fit isotonic-style step maps: list of {key: {bin_label: actual_rate}}."""
    buckets: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for s in samples:
        key = s["key"]
        b = _bin_index(s["prob"])
        buckets[key][b].append(int(s["hit"]))

    table: dict[str, dict[str, float]] = {}
    for key, bins in buckets.items():
        mapped: dict[str, float] = {}
        for b in sorted(bins):
            hits = bins[b]
            if len(hits) >= 3:
                mapped[str(b)] = round(sum(hits) / len(hits), 3)
        if mapped:
            table[key] = mapped

    return {
        "version": datetime.now(timezone.utc).isoformat(),
        "bin_width": BIN_WIDTH,
        "bin_start": BIN_START,
        "table": table,
        "sample_count": len(samples),
    }


def apply_calibration(prob: float, key: str, table: dict | None = None) -> float:
    data = table if table is not None else load_calibration()
    if not data:
        return prob
    mapped = data.get("table", {}).get(key)
    if not mapped:
        return prob

    b = _bin_index(prob)
    # exact bin or nearest lower bin with data
    while b >= 0:
        rate = mapped.get(str(b))
        if rate is not None:
            return rate
        b -= 1
    # try higher bins
    b = _bin_index(prob) + 1
    while b <= 9:
        rate = mapped.get(str(b))
        if rate is not None:
            return rate
        b += 1
    return prob


def load_calibration() -> dict | None:
    if not CALIBRATION_PATH.exists():
        return None
    try:
        return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_calibration(data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    CALIBRATION_PATH.write_text(json.dumps(data), encoding="utf-8")


def calibration_version() -> str | None:
    data = load_calibration()
    return data.get("version") if data else None
