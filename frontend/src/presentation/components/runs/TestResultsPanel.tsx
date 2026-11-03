import clsx from 'clsx'
import { FlaskConical } from 'lucide-react'
import { useState } from 'react'
import { migrated, type TestResult } from '@/domain/run'
import { formatDuration } from '../../lib/format'
import { EmptyState } from '../ui/States'
import { Badge } from '../ui/StatusBadge'

function Count({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-md border border-line bg-canvas px-3 py-2">
      <p className="text-[11px] tracking-wide text-fg-subtle uppercase">{label}</p>
      <p className={clsx('font-mono text-lg tabular-nums', tone)}>{value}</p>
    </div>
  )
}

const SEGMENTS = [
  { key: 'passed', label: 'passed', className: 'bg-success' },
  { key: 'failed', label: 'failed', className: 'bg-danger' },
  { key: 'errors', label: 'errors', className: 'bg-warning' },
] as const

/** One stacked bar per test run, so the debugging loop's progress (or lack of it) is visible. */
function AttemptChart({ results, selected, onSelect }: { results: TestResult[]; selected: number; onSelect: (attempt: number) => void }) {
  const scale = Math.max(1, ...results.map((r) => r.passed + r.failed + r.errors))
  return (
    <figure className="space-y-1.5">
      <figcaption className="flex flex-wrap items-center gap-3 text-[11px] text-fg-muted">
        Tests per run
        {SEGMENTS.map((s) => (
          <span key={s.key} className="flex items-center gap-1">
            <span className={clsx('size-2 rounded-sm', s.className)} aria-hidden /> {s.label}
          </span>
        ))}
      </figcaption>
      {results.map((r) => {
        const label = r.executed ? `${r.passed}/${r.total} passed, ${r.failed} failed, ${r.errors} errors` : 'not executed'
        return (
          <button
            key={r.attempt}
            type="button"
            onClick={() => onSelect(r.attempt)}
            aria-pressed={r.attempt === selected}
            aria-label={`Run ${r.attempt}: ${label}`}
            className={clsx('grid w-full grid-cols-[3.5rem_1fr_9rem] items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-hover', r.attempt === selected && 'bg-accent-soft')}
          >
            <span className="font-mono text-xs text-fg-muted">Run {r.attempt}</span>
            <span className="flex h-2.5 gap-px overflow-hidden rounded-r-[4px]">
              {r.executed &&
                SEGMENTS.map((s) =>
                  r[s.key] > 0 ? <span key={s.key} className={s.className} style={{ width: `${(r[s.key] / scale) * 100}%` }} /> : null,
                )}
            </span>
            <span className="text-right font-mono text-[11px] text-fg-subtle">{r.executed ? `${r.passed}/${r.total}` : 'not run'}</span>
          </button>
        )
      })}
    </figure>
  )
}

/** Results reported by the real test runner in the sandbox. Never model output. */
export function TestResultsPanel({
  results,
  maxDebugIterations,
  files = [],
  onOpenFile,
}: {
  results: TestResult[]
  maxDebugIterations: number
  /** Paths of the generated files, so failures can link to the ones that exist. */
  files?: string[]
  onOpenFile?: (path: string, line?: number | null) => void
}) {
  const [selected, setSelected] = useState<number | null>(null)
  if (results.length === 0) {
    return <EmptyState icon={<FlaskConical className="size-5" />} title="No test runs yet" description="Tests run in an isolated sandbox once code and tests are generated." />
  }
  const current = results.find((r) => r.attempt === selected) ?? results[results.length - 1]
  const verified =
    current.executed &&
    current.exitCode === 0 &&
    current.total > 0 &&
    current.failed === 0 &&
    current.errors === 0 &&
    (!current.database || migrated(current.database))

  const known = new Set(files)

  return (
    <div className="space-y-4">
      <AttemptChart results={results} selected={current.attempt} onSelect={setSelected} />
      <p className="text-right text-xs text-fg-subtle">
        Retry budget: {Math.max(0, results.length - 1)}/{maxDebugIterations} debugging iterations
      </p>

      {!current.executed ? (
        <p className="rounded-md border border-warning/25 bg-warning-soft p-3 text-[13px] text-fg">
          <span className="font-medium text-warning">Tests were generated but not executed.</span>{' '}
          {current.unavailableReason}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <Count label="Total" value={current.total} tone="text-fg" />
            <Count label="Passed" value={current.passed} tone="text-success" />
            <Count label="Failed" value={current.failed} tone={current.failed ? 'text-danger' : 'text-fg-muted'} />
            <Count label="Errors" value={current.errors} tone={current.errors ? 'text-danger' : 'text-fg-muted'} />
            <Count label="Skipped" value={current.skipped} tone="text-warning" />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
            <Badge tone={verified ? 'success' : 'danger'}>{verified ? 'Verified by test runner' : 'Failing'}</Badge>
            <code className="font-mono text-fg-subtle">{current.command}</code>
            <span>exit {current.exitCode ?? 'timeout'}</span>
            <span>{formatDuration(current.durationMs === null ? null : current.durationMs / 1000)}</span>
          </div>
        </>
      )}

      {current.failures.length > 0 && (
        <ul className="space-y-2">
          {current.failures.map((failure) => (
            <li key={failure.name} className="rounded-md border border-danger/25 bg-danger-soft p-3">
              <p className="font-mono text-xs text-danger">
                {failure.name}
                {failure.file_path &&
                  (known.has(failure.file_path) && onOpenFile ? (
                    <>
                      {' · '}
                      <button type="button" className="text-accent hover:underline" onClick={() => onOpenFile(failure.file_path!, failure.line)}>
                        {failure.file_path}
                        {failure.line ? `:${failure.line}` : ''}
                      </button>
                    </>
                  ) : (
                    <span className="text-fg-subtle">
                      {' · '}
                      {failure.file_path}
                      {failure.line ? `:${failure.line}` : ''}
                    </span>
                  ))}
              </p>
              <pre className="mt-1.5 max-h-48 overflow-auto font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-fg-muted">
                {failure.message}
              </pre>
            </li>
          ))}
        </ul>
      )}

      {current.outputExcerpt && (
        <details className="rounded-md border border-line bg-canvas">
          <summary className="cursor-pointer px-3 py-2 text-xs text-fg-muted">Runner output</summary>
          <pre className="max-h-72 overflow-auto border-t border-line p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-fg-muted">
            {current.outputExcerpt}
          </pre>
        </details>
      )}
    </div>
  )
}
