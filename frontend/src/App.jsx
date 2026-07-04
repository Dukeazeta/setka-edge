import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowsClockwise, WifiSlash } from '@phosphor-icons/react'
import { usePredictions } from './usePredictions.js'
import { PulseDot, SkeletonRow } from './components/atoms.jsx'
import EventRow from './components/EventRow.jsx'
import BetSlip from './components/BetSlip.jsx'

const LEAGUE_FILTERS = ['All', 'Ukraine', 'Czech Republic', 'Moldova']

function leagueOf(e) {
  if (/Czech/i.test(e.league)) return 'Czech Republic'
  if (/Moldova/i.test(e.league)) return 'Moldova'
  return 'Ukraine'
}

export default function App() {
  const { status, data, error, waking, forceRefresh } = usePredictions()
  const [filter, setFilter] = useState('All')

  const events = useMemo(() => {
    const all = data?.events || []
    return filter === 'All' ? all : all.filter((e) => leagueOf(e) === filter)
  }, [data, filter])

  const updated = data?.updatedAt
    ? new Date(data.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="min-h-[100dvh]">
      <div className="mx-auto max-w-[1400px] px-4 pb-24 md:px-10">
        {/* Asymmetric header: heavy left block, meta on the right */}
        <header className="grid grid-cols-1 gap-6 pt-10 md:grid-cols-[2fr_1fr] md:items-end md:pt-16">
          <div>
            <div className="flex items-center gap-2.5">
              <PulseDot />
              <span className="font-mono text-xs tracking-widest text-zinc-500 uppercase">
                {waking ? 'waking server' : 'live model · refreshes when active'}
              </span>
            </div>
            <h1 className="mt-3 text-4xl font-bold tracking-tighter text-zinc-50 md:text-6xl md:leading-none">
              Setka Edge
            </h1>
            <p className="mt-3 max-w-[52ch] text-base leading-relaxed text-zinc-400">
              Every unstarted Setka Cup match on SportyBet, priced against ten days of official
              results. The model surfaces the single best market per game.
            </p>
          </div>
          <div className="flex items-center gap-4 md:justify-end">
            {updated && (
              <span className="font-mono text-xs text-zinc-500">
                updated {updated}
                {data?.historyMatches ? ` · ${data.historyMatches.toLocaleString()} matches learned` : ''}
              </span>
            )}
            <motion.button
              type="button"
              onClick={forceRefresh}
              whileTap={{ scale: 0.96 }}
              className="inline-flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-500"
            >
              <ArrowsClockwise size={15} weight="bold" />
              Refresh
            </motion.button>
          </div>
        </header>

        {/* Cold start / refresh banners */}
        {waking && status === 'loading' && (
          <div className="mt-8 rounded-2xl border border-ink-700 bg-ink-900/80 px-5 py-4">
            <p className="font-medium text-zinc-200">Waking the server</p>
            <p className="mt-1 max-w-[58ch] text-sm leading-relaxed text-zinc-500">
              On Render free tier the app sleeps after inactivity. First visit can take up to a
              minute while the container starts and the model loads fresh data.
            </p>
          </div>
        )}

        {status === 'ready' && data?.refreshing && (
          <div className="mt-8 rounded-2xl border border-emerald-400/20 bg-emerald-400/5 px-5 py-3">
            <p className="text-sm text-emerald-300">Refreshing predictions from SportyBet and Setka Cup…</p>
          </div>
        )}

        {/* League filter */}
        <nav className="mt-10 flex flex-wrap gap-2">
          {LEAGUE_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`rounded-full px-4 py-1.5 text-sm transition-all active:scale-[0.97] ${
                filter === f
                  ? 'bg-zinc-100 font-medium text-zinc-900'
                  : 'border border-ink-700 text-zinc-400 hover:border-zinc-500'
              }`}
            >
              {f}
            </button>
          ))}
        </nav>

        {/* Asymmetric body: 2fr feed / 1fr slip */}
        <main className="mt-8 grid grid-cols-1 gap-12 lg:grid-cols-[2fr_1fr]">
          <section>
            {status === 'loading' && (
              <div>
                {Array.from({ length: 7 }).map((_, i) => (
                  <SkeletonRow key={i} />
                ))}
              </div>
            )}

            {status === 'error' && (
              <div className="flex flex-col items-start gap-4 border-t border-ink-800 pt-10">
                <WifiSlash size={28} className="text-zinc-600" />
                <div>
                  <p className="font-medium text-zinc-300">Can't reach the prediction engine.</p>
                  <p className="mt-1 max-w-[48ch] text-sm leading-relaxed text-zinc-500">
                    The server may still be waking on Render, or the fetch failed. Wait a moment and
                    retry. Error: {error}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="rounded-full border border-ink-700 px-4 py-1.5 text-sm text-zinc-300 hover:border-zinc-500 active:scale-[0.97]"
                >
                  Retry
                </button>
              </div>
            )}

            {status === 'ready' && events.length === 0 && (
              <div className="border-t border-ink-800 pt-12">
                <p className="font-medium text-zinc-300">No upcoming matches on the board.</p>
                <p className="mt-2 max-w-[52ch] text-sm leading-relaxed text-zinc-500">
                  SportyBet lists Setka Cup fixtures in rolling batches through the day. Leave this
                  open — the feed re-checks every minute and new matches will drop in by themselves.
                </p>
              </div>
            )}

            {status === 'ready' &&
              events.map((e, i) => <EventRow key={e.eventId} event={e} index={i} />)}
          </section>

          <aside>
            {status === 'ready' && <BetSlip events={data?.events || []} />}
          </aside>
        </main>

        <footer className="mt-20 border-t border-ink-800 pt-6">
          <p className="max-w-[70ch] text-xs leading-relaxed text-zinc-600">
            Setka Edge is a statistics explorer, not betting advice. Table tennis daily leagues are
            extremely volatile; no pick is safe. Never stake money you can't afford to lose. 18+,
            bet responsibly.
          </p>
        </footer>
      </div>
    </div>
  )
}
