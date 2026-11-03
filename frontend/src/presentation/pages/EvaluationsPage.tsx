import clsx from 'clsx'
import { CircleCheck, FlaskConical, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useBenchmarks } from '@/application/use-cases/evaluations'
import {
  SYSTEM_LABELS,
  SYSTEMS,
  passFraction,
  taskRows,
  type Benchmark,
  type EvaluationResult,
  type SystemKind,
  type SystemSummary,
  type TestTally,
} from '@/domain/evaluation'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { NO_DATA, formatDateTime, formatDuration, formatPercent, formatUsd } from '../lib/format'

/** Series colour follows the system (fixed order), never its rank. */
const SERIES: Record<SystemKind, string> = { multi_agent: 'bg-series-1', single_agent: 'bg-series-2' }

const COMMAND = '.venv/Scripts/python ../evals/scripts/run_benchmark.py'

function Swatch({ system }: { system: SystemKind }) {
  return <span aria-hidden className={clsx('inline-block size-2.5 shrink-0 rounded-sm', SERIES[system])} />
}

function tally(t: TestTally): string {
  return t.executed ? `${t.passed}/${t.total}` : NO_DATA
}

const number = (value: number | null, digits = 1) => (value === null ? NO_DATA : value.toFixed(digits))

const METRICS: { label: string; hint?: string; value: (s: SystemSummary) => string }[] = [
  { label: 'Tasks solved', hint: 'every hidden reference test passed', value: (s) => `${s.solved}/${s.tasks} (${formatPercent(s.solveRate)})` },
  { label: 'Reference tests passed', hint: 'mean per task', value: (s) => formatPercent(s.referencePassRate) },
  { label: 'Own test suite green', hint: 'its own tests, where they ran', value: (s) => formatPercent(s.ownSuiteSuccessRate) },
  { label: 'Debug iterations', hint: 'mean per task', value: (s) => number(s.meanDebugIterations) },
  { label: 'Latency', hint: 'median per task', value: (s) => formatDuration(s.medianLatencySeconds) },
  { label: 'Tokens', value: (s) => (s.totalInputTokens + s.totalOutputTokens).toLocaleString('en-US') },
  { label: 'Est. cost', value: (s) => formatUsd(s.totalCostUsd) },
  { label: 'Blocking findings', hint: 'same analysers for both', value: (s) => String(s.blockingFindings) },
  { label: 'Crashed attempts', value: (s) => String(s.errors) },
]

