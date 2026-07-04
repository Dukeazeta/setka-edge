export const LEAGUE_FILTERS = ['All', 'Ukraine', 'Czech Republic', 'Moldova']
export const TIME_FILTERS = ['All', 'Next hour', 'Next 3h']
export const TIER_FILTERS = ['All picks', 'Strong', 'Value+']
export const SORT_OPTIONS = ['By time', 'By probability']

export function leagueOf(e) {
  if (/Czech/i.test(e.league)) return 'Czech Republic'
  if (/Moldova/i.test(e.league)) return 'Moldova'
  return 'Ukraine'
}

export function matchesLeague(e, filter) {
  return filter === 'All' || leagueOf(e) === filter
}

export function matchesTime(e, filter) {
  if (filter === 'All') return true
  const mins = (e.startTime - Date.now()) / 60000
  if (mins <= 0) return false
  if (filter === 'Next hour') return mins <= 60
  if (filter === 'Next 3h') return mins <= 180
  return true
}

export function matchesTier(e, filter) {
  if (filter === 'All picks') return true
  if (!e.best) return false
  if (filter === 'Strong') return e.best.tier === 'strong'
  if (filter === 'Value+') return e.best.tier === 'strong' || e.best.tier === 'value'
  return true
}

export function sortEvents(events, sortBy) {
  const copy = [...events]
  if (sortBy === 'By probability') {
    copy.sort((a, b) => (b.best?.prob ?? 0) - (a.best?.prob ?? 0) || a.startTime - b.startTime)
  } else {
    copy.sort((a, b) => a.startTime - b.startTime)
  }
  return copy
}

/** Server slip legs when present; otherwise derive from events (legacy snapshots). */
export function resolveSlipPicks(events, slip) {
  if (slip?.legs?.length) {
    return slip.legs.map((leg) => ({
      ...leg,
      best: leg.best,
    }))
  }
  return events
    .filter(
      (e) =>
        e.best &&
        e.best.tier !== 'lean' &&
        e.best.qualified !== false &&
        e.best.prob >= 0.60 &&
        e.best.confidence !== 'low' &&
        e.startTime > Date.now() &&
        e.best.selection,
    )
    .sort((a, b) => b.best.prob - a.best.prob)
    .slice(0, 6)
}
