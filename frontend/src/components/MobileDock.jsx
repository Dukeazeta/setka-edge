import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Copy, Lightning } from '@phosphor-icons/react'

/** Sticky bottom summary on mobile — quick glance at slip + scroll to full list. */
export default function MobileDock({ picks, acca, slip, onScrollToSlip }) {
  const [copied, setCopied] = useState(false)
  if (picks.length === 0) return null

  const top = picks[0]
  const code = slip?.bookingCode

  const copyCode = async (e) => {
    e.stopPropagation()
    if (!code) return
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 120, damping: 22 }}
      className="fixed inset-x-0 bottom-0 z-40 border-t border-ink-800 bg-ink-950/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md md:hidden"
    >
      <button
        type="button"
        onClick={onScrollToSlip}
        className="flex w-full items-center gap-3 text-left active:scale-[0.98]"
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-emerald-400/25 bg-emerald-400/10">
          <Lightning size={18} weight="fill" className="text-emerald-300" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-100">
            {picks.length} high-confidence picks
          </p>
          <p className="truncate text-xs text-zinc-500">
            Top: {Math.round(top.best.prob * 100)}% · {top.best.bet}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-lg font-bold text-zinc-50">{acca.toFixed(2)}</p>
          {code ? (
            <button
              type="button"
              onClick={copyCode}
              className="mt-0.5 inline-flex items-center gap-1 font-mono text-[11px] text-emerald-300"
            >
              {code}
              {copied ? <Check size={12} weight="bold" /> : <Copy size={12} weight="bold" />}
            </button>
          ) : (
            <p className="text-[10px] tracking-wide text-zinc-500 uppercase">combined</p>
          )}
        </div>
      </button>
    </motion.div>
  )
}
