import clsx from 'clsx'
import { ShieldCheck, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'
import { SEVERITIES, type ReviewFinding, type Severity } from '@/domain/run'
import { SEVERITY_TONE } from '../../lib/severity'
import { EmptyState } from '../ui/States'
import { Badge } from '../ui/StatusBadge'

/** Review findings with severity/category filters and provenance (tool vs LLM). */
export function FindingsPanel({
  findings,
  onOpenFile,
}: {
  findings: ReviewFinding[]
  onOpenFile?: (path: string, line?: number | null) => void
}) {
  const latestCycle = Math.max(0, ...findings.map((f) => f.cycle))
  const [severity, setSeverity] = useState<Severity | 'all'>('all')
  const [category, setCategory] = useState('all')
  const latest = findings.filter((f) => f.cycle === latestCycle)
  const categories = useMemo(() => [...new Set(latest.map((f) => f.category))].sort(), [latest])
  const visible = latest.filter((f) => (severity === 'all' || f.severity === severity) && (category === 'all' || f.category === category))

  if (findings.length === 0) {
    return <EmptyState icon={<ShieldCheck className="size-5" />} title="No findings" description="Review runs after the tests pass." />
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <label className="sr-only" htmlFor="severity-filter">Severity</label>
        <select id="severity-filter" value={severity} onChange={(e) => setSeverity(e.target.value as Severity | 'all')} className="h-7 rounded-md border border-line-strong bg-canvas px-2 text-fg">
          <option value="all">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <label className="sr-only" htmlFor="category-filter">Category</label>
        <select id="category-filter" value={category} onChange={(e) => setCategory(e.target.value)} className="h-7 rounded-md border border-line-strong bg-canvas px-2 text-fg">
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <span className="ml-auto text-fg-subtle">
          Review cycle {latestCycle} · {visible.length} of {latest.length}
        </span>
      </div>
      <ul className="space-y-2">
        {visible.map((f) => (
          <li key={f.id} className="rounded-md border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={SEVERITY_TONE[f.severity]}>{f.severity}</Badge>
              <span className="text-[13px] font-medium text-fg">{f.title}</span>
              <span
                className={clsx(
                  'ml-auto inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium',
                  f.source === 'tool' ? 'border-success/30 text-success' : 'border-line-strong text-fg-subtle',
                )}
                title={f.source === 'tool' ? 'Verified by a deterministic tool' : 'Identified by the LLM reviewer (may be wrong)'}
              >
                {f.source === 'tool' ? <Wrench className="size-3" aria-hidden /> : null}
                {f.source === 'tool' ? `tool: ${f.toolName}` : 'LLM'}
              </span>
            </div>
            <p className="mt-1.5 text-[13px] text-fg-muted">{f.description}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs">
              <span className="text-fg-subtle">{f.category}</span>
              {f.filePath && (
                <button type="button" className="font-mono text-accent hover:underline" onClick={() => onOpenFile?.(f.filePath!, f.line)}>
                  {f.filePath}
                  {f.line ? `:${f.line}` : ''}
                </button>
              )}
            </div>
            {f.suggestion && <p className="mt-1.5 text-xs text-fg"><span className="text-fg-subtle">Suggestion: </span>{f.suggestion}</p>}
          </li>
        ))}
      </ul>
    </div>
  )
}
