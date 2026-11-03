import clsx from 'clsx'
import type { ReactNode } from 'react'
import { RUN_STATUS_META, type RunStatus, type StatusTone } from '@/domain/run'

const TONE_CLASSES: Record<StatusTone, { badge: string; dot: string }> = {
  neutral: { badge: 'bg-elevated text-fg-muted border-line-strong', dot: 'bg-fg-subtle' },
  info: { badge: 'bg-info-soft text-info border-info/25', dot: 'bg-info' },
  accent: { badge: 'bg-accent-soft text-accent border-accent/25', dot: 'bg-accent' },
  success: { badge: 'bg-success-soft text-success border-success/25', dot: 'bg-success' },
  warning: { badge: 'bg-warning-soft text-warning border-warning/25', dot: 'bg-warning' },
  danger: { badge: 'bg-danger-soft text-danger border-danger/25', dot: 'bg-danger' },
}

interface BadgeProps {
  tone: StatusTone
  children: ReactNode
  pulse?: boolean
  className?: string
}

export function Badge({ tone, children, pulse = false, className }: BadgeProps) {
  const classes = TONE_CLASSES[tone]
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap',
        classes.badge,
        className,
      )}
    >
      <span className={clsx('size-1.5 rounded-full', classes.dot, pulse && 'animate-pulse')} aria-hidden />
      {children}
    </span>
  )
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const meta = RUN_STATUS_META[status]
  return (
    <Badge tone={meta.tone} pulse={status === 'running'}>
      {meta.label}
    </Badge>
  )
}
