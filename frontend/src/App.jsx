import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowsClockwise, WifiSlash } from '@phosphor-icons/react'
import { usePredictions } from './usePredictions.js'
import { PulseDot, SkeletonRow } from './components/atoms.jsx'
import EventRow from './components/EventRow.jsx'
import BetSlip, { useSlipPicks } from './components/BetSlip.jsx'
import FilterChips from './components/FilterChips.jsx'
import MobileDock from './components/MobileDock.jsx'

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

  const slipPicks = useSlipPicks(data?.events || [])
  const slipAcca = slipPicks.reduce((acc, e) => acc * e.best.odds, 1)

  const updated = data?.updatedAt
    ? new Date(data.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

  const scrollToSlip = () => {
    document.getElementById('slip')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="min-h-[100dvh]">
      <div className="mx-auto max-w-[1400px] px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] pt-[max(1.5rem,env(safe-area-inset-top))] md:px-10 md:pb-24 md:pt-10">
        <header className="grid grid-cols-1 gap-5 md:grid-cols-[2fr_1fr] md:items-end md:gap-6 md:pt-6">
          <div>
            <div className="flex items-center gap-2.5">
              <PulseDot />
              <span className="font-mono text-[10px] tracking-widest text-zinc-500 uppercase sm:text-xs">
                {waking ? 'waking server' : 'live model'}
              </span>
            </div>
            <h1 className="mt-2 text-3xl font-bold tracking-tighter text-zinc-50 sm:text-4xl md:text-6xl md:leading-none">
              Setka Edge
            </h1>
            <p className="mt-2 max-w-[52ch] text-sm leading-relaxed text-zinc-400 sm:text-base">
              Setka Cup matches on SportyBet, ranked by highest model probability.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 md:justify-end">
            {updated && (
              <span className="font-mono text-[11px] text-zinc-500 sm:text-xs">
                {updated}
                {data?.historyMatches ? ` · ${data.historyMatches.toLocaleString()} learned` : ''}
              </span>
            )}
            <motion.button
              type="button"
              onClick={forceRefresh}
              whileTap={{ scale: 0.96 }}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500"
            >
              <ArrowsClockwise size={16} weight="bold" />
              Refresh
            </motion.button>
          </div>
        </header>

        {status === 'ready' && data?.events?.length > 0 && (
          <div className="mt-6 grid grid-cols-3 gap-2 border-y border-ink-800 py-3 md:mt-8 md:gap-4">
            <div>
              <p className="font-mono text-lg font-semibold text-zinc-100">{data.events.length}</p>
              <p className="text-[10px] tracking-wide text-zinc-500 uppercase">on board</p>
            </div>
            <div>
              <p className="font-mono text-lg font-semibold text-emerald-300">{slipPicks.length}</p>
              <p className="text-[10px] tracking-wide text-zinc-500 uppercase">58%+ picks</p>
            </div>
            <div>
              <p className="font-mono text-lg font-semibold text-zinc-100">
                {slipPicks.length ? slipAcca.toFixed(2) : '—'}
              </p>
              <p className="text-[10px] tracking-wide text-zinc-500 uppercase">slip odds</p>
            </div>
          </div>
        )}

        {waking && status === 'loading' && (
          <div className="mt-6 rounded-2xl border border-ink-700 bg-ink-900/80 px-4 py-3.5 sm:px-5 sm:py-4">
            <p className="font-medium text-zinc-200">Waking the server</p>
            <p className="mt-1 text-sm leading-relaxed text-zinc-500">
              First visit after sleep can take up to a minute on Render free tier.
            </p>
          </div>
        )}

        {status === 'ready' && data?.refreshing && (
          <div className="mt-6 rounded-2xl border border-emerald-400/20 bg-emerald-400/5 px-4 py-3">
            <p className="text-sm text-emerald-300">Refreshing predictions…</p>
          </div>
        )}

        <div className="mt-6 md:mt-10">
          <FilterChips options={LEAGUE_FILTERS} value={filter} onChange={setFilter} />
        </div>

        {/* Mobile: slip carousel first, then feed. Desktop: side-by-side. */}
        <main className="mt-6 grid grid-cols-1 gap-10 lg:mt-8 lg:grid-cols-[2fr_1fr] lg:gap-12">
          <section className="order-2 lg:order-1">
            {status === 'loading' && (
              <div>
                {Array.from({ length: 6 }).map((_, i) => (
                  <SkeletonRow key={i} />
                ))}
              </div>
            )}

            {status === 'error' && (
              <div className="flex flex-col items-start gap-4 border-t border-ink-800 pt-8">
                <WifiSlash size={28} className="text-zinc-600" />
                <div>
                  <p className="font-medium text-zinc-300">Can't reach the prediction engine.</p>
                  <p className="mt-1 max-w-[48ch] text-sm leading-relaxed text-zinc-500">
                    Server may still be waking. Error: {error}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="min-h-[44px] rounded-full border border-ink-700 px-5 py-2.5 text-sm text-zinc-300 hover:border-zinc-500 active:scale-[0.97]"
                >
                  Retry
                </button>
              </div>
            )}

            {status === 'ready' && events.length === 0 && (
              <div className="border-t border-ink-800 pt-10">
                <p className="font-medium text-zinc-300">No matches for this filter.</p>
                <p className="mt-2 text-sm leading-relaxed text-zinc-500">
                  Fixtures roll in through the day. Try another league or check back shortly.
                </p>
              </div>
            )}

            {status === 'ready' &&
              events.map((e, i) => <EventRow key={e.eventId} event={e} index={i} />)}
          </section>

          <aside className="order-1 lg:order-2">
            {status === 'ready' && <BetSlip events={data?.events || []} id="slip" />}
          </aside>
        </main>

        <footer className="mt-16 border-t border-ink-800 pt-6 md:mt-20">
          <p className="max-w-[70ch] text-xs leading-relaxed text-zinc-600">
            Setka Edge is a statistics explorer, not betting advice. Table tennis daily leagues are
            extremely volatile. Never stake money you can't afford to lose. 18+, bet responsibly.
          </p>
        </footer>
      </div>

      {status === 'ready' && (
        <MobileDock picks={slipPicks} acca={slipAcca} onScrollToSlip={scrollToSlip} />
      )}
    </div>
  )
}
