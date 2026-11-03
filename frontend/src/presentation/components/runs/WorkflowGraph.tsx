import clsx from 'clsx'
import { lazy, Suspense } from 'react'
import { WORKFLOW_EDGES, WORKFLOW_NODES, type AgentExecution, type NodeState, type WorkflowNodeId } from '@/domain/run'
import { formatDuration } from '../../lib/format'
import { STATE_CLASSES, STATE_LABEL } from './workflow-states'

// React Flow is only downloaded when a run page is opened.
const WorkflowCanvas = lazy(() => import('./WorkflowCanvas'))

function duration(e: AgentExecution): number | null {
  return e.startedAt && e.finishedAt ? (e.finishedAt.getTime() - e.startedAt.getTime()) / 1000 : null
}

/** Every attempt of one step, as recorded by the backend. */
function NodeDetails({ node, executions }: { node: WorkflowNodeId; executions: AgentExecution[] }) {
  const meta = WORKFLOW_NODES.find((n) => n.id === node)!
  const next = WORKFLOW_EDGES.filter((e) => e.from === node)
  return (
    <section aria-label={`${meta.label} details`} className="border-t border-line px-4 py-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-[13px] font-semibold text-fg">{meta.label}</h3>
        {meta.agent && <span className="text-xs text-fg-subtle">{meta.agent} agent</span>}
        {next.length > 0 && (
          <span className="text-[11px] text-fg-subtle">
            next: {next.map((e) => `${WORKFLOW_NODES.find((n) => n.id === e.to)!.label}${e.label ? ` (${e.label})` : ''}`).join(' · ')}
          </span>
        )}
      </div>
      {executions.length === 0 ? (
        <p className="text-xs text-fg-subtle">Not executed in this run.</p>
      ) : (
        <ol className="space-y-1.5">
          {executions.map((e) => (
            <li key={e.id} className="grid grid-cols-[4.5rem_1fr_auto] gap-x-3 text-xs">
              <span className="font-mono text-fg-muted">attempt {e.attempt}</span>
              <span className={e.error ? 'text-danger' : 'text-fg'}>
                <span className="mr-2 text-fg-subtle">{e.status}</span>
                {e.error ?? e.summary ?? ''}
              </span>
              <span className="text-right font-mono text-fg-subtle">
                {formatDuration(duration(e))}
                {e.inputTokens + e.outputTokens > 0 && ` · ${(e.inputTokens + e.outputTokens).toLocaleString()} tok`}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/**
 * The LangGraph workflow with each step's state (from confirmed backend records only).
 * The interactive graph is for pointer users on wider screens; the step list carries the
 * same information for keyboards and screen readers, and is the only view on phones.
 */
export function WorkflowGraph({
  states,
  executions,
  selected,
  onSelect,
}: {
  states: Record<WorkflowNodeId, NodeState>
  executions: Map<string, AgentExecution[]>
  selected: WorkflowNodeId | null
  onSelect: (node: WorkflowNodeId | null) => void
}) {
  const attempts = Object.fromEntries([...executions].map(([node, list]) => [node, list.length]))
  return (
    <div>
      <div className="hidden md:block" aria-hidden>
        <Suspense fallback={<div className="h-[380px] animate-pulse bg-elevated/30" />}>
          <WorkflowCanvas states={states} attempts={attempts} selected={selected} onSelect={(n) => onSelect(n === selected ? null : n)} />
        </Suspense>
      </div>
      <ol aria-label="Workflow progress" className="flex flex-wrap gap-1.5 p-3 md:sr-only">
        {WORKFLOW_NODES.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              aria-pressed={selected === node.id}
              aria-label={`${node.label}: ${STATE_LABEL[states[node.id]]}${(attempts[node.id] ?? 0) > 1 ? `, ${attempts[node.id]} attempts` : ''}`}
              onClick={() => onSelect(selected === node.id ? null : node.id)}
              className={clsx(
                'rounded-md border px-2 py-1 text-left text-[12px]',
                STATE_CLASSES[states[node.id]],
                selected === node.id && 'ring-2 ring-accent',
              )}
            >
              {node.label}
              <span className="ml-1.5 text-[10px] text-fg-subtle">{STATE_LABEL[states[node.id]]}</span>
            </button>
          </li>
        ))}
      </ol>
      {selected && <NodeDetails node={selected} executions={executions.get(selected) ?? []} />}
    </div>
  )
}
