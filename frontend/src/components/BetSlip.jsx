import React from 'react'
import { motion } from 'framer-motion'
import { Lightning } from '@phosphor-icons/react'
import { TierBadge } from './atoms.jsx'

const fmtTime = (ms) =>
  new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** Right rail: the model's strongest currently-playable picks, acca odds product. */
export default function BetSlip({ events }) {
  const picks = events
    .filter((e) => e.best && e.best.tier !== 'lean' && e.startTime > Date.now())
    .sort((a, b) => b.best.score - a.best.score)
    .slice(0, 6)

  const acca = picks.reduce((acc, e) => acc * e.best.odds, 1)

  return (
    <div className="lg:sticky lg:top-8">
      <div className="flex items-center gap-2">
        <Lightning size={16} weight="fill" className="text-emerald-300" />
        <h2 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Today's sharpest slip
        </h2>
      </div>

      {picks.length === 0 ? (
        <p className="mt-6 border-t border-ink-800 pt-6 text-sm leading-relaxed text-zinc-500">
          Nothing clears the strong or value bar right now. New markets open through the day —
          the board refreshes automatically every 20 minutes.
        </p>
      ) : (
        <>
          <div className="mt-4 divide-y divide-ink-800 border-t border-ink-800">
            {picks.map((e, i) => (
              <motion.div
                key={e.eventId}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ type: 'spring', stiffness: 100, damping: 20, delay: 0.3 + i * 0.08 }}
                className="py-3.5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-xs text-zinc-500">{fmtTime(e.startTime)}</span>
                  <TierBadge tier={e.best.tier} />
                </div>
                <div className="mt-1 truncate text-sm text-zinc-200">{e.best.bet}</div>
                <div className="mt-0.5 flex items-center justify-between">
                  <span className="truncate text-xs text-zinc-500">
                    {e.home} vs {e.away}
                  </span>
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
        </>
      )}

      <p className="mt-8 max-w-[38ch] text-xs leading-relaxed text-zinc-600">
        Model probabilities come from the last 10 days of official Setka Cup results and direct
        head-to-heads, priced against live SportyBet odds. Past form is a weak oracle — stake
        accordingly.
      </p>
    </div>
  )
}
