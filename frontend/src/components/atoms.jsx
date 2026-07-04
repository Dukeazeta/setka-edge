import React from 'react'
import { motion } from 'framer-motion'

/** Perpetual pulsing status dot, isolated so the loop never re-renders parents. */
export const PulseDot = React.memo(function PulseDot({ color = 'bg-emerald-400' }) {
  return (
    <span className="relative flex h-2 w-2">
      <motion.span
        className={`absolute inline-flex h-full w-full rounded-full ${color} opacity-60`}
        animate={{ scale: [1, 2.1], opacity: [0.6, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
      />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  )
})

export function TierBadge({ tier }) {
  const styles = {
    strong: 'text-emerald-300 border-emerald-400/30 bg-emerald-400/10',
    value: 'text-sky-300 border-sky-400/25 bg-sky-400/10',
    lean: 'text-zinc-400 border-zinc-500/30 bg-zinc-500/10',
  }
  const labels = { strong: 'Strong', value: 'Value', lean: 'Lean' }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium tracking-wide uppercase ${styles[tier] || styles.lean}`}
    >
      {labels[tier] || tier}
    </span>
  )
}

export function ProbBar({ value }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-ink-700">
      <motion.div
        className="h-full rounded-full bg-emerald-400/80"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: value }}
        style={{ originX: 0 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
      />
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-t border-ink-800 py-4 md:gap-6 md:py-5">
      <div className="skeleton h-8 w-14 rounded md:h-3 md:w-12" />
      <div className="space-y-2">
        <div className="skeleton h-4 w-full max-w-[240px] rounded" />
        <div className="skeleton h-4 w-3/4 max-w-[180px] rounded" />
        <div className="skeleton mt-2 h-10 w-full rounded-xl md:hidden" />
      </div>
      <div className="skeleton h-9 w-16 rounded-lg" />
    </div>
  )
}
