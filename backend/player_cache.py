"""Persistent SportyBet name -> Setka player_id cache."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "cache" / "players.json"


def _norm_key(sporty_name: str) -> str:
    s = unicodedata.normalize("NFKD", sporty_name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s.strip())


def load() -> dict[str, int]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return {k: int(v) for k, v in json.loads(CACHE_PATH.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def save(cache: dict[str, int]) -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def remember(sporty_name: str, player_id: int) -> None:
    cache = load()
    cache[_norm_key(sporty_name)] = player_id
    save(cache)


def lookup(sporty_name: str) -> int | None:
    return load().get(_norm_key(sporty_name))
