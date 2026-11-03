import clsx from 'clsx'
import type { ReactNode } from 'react'

export interface TabItem<T extends string> {
  id: T
  label: string
  count?: number
  icon?: ReactNode
}

/** Accessible tab list with roving focus: arrow keys, Home and End move selection and focus together. */
export function Tabs<T extends string>({ items, value, onChange, label }: { items: TabItem<T>[]; value: T; onChange: (id: T) => void; label: string }) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className="flex gap-1 overflow-x-auto border-b border-line px-2"
      onKeyDown={(event) => {
        const tabs = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')]
        const focused = tabs.indexOf(document.activeElement as HTMLButtonElement)
        const index = focused >= 0 ? focused : items.findIndex((i) => i.id === value)
        const target = {
          ArrowRight: (index + 1) % items.length,
          ArrowLeft: (index - 1 + items.length) % items.length,
          Home: 0,
          End: items.length - 1,
        }[event.key]
        if (target === undefined) return
        event.preventDefault()
        onChange(items[target].id)
        // Focus follows selection; otherwise focus is left on a tab that just left the tab order.
        tabs[target]?.focus()
      }}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === value}
          tabIndex={item.id === value ? 0 : -1}
          onClick={() => onChange(item.id)}
          className={clsx(
            '-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] font-medium transition-colors',
            item.id === value ? 'border-accent text-fg' : 'border-transparent text-fg-muted hover:text-fg',
          )}
        >
          {item.icon}
          {item.label}
          {item.count !== undefined && (
            <span className="rounded bg-elevated px-1.5 font-mono text-[10px] text-fg-subtle">{item.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}
