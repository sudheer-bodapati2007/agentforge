import clsx from 'clsx'
import { CircleAlert, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { toAppError } from '@/application/errors'
import { Button } from './Button'

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={clsx('flex flex-col items-center justify-center px-6 py-10 text-center', className)}>
      {icon && (
        <div className="mb-3 grid size-10 place-items-center rounded-lg border border-line-strong bg-elevated text-fg-muted">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-fg">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-fg-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({
  error,
  title = 'Could not load data',
  onRetry,
}: {
  error: unknown
  title?: string
  onRetry?: () => void
}) {
  const appError = toAppError(error)
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-lg border border-danger/25 bg-danger-soft p-4 sm:flex-row sm:items-center"
    >
      <CircleAlert className="size-5 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{title}</p>
        <p className="text-[13px] text-fg-muted">{appError.message}</p>
      </div>
      {onRetry && (
        <Button size="sm" icon={<RotateCw className="size-3.5" />} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded-md bg-elevated', className)} aria-hidden />
}

export function LoadingBlock({ label = 'Loading', rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-label={label} className="space-y-2.5">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={clsx('h-4', i % 2 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}
