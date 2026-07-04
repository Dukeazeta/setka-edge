import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Copy, Lightning } from '@phosphor-icons/react'
import { TierBadge } from './atoms.jsx'

const fmtTime = (ms) =>
  new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export function useSlipPicks(events) {
  return events
    .filter(
      (e) =>
        e.best &&
        e.best.tier !== 'lean' &&
        e.best.prob >= 0.58 &&
        e.best.confidence !== 'low' &&
        e.startTime > Date.now(),
    )
    .sort((a, b) => b.best.prob - a.best.prob)
    .slice(0, 6)
}

function PickCard({ event, compact = false }) {
  const { best } = event
  return (
    <div
      className={`flex shrink-0 flex-col justify-between rounded-2xl border border-ink-700/80 bg-ink-900/60 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${
        compact ? 'w-[min(88vw,320px)] snap-center' : ''
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-xs text-zinc-500">{fmtTime(event.startTime)}</span>
        <TierBadge tier={best.tier} />
      </div>
      <p className="mt-2 line-clamp-2 text-sm leading-snug text-zinc-100">{best.bet}</p>
      <p className="mt-1 truncate text-xs text-zinc-500">
        {event.home} vs {event.away}
      </p>
      <div className="mt-3 flex items-end justify-between border-t border-ink-800 pt-3">
        <div>
          <span className="font-mono text-xs text-zinc-400">{Math.round(best.prob * 100)}%</span>
          {best.sampleN != null && (
            <span className="ml-2 font-mono text-[10px] text-zinc-600">n={Math.round(best.sampleN)}</span>
          )}
        </div>
        <span className="font-mono text-base font-semibold text-emerald-300">{best.odds.toFixed(2)}</span>
      </div>
    </div>
  )
}

function BookingCode({ slip }) {
  const [copied, setCopied] = useState(false)
  if (!slip?.bookingCode) return null

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(slip.bookingCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <div className="mt-4 rounded-2xl border border-ink-700/80 bg-ink-900/50 p-4">
      <p className="text-[10px] tracking-wide text-zinc-500 uppercase">SportyBet booking code</p>
      <div className="mt-2 flex items-center gap-2">
        <span className="font-mono text-lg font-semibold tracking-wider text-zinc-100">
          {slip.bookingCode}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex min-h-[36px] min-w-[36px] items-center justify-center rounded-full border border-ink-700 text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
          aria-label="Copy booking code"
        >
          {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
        </button>
      </div>
      {slip.shareUrl && (
        <a
          href={slip.shareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs text-emerald-300/90 hover:text-emerald-300"
        >
          Load on SportyBet →
        </a>
      )}
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">
        Paste in SportyBet betslip → Booking Code → Load. Expires when the first leg starts.
      </p>
    </div>
  )
}

/** Desktop rail + mobile horizontal carousel of highest-confidence picks. */
export default function BetSlip({ events, slip, id = 'slip' }) {
  const picks = useSlipPicks(events)
  const acca = picks.reduce((acc, e) => acc * e.best.odds, 1)

  return (
    <div id={id} className="lg:sticky lg:top-8">
      <div className="flex items-center gap-2">
        <Lightning size={16} weight="fill" className="text-emerald-300" />
        <h2 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Highest-confidence slip
        </h2>
      </div>

      {picks.length === 0 ? (
        <p className="mt-6 border-t border-ink-800 pt-6 text-sm leading-relaxed text-zinc-500">
          Nothing clears the 58% confidence bar right now. New markets open through the day —
          the board refreshes automatically when the server is active.
        </p>
      ) : (
        <>
          {/* Mobile: horizontal snap carousel */}
          <div className="scroll-strip-x -mx-4 mt-4 flex gap-3 px-4 pb-2 snap-x snap-mandatory scrollbar-none lg:mx-0 lg:hidden lg:flex-col lg:overflow-visible lg:px-0 lg:pb-0">
            {picks.map((e, i) => (
              <motion.div
                key={e.eventId}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ type: 'spring', stiffness: 100, damping: 20, delay: i * 0.05 }}
              >
                <PickCard event={e} compact />
              </motion.div>
            ))}
          </div>

          {/* Desktop: vertical list */}
          <div className="mt-4 hidden divide-y divide-ink-800 border-t border-ink-800 lg:block">
            {picks.map((e, i) => (
              <motion.div
                key={e.eventId}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ type: 'spring', stiffness: 100, damping: 20, delay: 0.2 + i * 0.06 }}
                className="py-3.5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-xs text-zinc-500">{fmtTime(e.startTime)}</span>
                  <TierBadge tier={e.best.tier} />
                </div>
                <div className="mt-1 text-sm text-zinc-200">{e.best.bet}</div>
                <div className="mt-0.5 flex items-center justify-between gap-2">
                  <span className="truncate text-xs text-zinc-500">
                    {e.home} vs {e.away}
                  </span>
                  <span className="font-mono text-xs text-zinc-400">{Math.round(e.best.prob * 100)}%</span>
                  <span className="font-mono text-sm font-semibold text-emerald-300">
                    {e.best.odds.toFixed(2)}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-ink-800 pt-4">
            <span className="text-xs tracking-wide text-zinc-500 uppercase">
              Combined ({picks.length} legs)
            </span>
            <span className="font-mono text-lg font-bold text-zinc-100">{acca.toFixed(2)}</span>
          </div>

          <BookingCode slip={slip} />

          {slip?.bookingError && !slip?.bookingCode && (
            <p className="mt-3 text-xs leading-relaxed text-zinc-600">
              Booking code unavailable ({slip.bookingError}). Picks are still ranked above — load
              them manually on SportyBet.
            </p>
          )}
        </>
      )}

      <p className="mt-6 max-w-[38ch] text-xs leading-relaxed text-zinc-600 lg:mt-8">
        Probabilities from the last 10 days of Setka Cup results and head-to-heads, priced against
        live SportyBet odds. Past form is a weak oracle — stake accordingly.
      </p>
    </div>
  )
}
