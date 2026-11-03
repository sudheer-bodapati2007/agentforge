import { Bot, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Run } from '@/domain/run'
import { formatDuration, formatRelativeTime } from '../../lib/format'
import { Badge, RunStatusBadge } from '../ui/StatusBadge'

export function ModelBadge({ run }: { run: Pick<Run, 'llmModel' | 'demoModel'> }) {
  if (run.demoModel) {
    return (
      <Badge tone="warning" className="gap-1">
        <Sparkles className="size-3" aria-hidden /> Demo model (not AI)
      </Badge>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[11px] text-fg-subtle">
      <Bot className="size-3" aria-hidden />
      {run.llmModel ?? 'unknown model'}
    </span>
  )
}

export function RunList({ runs, showProject = false }: { runs: Run[]; showProject?: boolean }) {
  return (
    <ul className="divide-y divide-line">
      {runs.map((run) => {
        const tests = run.finalReport?.verified.tests
        return (
          <li key={run.id}>
            <Link to={`/runs/${run.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-hover">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-fg">
                  {showProject ? run.projectName : `Run ${run.id.slice(0, 8)}`}
                </p>
                <p className="text-xs text-fg-subtle">
                  {formatRelativeTime(run.createdAt)}
                  {run.currentNode && !run.finishedAt ? ` · ${run.currentNode.replace(/_/g, ' ')}` : ''}
                </p>
              </div>
              <ModelBadge run={run} />
              {tests?.executed && (
                <span className="font-mono text-xs text-fg-muted">
                  {tests.passed}/{tests.total} tests
                </span>
              )}
              <span className="w-14 text-right font-mono text-xs text-fg-subtle">{formatDuration(run.durationSeconds)}</span>
              <RunStatusBadge status={run.status} />
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