function Comparison({ summaries }: { summaries: SystemSummary[] }) {
  const bySystem = new Map(summaries.map((s) => [s.system, s]))
  const systems = SYSTEMS.filter((s) => bySystem.has(s))
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-[13px]">
        <caption className="sr-only">Benchmark summary per system</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs text-fg-muted">
            <th scope="col" className="py-2 pr-3 font-medium">Metric</th>
            {systems.map((system) => (
              <th key={system} scope="col" className="px-3 py-2 font-medium">
                <span className="flex items-center gap-2">
                  <Swatch system={system} />
                  {SYSTEM_LABELS[system]}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {METRICS.map((metric) => (
            <tr key={metric.label}>
              <th scope="row" className="py-2 pr-3 text-left font-normal text-fg-muted">
                {metric.label}
                {metric.hint && <span className="block text-[11px] text-fg-subtle">{metric.hint}</span>}
              </th>
              {systems.map((system) => (
                <td key={system} className="px-3 py-2 font-mono text-fg tabular-nums">
                  {metric.value(bySystem.get(system)!)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Bar({ result, active, onActivate }: { result: EvaluationResult; active: boolean; onActivate: (on: boolean) => void }) {
  const fraction = passFraction(result.referenceTests)
  const label = `${SYSTEM_LABELS[result.system]}: ${
    fraction === null ? 'reference tests did not run' : `${tally(result.referenceTests)} reference tests passed`
  }${result.solved ? ', solved' : ''}`
  return (
    <div
      className="relative flex h-6 items-center"
      tabIndex={0}
      role="img"
      aria-label={label}
      onMouseEnter={() => onActivate(true)}
      onMouseLeave={() => onActivate(false)}
      onFocus={() => onActivate(true)}
      onBlur={() => onActivate(false)}
    >
      {fraction === null ? (
        <span className="text-[11px] text-fg-subtle">not run</span>
      ) : (
        <span
          className={clsx('h-2.5 rounded-r-[4px]', SERIES[result.system], active && 'brightness-125')}
          // A zero result still shows a sliver so "ran, nothing passed" differs from "not run".
          style={{ width: `max(${fraction * 100}%, 2px)` }}
        />
      )}
      {active && (
        <div
          role="tooltip"
          className="pointer-events-none absolute -top-9 left-0 z-10 rounded-md border border-line-strong bg-elevated px-2 py-1 text-xs whitespace-nowrap text-fg shadow-panel"
        >
          {label}
          {result.error && <span className="text-fg-muted"> · crashed</span>}
        </div>
      )}
    </div>
  )
}

function TaskChart({ results }: { results: EvaluationResult[] }) {
  const [active, setActive] = useState<string | null>(null)
  const present = SYSTEMS.filter((s) => results.some((r) => r.system === s))
  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted" aria-label="Legend">
        {present.map((system) => (
          <li key={system} className="flex items-center gap-1.5">
            <Swatch system={system} />
            {SYSTEM_LABELS[system]}
          </li>
        ))}
      </ul>
      <div className="space-y-3">
        {taskRows(results).map((row) => (
          <div key={row.taskId} className="grid grid-cols-1 gap-1 sm:grid-cols-[180px_1fr] sm:gap-3">
            <div className="min-w-0 text-[13px]">
              <p className="truncate text-fg" title={row.taskTitle}>{row.taskTitle}</p>
              <p className="text-[11px] text-fg-subtle">{row.category}</p>
            </div>
            {/* Hairline baseline at 0; bars grow to the right, scaled 0–100% of reference tests. */}
            <div className="space-y-0.5 border-l border-line-strong pl-px">
              {present.map((system) => {
                const result = row.bySystem[system]
                const key = `${row.taskId}:${system}`
                return result ? (
                  <Bar key={key} result={result} active={active === key} onActivate={(on) => setActive(on ? key : null)} />
                ) : (
                  <div key={key} className="h-6 text-[11px] leading-6 text-fg-subtle">not run</div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-fg-subtle sm:pl-[192px]">Share of hidden reference tests passed (0–100%)</p>
    </div>
  )
}

function ResultsTable({ results }: { results: EvaluationResult[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-[13px]">
        <caption className="sr-only">Every task and system result</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs text-fg-muted">
            {['Task', 'System', 'Reference tests', 'Own tests', 'Debug', 'Latency', 'Tokens', 'Findings', 'Note'].map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium first:pl-4">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {results.map((r) => (
            <tr key={`${r.taskId}:${r.system}`} className="align-top">
              <td className="py-2 pr-3 pl-4 text-fg">{r.taskTitle}</td>
              <td className="px-3 py-2 text-fg-muted">
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <Swatch system={r.system} />
                  {SYSTEM_LABELS[r.system]}
                </span>
              </td>
              <td className="px-3 py-2 font-mono whitespace-nowrap text-fg tabular-nums">
                {tally(r.referenceTests)}
                {r.solved && (
                  <span className="ml-2 inline-flex items-center gap-1 font-sans text-xs text-success">
                    <CircleCheck className="size-3.5" aria-hidden />
                    solved
                  </span>
                )}
              </td>
              <td className="px-3 py-2 font-mono text-fg-muted tabular-nums">{tally(r.ownTests)}</td>
              <td className="px-3 py-2 font-mono text-fg-muted tabular-nums">{r.debugIterations}</td>
              <td className="px-3 py-2 font-mono text-fg-muted tabular-nums">{formatDuration(r.latencySeconds)}</td>
              <td className="px-3 py-2 font-mono text-fg-muted tabular-nums">{(r.inputTokens + r.outputTokens).toLocaleString('en-US')}</td>
              <td className="px-3 py-2 font-mono text-fg-muted tabular-nums">
                {r.findingsTotal}
                {r.blockingFindings > 0 && <span className="text-danger"> ({r.blockingFindings} blocking)</span>}
              </td>
              <td className="max-w-[260px] px-3 py-2 text-xs break-words text-fg-subtle">{r.error ? `Crashed: ${r.error}` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BenchmarkView({ benchmark }: { benchmark: Benchmark }) {
  return (
    <div className="space-y-4">
      {benchmark.demoModel && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning-soft px-4 py-2.5 text-[13px] text-fg">
          <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden />
          Produced with the scripted demo model, which is not AI. These numbers measure nothing.
        </div>
      )}
      <p className="text-xs text-fg-muted">
        Benchmark <span className="font-mono text-fg">{benchmark.id}</span> · {formatDateTime(benchmark.createdAt)} · model{' '}
        <span className="font-mono text-fg">{benchmark.modelNames.join(', ') || NO_DATA}</span>
      </p>
      <div className="grid gap-4 xl:grid-cols-5">
        <Panel title="Summary" className="xl:col-span-2">
          <Comparison summaries={benchmark.summaries} />
        </Panel>
        <Panel title="Reference tests passed, per task" className="xl:col-span-3">
          <TaskChart results={benchmark.results} />
        </Panel>
      </div>
      <Panel title="All results" bodyClassName="p-0">
        <ResultsTable results={benchmark.results} />
      </Panel>
    </div>
  )
}

export function EvaluationsPage() {
  const query = useBenchmarks()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const benchmarks = query.data ?? []
  const benchmark = benchmarks.find((b) => b.id === selectedId) ?? benchmarks[0]

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Evaluations"
        description="The multi-agent workflow vs a single-agent baseline on fixed tasks. Both are graded by hidden reference tests run in the Docker sandbox."
        actions={
          benchmarks.length > 1 && (
            <label className="flex items-center gap-2 text-xs text-fg-muted">
              Benchmark
              <select
                className="h-8 rounded-md border border-line-strong bg-elevated px-2 font-mono text-xs text-fg"
                value={benchmark?.id}
                onChange={(e) => setSelectedId(e.target.value)}
              >
                {benchmarks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.id}
                  </option>
                ))}
              </select>
            </label>
          )
        }
      />
      {query.isError ? (
        <ErrorState error={query.error} title="Could not load benchmark results" onRetry={() => query.refetch()} />
      ) : query.isPending ? (
        <Panel>
          <LoadingBlock label="Loading benchmark results" />
        </Panel>
      ) : !benchmark ? (
        <Panel>
          <EmptyState
            icon={<FlaskConical className="size-5" />}
            title="No benchmark has been run yet"
            description={
              <>
                Results appear here after running the benchmark from <span className="font-mono">backend/</span>:
                <code className="mt-2 block rounded bg-elevated px-2 py-1 font-mono text-xs text-fg">{COMMAND}</code>
              </>
            }
          />
        </Panel>
      ) : (
        <BenchmarkView benchmark={benchmark} />
      )}
    </div>
  )
}
