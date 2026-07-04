import React, { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CaretDown, Clock } from '@phosphor-icons/react'
import { TierBadge, ProbBar } from './atoms.jsx'

const fmtTime = (ms) =>
  new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const minutesUntil = (ms) => Math.round((ms - Date.now()) / 60000)

function StartsIn({ startTime }) {
  const mins = minutesUntil(startTime)
  if (mins <= 0) return <span className="text-rose-300">starting</span>
  if (mins < 60) return <span>{mins}m</span>
  return <span>{Math.floor(mins / 60)}h {mins % 60}m</span>
}

export default function EventRow({ event, index }) {
  const [open, setOpen] = useState(false)
  const best = event.best

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 100, damping: 20, delay: index * 0.045 }}
      className="border-t border-ink-800"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[3.5rem_1fr_auto] items-center gap-3 py-4 text-left transition-colors hover:bg-ink-900/60 active:scale-[0.995] md:grid-cols-[4rem_2fr_1fr_auto] md:gap-6"
      >
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

        <div className="hidden min-w-0 md:block">
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
            <span className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1 font-mono text-sm font-semibold text-emerald-300">
              {best.odds.toFixed(2)}
            </span>
          )}
          <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ type: 'spring', stiffness: 200, damping: 22 }}>
            <CaretDown size={16} className="text-zinc-500" />
          </motion.span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 140, damping: 24 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 pb-5 pl-[3.5rem] pr-2 md:pl-[4rem]">
              {best && (
                <div className="text-sm text-zinc-300 md:hidden">
                  <TierBadge tier={best.tier} /> <span className="ml-2">{best.bet}</span>
                </div>
              )}
              {(event.picks || []).map((p) => (
                <div key={p.bet} className="grid grid-cols-[1fr_auto_auto] items-center gap-4">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-zinc-300">{p.bet}</div>
                    <div className="mt-1.5 max-w-56">
                      <ProbBar value={p.prob} />
                    </div>
                  </div>
                  <div className="font-mono text-xs text-zinc-500">
                    p {Math.round(p.prob * 100)}% · EV {p.ev > 0 ? '+' : ''}
                    {Math.round(p.ev * 100)}%
                  </div>
                  <div className="font-mono text-sm text-zinc-200">{p.odds.toFixed(2)}</div>
                </div>
              ))}
              {(!event.picks || event.picks.length === 0) && (
                <p className="text-sm text-zinc-600">
                  Markets not yet posted for this match. They usually appear 30 to 60 minutes before start.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
