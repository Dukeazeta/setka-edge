"""Map SportyBet league names to Setka Cup locationIds (hall codes)."""

from __future__ import annotations

# Discovered by player-name cross-reference against Setka API history.
LEAGUE_LOCATIONS: dict[str, list[int]] = {
    "Ukraine": [10],       # London hall
    "Czech Republic": [11, 14],  # Prague primary, Paris secondary
    "Moldova": [19, 18],   # Rio primary, Mexico secondary
    "Women": [10, 11, 19],  # women rotate halls; use blended
}


def league_key(sporty_league: str) -> str:
    if "Czech" in sporty_league:
        return "Czech Republic"
    if "Moldova" in sporty_league:
        return "Moldova"
    if "Women" in sporty_league:
        return "Women"
    return "Ukraine"


def location_ids_for_league(sporty_league: str) -> list[int]:
    return LEAGUE_LOCATIONS.get(league_key(sporty_league), [10])
