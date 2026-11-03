import { CircleCheck, Clock, Coins, FlaskConical, FolderKanban, Plus, Rocket, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDashboardMetrics } from '@/application/use-cases/dashboard'
import { useSystemStatus } from '@/application/use-cases/system'
import type { DashboardMetrics } from '@/domain/dashboard'
import { MetricCard } from '../components/MetricCard'
import { PageHeader } from '../components/PageHeader'
import { SystemReadiness } from '../components/SystemReadiness'
import { ButtonLink } from '../components/ui/Button'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from '../components/ui/States'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { formatDuration, formatPercent, formatRelativeTime, formatUsd } from '../lib/format'

const NEW_PROJECT = (
  <ButtonLink to="/projects/new" variant="primary" icon={<Plus className="size-4" />}>
    New Project
  </ButtonLink>
)

function Metrics({ metrics }: { metrics: DashboardMetrics }) {
  const noRuns = 'No finished runs yet'
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <MetricCard label="Projects" value={String(metrics.totalProjects)} icon={<FolderKanban className="size-4" />} />
      <MetricCard label="Workflow runs" value={String(metrics.totalRuns)} icon={<Workflow className="size-4" />} />
      <MetricCard
        label="Completion"
        value={formatPercent(metrics.completionRate)}
        icon={<CircleCheck className="size-4" />}
        caption={metrics.completionRate === null ? noRuns : 'of finished runs'}
      />
      <MetricCard
        label="Test pass rate"
        value={formatPercent(metrics.testPassRate)}
        icon={<FlaskConical className="size-4" />}
        caption={
          metrics.testPassRate === null
            ? 'No executed test suites'
            : `${metrics.executedTestSuites} executed suite${metrics.executedTestSuites === 1 ? '' : 's'}`
        }
      />
      <MetricCard
        label="Avg duration"
        value={formatDuration(metrics.averageDurationSeconds)}
        icon={<Clock className="size-4" />}
        caption={metrics.averageDurationSeconds === null ? noRuns : undefined}
      />
      <MetricCard
        label="Est. LLM cost"
        value={formatUsd(metrics.totalEstimatedCostUsd)}
        icon={<Coins className="size-4" />}
        caption={metrics.totalEstimatedCostUsd === null ? 'No usage recorded' : 'all runs'}
      />
    </div>
  )
}

function Onboarding() {
  return (
    <Panel>
      <EmptyState
        icon={<Rocket className="size-5" />}
        title="Create your first project"
        description="Describe the software you want built. AgentForge's agents will plan, implement, test, review and document it. Metrics appear here once runs exist."
        action={NEW_PROJECT}
      />
    </Panel>
  )
}

export function DashboardPage() {
  const metricsQuery = useDashboardMetrics()
  const statusQuery = useSystemStatus()
  const metrics = metricsQuery.data

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Dashboard" description="Operational overview from persisted workflow data." actions={NEW_PROJECT} />

      {metricsQuery.isError ? (
        <ErrorState error={metricsQuery.error} title="Could not load dashboard metrics" onRetry={() => metricsQuery.refetch()} />
      ) : !metrics ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6" role="status" aria-label="Loading metrics">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-[92px]" />
          ))}
        </div>
      ) : (
        <>
          {metrics.totalProjects === 0 ? <Onboarding /> : <Metrics metrics={metrics} />}
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Recent workflow runs" icon={<Workflow className="size-4" />} className="lg:col-span-2" bodyClassName="p-0">
          {!metrics ? (
            <div className="p-4">
              <LoadingBlock label="Loading runs" />
            </div>
          ) : metrics.recentRuns.length === 0 ? (
            <EmptyState
              title="No workflow runs yet"
              description="Runs appear here when a project is executed. The workflow engine is introduced in Phase 2."
            />
          ) : (
            <ul className="divide-y divide-line">
              {metrics.recentRuns.map((run) => (
                <li key={run.id}>
                  <Link to={`/projects/${run.projectId}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-hover">
                    <span className="min-w-0 flex-1 truncate text-[13px] text-fg">{run.projectName}</span>
                    <span className="font-mono text-xs text-fg-subtle">{formatDuration(run.durationSeconds)}</span>
                    <span className="hidden text-xs text-fg-subtle sm:inline">{formatRelativeTime(run.createdAt)}</span>
                    <RunStatusBadge status={run.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="System readiness" bodyClassName="py-1">
            {statusQuery.isError ? (
              <div className="py-3">
                <ErrorState error={statusQuery.error} title="Backend unreachable" onRetry={() => statusQuery.refetch()} />
              </div>
            ) : statusQuery.data ? (
              <SystemReadiness status={statusQuery.data} />
            ) : (
              <div className="py-3">
                <LoadingBlock label="Loading system status" />
              </div>
            )}
          </Panel>

          <Panel title="Recent projects" icon={<FolderKanban className="size-4" />} bodyClassName="p-0">
            {!metrics ? (
              <div className="p-4">
                <LoadingBlock label="Loading projects" rows={2} />
              </div>
            ) : metrics.recentProjects.length === 0 ? (
              <p className="px-4 py-6 text-center text-[13px] text-fg-subtle">No projects yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {metrics.recentProjects.map((project) => (
                  <li key={project.id}>
                    <Link to={`/projects/${project.id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-hover">
                      <span className="truncate text-[13px] text-fg">{project.name}</span>
                      <span className="shrink-0 text-xs text-fg-subtle">{formatRelativeTime(project.updatedAt)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
