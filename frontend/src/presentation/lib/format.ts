/** Display formatting. `null` always renders as an em dash, never as zero. */
export const NO_DATA = '—'

export function formatPercent(value: number | null): string {
  return value === null ? NO_DATA : `${(value * 100).toFixed(value === 1 ? 0 : 1)}%`
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return NO_DATA
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return minutes < 60 ? `${minutes}m ${rest}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1000) return `${bytes} B`
  return bytes < 1_000_000 ? `${(bytes / 1000).toFixed(1)} KB` : `${(bytes / 1_000_000).toFixed(1)} MB`
}

export function formatUsd(value: number | null): string {
  if (value === null) return NO_DATA
  return value < 0.01 && value > 0 ? '<$0.01' : `$${value.toFixed(2)}`
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function formatRelativeTime(date: Date, now: Date = new Date()): string {
  const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000)
  const abs = Math.abs(diffSeconds)
  if (abs < 45) return 'just now'
  if (abs < 3600) return relative.format(Math.round(diffSeconds / 60), 'minute')
  if (abs < 86_400) return relative.format(Math.round(diffSeconds / 3600), 'hour')
  if (abs < 2_592_000) return relative.format(Math.round(diffSeconds / 86_400), 'day')
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(date: Date): string {
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
