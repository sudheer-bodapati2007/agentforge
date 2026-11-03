import { Workflow } from 'lucide-react'
import { useState } from 'react'
import { useRuns } from '@/application/use-cases/runs'
import { RUN_STATUS_META, RUN_STATUSES, type RunStatus } from '@/domain/run'
import { PageHeader } from '../components/PageHeader'
import { RunList } from '../components/runs/RunList'
import { ButtonLink } from '../components/ui/Button'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'

const PAGE_SIZE = 25

/** Every workflow run across the user's projects, newest first. */
export function RunsPage({ title = 'All workflows', description = 'Every workflow run across your projects.' }) {
  const [status, setStatus] = useState<RunStatus | ''>('')
  const [page, setPage] = useState(0)
  const query = useRuns({ status: status || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
  const total = query.data?.total ?? 0

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title={title}
        description={description}
        actions={
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as RunStatus | '')
              setPage(0)
            }}
            className="h-9 rounded-md border border-line-strong bg-panel px-3 text-sm text-fg"
          >
            <option value="">All statuses</option>
            {RUN_STATUSES.map((s) => (
              <option key={s} value={s}>
                {RUN_STATUS_META[s].label}
              </option>
            ))}
          </select>
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
            icon={<Workflow className="size-5" />}
            title={status ? 'No runs with this status' : 'No workflow runs yet'}
            description="Open a project and use Run Project to start the agent workflow."
            action={<ButtonLink to="/projects">Go to projects</ButtonLink>}
          />
        ) : (
          <RunList runs={query.data.items} showProject />
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
