import clsx from 'clsx'
import { CircleAlert, CircleCheck, CircleDashed, LoaderCircle } from 'lucide-react'
import type { AgentExecution } from '@/domain/run'
import { formatDuration } from '../../lib/format'

const ICON = {
  completed: <CircleCheck className="size-4 text-success" aria-label="completed" />,
  failed: <CircleAlert className="size-4 text-danger" aria-label="failed" />,
  running: <LoaderCircle className="size-4 animate-spin text-info" aria-label="running" />,
  pending: <CircleDashed className="size-4 text-fg-subtle" aria-label="pending" />,
  skipped: <CircleDashed className="size-4 text-fg-subtle" aria-label="skipped" />,
}

function duration(e: AgentExecution): number | null {
  return e.startedAt && e.finishedAt ? (e.finishedAt.getTime() - e.startedAt.getTime()) / 1000 : null
}

/** Agent activity as recorded by the backend: one row per executed step and attempt. */
export function AgentTimeline({
  executions,
  selected,
  onSelect,
}: {
  executions: AgentExecution[]
  selected?: string | null
  onSelect?: (id: string) => void
}) {
  if (executions.length === 0) {
    return <p className="px-4 py-6 text-center text-[13px] text-fg-subtle">Waiting for the first agent to start…</p>
  }
  return (
    <ol className="divide-y divide-line">
      {executions.map((e) => (
        <li key={e.id}>
          <button
            type="button"
            onClick={() => onSelect?.(e.id)}
            aria-current={selected === e.id || undefined}
            className={clsx(
              'flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-hover',
              selected === e.id && 'bg-accent-soft',
            )}
          >
            <span className="mt-0.5">{ICON[e.status]}</span>
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline gap-2">
                <span className="text-[13px] font-medium text-fg capitalize">{e.node.replace(/_/g, ' ')}</span>
                {e.attempt > 1 && <span className="font-mono text-[11px] text-fg-subtle">#{e.attempt}</span>}
                {e.agent && <span className="text-[11px] text-fg-subtle">{e.agent}</span>}
              </span>
              {(e.error || e.summary) && (
                <span className={clsx('mt-0.5 block text-xs', e.error ? 'text-danger' : 'text-fg-muted')}>
                  {e.error ?? e.summary}
                </span>
              )}
            </span>
            <span className="shrink-0 text-right font-mono text-[11px] text-fg-subtle">
              {formatDuration(duration(e))}
              {e.inputTokens + e.outputTokens > 0 && (
                <span className="block">{(e.inputTokens + e.outputTokens).toLocaleString()} tok</span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
