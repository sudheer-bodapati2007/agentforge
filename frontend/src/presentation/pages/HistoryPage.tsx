import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, History } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useGateways } from '@/application/gateways-context'
import { useProjects } from '@/application/use-cases/projects'
import { runKeys, useRuns } from '@/application/use-cases/runs'
import { RUN_STATUS_META, RUN_STATUSES, type Run, type RunStatus } from '@/domain/run'
import { PageHeader } from '../components/PageHeader'
import { ModelBadge } from '../components/runs/RunList'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { describeEvent } from '../lib/events'
import { formatDateTime, formatDuration } from '../lib/format'

const PAGE_SIZE = 20

function EventLog({ runId }: { runId: string }) {
  const { runs } = useGateways()
  const query = useQuery({ queryKey: runKeys.part(runId, 'events'), queryFn: () => runs.events(runId) })
  if (query.isError) return <ErrorState error={query.error} title="Could not load the event history" onRetry={() => query.refetch()} />
  if (!query.data) return <LoadingBlock label="Loading events" rows={3} />
  if (query.data.length === 0) return <p className="text-xs text-fg-subtle">No events recorded.</p>
  return (
    <ol className="max-h-80 space-y-1 overflow-y-auto font-mono text-xs" aria-label="Event history">
      {query.data.map((event) => (
        <li key={event.id} className="grid grid-cols-[72px_150px_1fr] gap-2">
          <time className="text-fg-subtle" dateTime={event.createdAt.toISOString()}>
            {event.createdAt.toLocaleTimeString(undefined, { hour12: false })}
          </time>
          <span className="truncate text-fg-muted">
            {event.type}
            {event.node ? ` · ${event.node}` : ''}
          </span>
          <span className="break-words text-fg">{describeEvent(event)}</span>
        </li>
      ))}
    </ol>
  )
}

function RunRow({ run }: { run: Run }) {
  const [open, setOpen] = useState(false)
  const tests = run.finalReport?.verified.tests
  return (
    <li className="px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <button
          type="button"
          aria-expanded={open}
          aria-label={`${open ? 'Hide' : 'Show'} history of run ${run.id.slice(0, 8)}`}
          onClick={() => setOpen((v) => !v)}
          className="text-fg-muted hover:text-fg"
        >
          {open ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
        </button>
        <div className="min-w-0 flex-1">
          <Link to={`/runs/${run.id}`} className="truncate text-[13px] font-medium text-fg hover:text-accent">
            {run.projectName} · run {run.id.slice(0, 8)}
          </Link>
          <p className="text-xs text-fg-subtle">{formatDateTime(run.createdAt)}</p>
        </div>
        <ModelBadge run={run} />
        {tests?.executed && (
          <span className="font-mono text-xs text-fg-muted">
            {tests.passed}/{tests.total} tests
          </span>
        )}
        <span className="w-14 text-right font-mono text-xs text-fg-subtle">{formatDuration(run.durationSeconds)}</span>
        <RunStatusBadge status={run.status} />
      </div>
      {open && (
        <div className="mt-2 rounded-md border border-line bg-canvas p-3">
          <EventLog runId={run.id} />
        </div>
      )}
    </li>
  )
}

export function HistoryPage() {
  const projects = useProjects('')
  const [projectId, setProjectId] = useState('')
  const [status, setStatus] = useState<RunStatus | ''>('')
  const [page, setPage] = useState(0)
  const query = useRuns({ projectId: projectId || undefined, status: status || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
  const total = query.data?.total ?? 0
  const select = 'h-9 max-w-56 rounded-md border border-line-strong bg-panel px-2 text-sm text-fg'

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Execution History"
        description="Every run with its complete, persisted event log: agent steps, retrieved documents, test runs and decisions."
        actions={
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filter by project"
              className={select}
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value)
                setPage(0)
              }}
            >
              <option value="">All projects</option>
              {(projects.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by status"
              className={select}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as RunStatus | '')
                setPage(0)
              }}
            >
              <option value="">All statuses</option>
              {RUN_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {RUN_STATUS_META[s].label}
                </option>
              ))}
            </select>
          </div>
        }
      />
      <Panel bodyClassName="p-0">
        {query.isError ? (
          <div className="p-4">
            <ErrorState error={query.error} title="Could not load runs" onRetry={() => query.refetch()} />
          </div>
        ) : !query.data ? (
          <div className="p-4">
            <LoadingBlock label="Loading runs" rows={4} />
          </div>
        ) : query.data.items.length === 0 ? (
          <EmptyState
            icon={<History className="size-5" />}
            title={projectId || status ? 'No runs match these filters' : 'No runs yet'}
            description="Runs appear here, with their full event history, once a project has been run."
          />
        ) : (
          <ul className="divide-y divide-line">
            {query.data.items.map((run) => (
              <RunRow key={run.id} run={run} />
            ))}
          </ul>
        )}
      </Panel>
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-2 text-xs text-fg-muted">
          <span>
            {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}
          </span>
          <button type="button" className="rounded border border-line px-2 py-1 disabled:opacity-40" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <button type="button" className="rounded border border-line px-2 py-1 disabled:opacity-40" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  )
}
