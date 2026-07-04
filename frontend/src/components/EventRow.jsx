import React, { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { CaretDown, Clock } from '@phosphor-icons/react'
import { TierBadge, ProbBar } from './atoms.jsx'

const fmtTime = (ms) =>
  new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const minutesUntil = (ms) => Math.round((ms - Date.now()) / 60000)

function StartsIn({ startTime }) {
  const mins = minutesUntil(startTime)
  if (mins <= 0) return <span className="text-rose-300">live</span>
  if (mins < 60) return <span>{mins}m</span>
  return <span>{Math.floor(mins / 60)}h {mins % 60}m</span>
}

function PlayerNames({ home, away }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-[15px] font-medium leading-tight text-zinc-100">{home}</p>
      <p className="my-0.5 text-[10px] font-medium tracking-widest text-zinc-600 uppercase">vs</p>
      <p className="truncate text-[15px] font-medium leading-tight text-zinc-100">{away}</p>
    </div>
  )
}

export default function EventRow({ event, index }) {
  const [open, setOpen] = useState(false)
  const best = event.best
  const reduceMotion = useReducedMotion()

  const motionProps = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 10 },
        animate: { opacity: 1, y: 0 },
        transition: { type: 'spring', stiffness: 100, damping: 20, delay: Math.min(index * 0.03, 0.3) },
      }

  return (
    <motion.div layout={!reduceMotion} {...motionProps} className="border-t border-ink-800">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full py-4 text-left transition-colors hover:bg-ink-900/50 active:scale-[0.995] md:py-4"
      >
        {/* Mobile layout */}
        <div className="md:hidden">
          <div className="flex items-start justify-between gap-3">
            <div className="font-mono text-xs text-zinc-500">
              <span className="text-sm text-zinc-300">{fmtTime(event.startTime)}</span>
              <span className="ml-2 inline-flex items-center gap-0.5 text-zinc-600">
                <Clock size={10} weight="bold" />
                <StartsIn startTime={event.startTime} />
              </span>
            </div>
            {best && (
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-xs text-zinc-400">{Math.round(best.prob * 100)}%</span>
                <span className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2 py-1 font-mono text-sm font-semibold text-emerald-300">
                  {best.odds.toFixed(2)}
                </span>
              </div>
            )}
          </div>

          <div className="mt-3 flex items-start justify-between gap-3">
            <PlayerNames home={event.home} away={event.away} />
            <motion.span
              animate={{ rotate: open ? 180 : 0 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
              className="mt-1 shrink-0 p-1"
            >
              <CaretDown size={18} className="text-zinc-500" />
            </motion.span>
          </div>

          {best ? (
            <div className="mt-3 flex items-center gap-2 rounded-xl border border-ink-700/80 bg-ink-900/40 px-3 py-2.5">
              <TierBadge tier={best.tier} />
              <span className="line-clamp-2 flex-1 text-sm leading-snug text-zinc-300">{best.bet}</span>
            </div>
          ) : (
            <p className="mt-2 text-sm text-zinc-600">{event.note || 'Markets pending'}</p>
          )}

          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-zinc-600">
            <span>{leagueOf(event.league)}</span>
            {event.h2h && (
              <span className="font-mono text-zinc-500">
                H2H {event.h2h.home}-{event.h2h.away}
              </span>
            )}
            <span className="font-mono">n={event.dataQuality}</span>
          </div>
        </div>

        {/* Desktop layout */}
        <div className="hidden md:grid md:grid-cols-[4rem_2fr_1fr_auto] md:items-center md:gap-6">
          <div className="font-mono text-sm text-zinc-500">
            <div>{fmtTime(event.startTime)}</div>
            <div className="mt-0.5 flex items-center gap-1 text-[11px] text-zinc-600">
              <Clock size={11} weight="bold" />
              <StartsIn startTime={event.startTime} />
            </div>
          </div>

          <div className="min-w-0">
            <div className="truncate font-medium text-zinc-100">
              {event.home} <span className="mx-1 text-zinc-600">vs</span> {event.away}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-500">
              <span>{event.league}</span>
              {event.h2h && (
                <span className="font-mono text-zinc-400">
                  H2H {event.h2h.home}-{event.h2h.away}
                </span>
              )}
              <span className="font-mono text-zinc-600">n={event.dataQuality}</span>
            </div>
          </div>

          <div className="min-w-0">
            {best ? (
              <div className="flex items-center gap-2">
                <TierBadge tier={best.tier} />
                <span className="truncate text-sm text-zinc-300">{best.bet}</span>
              </div>
            ) : (
              <span className="text-sm text-zinc-600">{event.note || 'No priced markets'}</span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {best && (
              <>
                <span className="font-mono text-xs text-zinc-400">{Math.round(best.prob * 100)}%</span>
                <span className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1 font-mono text-sm font-semibold text-emerald-300">
                  {best.odds.toFixed(2)}
                </span>
              </>
            )}
            <motion.span
              animate={{ rotate: open ? 180 : 0 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
            >
              <CaretDown size={16} className="text-zinc-500" />
            </motion.span>
          </div>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 140, damping: 24 }}
            className="overflow-hidden"
          >
            <div className="space-y-4 border-t border-ink-800/50 pb-5 pt-3 md:pl-16">
              {(event.picks || []).map((p) => (
                <div
                  key={p.bet}
                  className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4"
                >
                  <div className="min-w-0">
                    <div className="text-sm leading-snug text-zinc-300">{p.bet}</div>
                    <div className="mt-2 max-w-full sm:max-w-56">
                      <ProbBar value={p.prob} />
                    </div>
                  </div>
                  <div className="font-mono text-xs text-zinc-500">
                    p {Math.round(p.prob * 100)}% · EV {p.ev > 0 ? '+' : ''}
                    {Math.round(p.ev * 100)}%
                  </div>
                  <div className="font-mono text-sm font-medium text-zinc-200 sm:text-right">
                    {p.odds.toFixed(2)}
                  </div>
                </div>
              ))}
              {(!event.picks || event.picks.length === 0) && (
                <p className="text-sm text-zinc-600">
                  Markets not yet posted. They usually appear 30 to 60 minutes before start.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function leagueOf(name) {
  if (/Czech/i.test(name)) return 'Czech'
  if (/Moldova/i.test(name)) return 'Moldova'
  return 'Ukraine'
}
