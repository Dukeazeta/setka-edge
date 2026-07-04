"""Grid search hyperparameter tuning for the prediction engine."""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

from backtest import rebuild_calibration, run_backtest
from engine import load_config

CONFIG_PATH = Path(__file__).parent / "config.json"

GRID = {
    "shrinkage_k": [5, 10, 15, 20],
    "half_life_days": [2, 3, 5],
    "h2h_match_weight": [0.6, 0.8, 0.9],
    "h2h_set1_weight": [0.6, 0.8, 0.9],
}


def _score(result: dict) -> tuple[float, float]:
    """Higher hit_rate wins; lower brier breaks ties."""
    if result.get("n", 0) < 50:
        return (-1.0, 1.0)
    return (result.get("hit_rate", 0), -result.get("brier", 1))


def run_tune(max_matches: int = 300, max_combos: int = 48) -> dict:
    """Search grid; rebuild calibration per candidate; return best config + metrics."""
    base = load_config()
    keys = list(GRID.keys())
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    if len(combos) > max_combos:
        # deterministic subsample: stride through sorted combos
        step = max(1, len(combos) // max_combos)
        combos = combos[::step][:max_combos]

    best_cfg = None
    best_result = None
    best_score = (-1.0, 1.0)

    for combo in combos:
        cfg = copy.deepcopy(base)
        for k, v in zip(keys, combo):
            cfg[k] = v

        rebuild_calibration(max_matches=max_matches, cfg=cfg)
        result = run_backtest(max_matches=max_matches, cfg=cfg, use_calibration=True)
        score = _score(result)
        if score > best_score:
            best_score = score
            best_cfg = cfg
            best_result = result

    if best_cfg is None:
        return {"error": "tuning found no valid config"}

    # persist winning config
    CONFIG_PATH.write_text(json.dumps(best_cfg, indent=2), encoding="utf-8")

    # final calibration with saved config
    rebuild_calibration(max_matches=max_matches, cfg=best_cfg)
    final = run_backtest(max_matches=max_matches, cfg=best_cfg, use_calibration=True)
    final["tuned_config"] = {k: best_cfg[k] for k in GRID}
    return final


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run_tune(), indent=2))
