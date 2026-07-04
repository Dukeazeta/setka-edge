import React from 'react'

/** Horizontally scrollable league filters — snap on mobile, wrap on desktop. */
export default function FilterChips({ options, value, onChange }) {
  return (
    <nav className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:overflow-visible md:px-0 snap-x snap-mandatory scrollbar-none">
      {options.map((f) => {
        const active = value === f
        return (
          <button
            key={f}
            type="button"
            onClick={() => onChange(f)}
            className={`shrink-0 snap-start rounded-full px-4 py-2.5 text-sm transition-all active:scale-[0.97] ${
              active
                ? 'bg-zinc-100 font-medium text-zinc-900'
                : 'border border-ink-700 text-zinc-400 hover:border-zinc-500'
            }`}
          >
            {f}
          </button>
        )
      })}
    </nav>
  )
}
