import { Activity, Ban, BookMarked, Database, Download, FileCode2, FlaskConical, History, RotateCw, ScrollText, SearchX, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { AppError, errorMessage } from '@/application/errors'
import {
  useCancelRun,
  useDownloadRun,
  useResumeRun,
  useRun,
  useRunAgents,
  useRunApprovals,
  useRunArtifacts,
  useRunFindings,
  useRunStream,
  useRunTests,
} from '@/application/use-cases/runs'
import { memoryFromEvents } from '@/domain/memory'
import { executionsByNode, isActive, nodeStates, type Run, type WorkflowNodeId } from '@/domain/run'
import { PageHeader } from '../components/PageHeader'
import { AgentTimeline } from '../components/runs/AgentTimeline'
import { DatabasePanel } from '../components/runs/DatabasePanel'
import { MemoryPanel } from '../components/runs/MemoryPanel'
import { ApprovalPanel } from '../components/runs/ApprovalPanel'
import { FilesPanel } from '../components/runs/FilesPanel'
import { FindingsPanel } from '../components/runs/FindingsPanel'
import { ModelBadge } from '../components/runs/RunList'
import { RunReport } from '../components/runs/RunReport'
import { TestResultsPanel } from '../components/runs/TestResultsPanel'
import { WorkflowGraph } from '../components/runs/WorkflowGraph'
import { Button, ButtonLink } from '../components/ui/Button'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { RunStatusBadge } from '../components/ui/StatusBadge'
import { Tabs } from '../components/ui/Tabs'
import { useToast } from '../components/ui/Toast'
import { describeEvent } from '../lib/events'
import { formatDateTime, formatDuration, formatRelativeTime, formatUsd } from '../lib/format'

type Tab = 'files' | 'tests' | 'database' | 'memory' | 'review' | 'report' | 'events'

function RunView({ run }: { run: Run }) {
  const toast = useToast()
  const { events, live } = useRunStream(run.id, run.status)
  const agents = useRunAgents(run.id)
  const artifacts = useRunArtifacts(run.id)
  const tests = useRunTests(run.id)
  const findings = useRunFindings(run.id)
  const approvals = useRunApprovals(run.id)
  const cancel = useCancelRun()
  const resume = useResumeRun()
  const download = useDownloadRun()
  const [tab, setTab] = useState<Tab>(run.finalReport ? 'report' : 'files')
  const [file, setFile] = useState<string | null>(null)
  const [line, setLine] = useState<number | null>(null)
  const [node, setNode] = useState<WorkflowNodeId | null>(null)

  const pending = (approvals.data ?? []).find((a) => a.status === 'pending')
  const executions = agents.data ?? []
  const states = nodeStates(run, executions)
  const allFindings = findings.data ?? []
  const latestCycle = Math.max(0, ...allFindings.map((f) => f.cycle))
  const latestFindings = allFindings.filter((f) => f.cycle === latestCycle)
  const databaseRun = [...(tests.data ?? [])].reverse().find((t) => t.database)
  const memory = memoryFromEvents(events)

  const openFile = (path: string, at: number | null = null) => {
    setFile(path)
    setLine(at)
    setTab('files')
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {run.projectName}
            <RunStatusBadge status={run.status} />
            {live && <span className="text-xs font-normal text-info">live</span>}
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-mono text-xs">run {run.id.slice(0, 8)}</span>
            <ModelBadge run={run} />
            <span>Started {run.startedAt ? formatRelativeTime(run.startedAt) : 'not yet'}</span>
            <span>{formatDuration(run.durationSeconds)}</span>
            <span className="font-mono text-xs">
              {(run.inputTokens + run.outputTokens).toLocaleString()} tokens · {formatUsd(run.estimatedCostUsd)}
            </span>
          </span>
        }
        actions={
          <>
            {isActive(run.status) && (
              <Button
                size="sm"
                variant="ghost"
                icon={<Ban className="size-3.5" />}
                loading={cancel.isPending}
                disabled={run.cancelRequested}
                onClick={() => cancel.mutate(run.id, { onError: (e) => toast.error(errorMessage(e)) })}
              >
                {run.cancelRequested ? 'Cancelling…' : 'Cancel'}
              </Button>
            )}
            {run.status === 'failed' && (
              <Button
                size="sm"
                icon={<RotateCw className="size-3.5" />}
                loading={resume.isPending}
                onClick={() => resume.mutate(run.id, { onError: (e) => toast.error(errorMessage(e)) })}
              >
                Resume from checkpoint
              </Button>
            )}
            <Button
              size="sm"
              icon={<Download className="size-3.5" />}
              disabled={(artifacts.data ?? []).length === 0}
              loading={download.isPending}
              onClick={() => download.mutate(run.id, { onError: (e) => toast.error(errorMessage(e)) })}
            >
              Download
            </Button>
            <ButtonLink size="sm" variant="ghost" to={`/projects/${run.projectId}`}>
              Project
            </ButtonLink>
          </>
        }
      />

      {run.error && <ErrorState error={new AppError('server', run.error)} title={`Run ${run.status}`} />}
      {pending && <ApprovalPanel runId={run.id} approval={pending} />}

      <Panel title="Workflow" icon={<Activity className="size-4" />} bodyClassName="p-0">
        <WorkflowGraph states={states} executions={executionsByNode(executions)} selected={node} onSelect={setNode} />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="min-w-0 rounded-lg border border-line bg-panel shadow-panel">
          <Tabs
            label="Run details"
            value={tab}
            onChange={setTab}
            items={[
              { id: 'files', label: 'Files', count: artifacts.data?.length, icon: <FileCode2 className="size-3.5" /> },
              { id: 'tests', label: 'Tests', count: tests.data?.length, icon: <FlaskConical className="size-3.5" /> },
              ...(databaseRun ? [{ id: 'database' as const, label: 'Database', count: databaseRun.database?.schema.length, icon: <Database className="size-3.5" /> }] : []),
              { id: 'memory', label: 'Memory', count: memory.length, icon: <BookMarked className="size-3.5" /> },
              { id: 'review', label: 'Review', count: findings.data?.length, icon: <ShieldCheck className="size-3.5" /> },
              { id: 'report', label: 'Report', icon: <ScrollText className="size-3.5" /> },
              { id: 'events', label: 'Events', count: events.length, icon: <History className="size-3.5" /> },
            ]}
          />
          <div className="p-4" role="tabpanel">
            {tab === 'files' && (
              <FilesPanel
                runId={run.id}
                artifacts={artifacts.data ?? []}
                findings={latestFindings}
                selected={file}
                line={line}
                onSelect={openFile}
              />
            )}
            {tab === 'tests' && (
              <TestResultsPanel
                results={tests.data ?? []}
                maxDebugIterations={run.maxDebugIterations}
                files={(artifacts.data ?? []).map((a) => a.path)}
                onOpenFile={openFile}
              />
            )}
            {tab === 'database' && <DatabasePanel report={databaseRun?.database} attempt={databaseRun?.attempt ?? null} />}
            {tab === 'memory' && <MemoryPanel entries={memory} />}
            {tab === 'review' && <FindingsPanel findings={findings.data ?? []} onOpenFile={openFile} />}
            {tab === 'report' && <RunReport run={run} />}
            {tab === 'events' && (
              <ol className="max-h-[32rem] space-y-1 overflow-auto font-mono text-[11px]">
                {events.map((e) => (
                  <li key={e.id} className="flex gap-3 text-fg-muted">
                    <span className="w-16 shrink-0 text-fg-subtle">{e.createdAt.toLocaleTimeString()}</span>
                    <span className="w-40 shrink-0 text-fg">{e.type}</span>
                    <span className="min-w-0 break-words" title={JSON.stringify(e.payload)}>
                      {e.node ? `${e.node} · ` : ''}
                      {describeEvent(e)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        <Panel title="Agent activity" icon={<Activity className="size-4" />} bodyClassName="p-0">
          {agents.isPending ? (
            <div className="p-4">
              <LoadingBlock label="Loading agent activity" />
            </div>
          ) : (
            <AgentTimeline executions={executions} />
          )}
          <p className="border-t border-line px-4 py-2 text-[11px] text-fg-subtle">
            Created {formatDateTime(run.createdAt)} · approval {run.requireApproval ? 'required' : 'off'}
          </p>
        </Panel>
      </div>
    </div>
  )
}

export function RunPage() {
  const { runId } = useParams()
  const query = useRun(runId)
  if (query.isError) {
    if (query.error instanceof AppError && query.error.kind === 'not_found') {
      return <EmptyState className="py-24" icon={<SearchX className="size-5" />} title="Run not found" action={<ButtonLink to="/workflows">All workflows</ButtonLink>} />
    }
    return (
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <ErrorState error={query.error} title="Could not load run" onRetry={() => query.refetch()} />
      </div>
    )
  }
  if (!query.data) {
    return (
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <LoadingBlock label="Loading run" rows={6} />
      </div>
    )
  }
  return <RunView key={query.data.id} run={query.data} />
}
