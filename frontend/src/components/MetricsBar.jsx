import React from 'react'

/** Walk-forward backtest summary from the model. */
export default function MetricsBar({ metrics }) {
  if (!metrics?.hit_rate) return null

  const strong = metrics.by_tier?.strong
  const value = metrics.by_tier?.value
  const byMarket = metrics.by_market

  return (
    <div className="mt-6 rounded-2xl border border-ink-700/80 bg-ink-900/40 px-4 py-3.5 md:px-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] tracking-wide text-zinc-500 uppercase">Model track record</p>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500">
            Walk-forward on {metrics.n?.toLocaleString()} recent matches
            {metrics.calibration_version ? ' · calibrated' : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 sm:gap-6">
          <Stat label="Overall" value={`${Math.round(metrics.hit_rate * 100)}%`} />
          {strong && (
            <Stat
              label={`Strong (${strong.n})`}
              value={`${Math.round(strong.rate * 100)}%`}
              accent
            />
          )}
          {value && <Stat label={`Value (${value.n})`} value={`${Math.round(value.rate * 100)}%`} />}
        </div>
      </div>
      {byMarket && Object.keys(byMarket).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3 border-t border-ink-800/80 pt-3">
          {Object.entries(byMarket).map(([mid, v]) => (
            <span key={mid} className="font-mono text-[10px] text-zinc-500">
              {mid === '186' ? 'Winner' : mid === '245' ? 'Set 1' : 'Totals'}{' '}
              <span className="text-zinc-300">{Math.round(v.rate * 100)}%</span>
              <span className="text-zinc-600"> n={v.n}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent = false }) {
  return (
    <div className="text-right">
      <p className="font-mono text-lg font-semibold text-zinc-100">
        <span className={accent ? 'text-emerald-300' : ''}>{value}</span>
      </p>
      <p className="text-[10px] tracking-wide text-zinc-500 uppercase">{label}</p>
    </div>
  )
}
