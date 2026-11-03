import type { ReactNode } from 'react'

interface MetricCardProps {
  label: string
  value: string
  icon: ReactNode
  /** Shown beneath the value; use it to explain "—" values. */
  caption?: string
}

export function MetricCard({ label, value, icon, caption }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4 shadow-panel">
      <div className="flex items-center justify-between text-fg-muted">
        <span className="text-xs font-medium tracking-wide uppercase">{label}</span>
        <span aria-hidden>{icon}</span>
      </div>
      <p className="mt-2 font-mono text-2xl font-medium text-fg tabular-nums">{value}</p>
      {caption && <p className="mt-1 text-xs text-fg-subtle">{caption}</p>}
    </div>
  )
}
