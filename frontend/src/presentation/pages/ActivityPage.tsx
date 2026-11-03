import { Activity, Bot, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useRunAgents, useRuns } from '@/application/use-cases/runs'
import { WORKFLOW_NODES, isActive, type Run } from '@/domain/run'
import { PageHeader } from '../components/PageHeader'
import { ModelBadge, RunList } from '../components/runs/RunList'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { formatDuration, formatRelativeTime } from '../lib/format'

const RECENT_RUNS = 100 // the API's page limit; older runs are not "activity"

function stepLabel(node: string | null): string {
  return WORKFLOW_NODES.find((n) => n.id === node)?.label ?? (node ? node.replace(/_/g, ' ') : 'queued')
}

function ActiveRun({ run, now }: { run: Run; now: number }) {
  const agents = useRunAgents(run.id, true)
  const current = [...(agents.data ?? [])].reverse().find((e) => e.status === 'running')
  const elapsed = current?.startedAt ? (now - current.startedAt.getTime()) / 1000 : null
  return (
    <li>
      <Link to={`/runs/${run.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-hover">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-info/40 bg-info-soft text-info" aria-hidden>
          {run.status === 'running' ? <LoaderCircle className="size-4 animate-spin" /> : <Bot className="size-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-fg">{run.projectName}</p>
          <p className="truncate text-xs text-fg-muted">
            {run.status === 'awaiting_approval'
              ? `Waiting for your decision at ${stepLabel(run.currentNode)}`
              : current
                ? `${current.agent ?? 'system'} · ${stepLabel(current.node)}${current.attempt > 1 ? ` (attempt ${current.attempt})` : ''}`
                : stepLabel(run.currentNode)}
          </p>
        </div>
        <ModelBadge run={run} />
        <span className="w-24 text-right font-mono text-xs text-fg-subtle" title="Time in the current step">
          {elapsed !== null ? formatDuration(elapsed) : run.startedAt ? `started ${formatRelativeTime(run.startedAt)}` : 'not started'}
        </span>
        <RunStatusBadge status={run.status} />
      </Link>
    </li>
  )
}

export function ActivityPage() {
  const query = useRuns({ limit: RECENT_RUNS })
  const runs = query.data?.items ?? []
  const active = runs.filter((r) => isActive(r.status))
  const finished = runs.filter((r) => !isActive(r.status)).slice(0, 5)
  // "Now" is when the list was last fetched (every few seconds while runs are active).
  const now = query.dataUpdatedAt

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Agent Activity"
        description="Which agent is working on which run right now. Refreshes every few seconds while anything is active."
      />
      {query.isError ? (
        <ErrorState error={query.error} title="Could not load activity" onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <Panel>
          <LoadingBlock label="Loading activity" rows={3} />
        </Panel>
      ) : (
        <>
          <Panel title={`Working now (${active.length})`} icon={<Activity className="size-4" />} bodyClassName="p-0">
            {active.length === 0 ? (
              <EmptyState icon={<Bot className="size-5" />} title="No agents are working right now" description="Start a run from a project to see its agents here live." />
            ) : (
              <ul className="divide-y divide-line" aria-label="Active runs">
                {active.map((run) => (
                  <ActiveRun key={run.id} run={run} now={now} />
                ))}
              </ul>
            )}
          </Panel>
          {finished.length > 0 && (
            <Panel title="Recently finished" bodyClassName="p-0">
              <RunList runs={finished} showProject />
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
