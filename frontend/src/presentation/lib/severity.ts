import type { Severity, StatusTone } from '@/domain/run'

export const SEVERITY_TONE: Record<Severity, StatusTone> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
  info: 'neutral',
}

/** Marker colour for a finding in the code gutter (status colours; the text says the severity too). */
export const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-danger',
  high: 'bg-danger',
  medium: 'bg-warning',
  low: 'bg-info',
  info: 'bg-fg-subtle',
}
