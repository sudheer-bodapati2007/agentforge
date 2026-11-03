import clsx from 'clsx'
import { BookMarked, FlaskConical, Lightbulb, Ruler, Scale, StickyNote } from 'lucide-react'
import type { ReactNode } from 'react'
import { isMeasured, type MemoryEntry } from '@/domain/memory'
import { EmptyState } from '../ui/States'
import { Badge } from '../ui/StatusBadge'

const KIND: Record<string, { label: string; icon: ReactNode }> = {
  assumption: { label: 'Assumption', icon: <BookMarked className="size-3.5" /> },
  decision: { label: 'Decision', icon: <Scale className="size-3.5" /> },
  note: { label: 'Note', icon: <StickyNote className="size-3.5" /> },
  hypothesis: { label: 'Hypothesis', icon: <Lightbulb className="size-3.5" /> },
  fact: { label: 'Measured fact', icon: <Ruler className="size-3.5" /> },
  verdict: { label: 'Verdict', icon: <FlaskConical className="size-3.5" /> },
}

const OUTCOME_TONE = { confirmed: 'success', partly: 'warning', refuted: 'danger', unknown: 'neutral' } as const

/**
 * What every agent knew during the run. Facts and verdicts are measured by AgentForge from
 * real test runs; everything else is an agent's own note and may be wrong.
 */
export function MemoryPanel({ entries }: { entries: MemoryEntry[] }) {
  if (entries.length === 0) {
    return <EmptyState icon={<BookMarked className="size-5" />} title="Nothing in memory yet" description="Agents add assumptions, decisions and hypotheses; AgentForge adds facts and verdicts from real test runs." />
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-subtle">
        Shared by every agent in this run. <span className="text-fg-muted">Measured</span> entries come from the real test runner;
        the rest are the agents’ own notes.
      </p>
      <ol aria-label="Run memory" className="space-y-1.5">
        {entries.map((m) => {
          const measured = isMeasured(m)
          const kind = KIND[m.kind] ?? KIND.note
          return (
            <li
              key={m.id}
              className={clsx('rounded-md border px-3 py-2 text-[13px]', measured ? 'border-info/30 bg-info-soft' : 'border-line bg-canvas')}
            >
              <div className="mb-0.5 flex flex-wrap items-center gap-2 text-[11px] text-fg-muted">
                <span className="flex items-center gap-1 font-medium text-fg">
                  <span aria-hidden className="text-fg-muted">{kind.icon}</span>
                  {kind.label}
                </span>
                {m.outcome && <Badge tone={OUTCOME_TONE[m.outcome] ?? 'neutral'}>{m.outcome}</Badge>}
                <span>
                  {m.author} · {m.step.replace(/_/g, ' ')}
                </span>
                {measured && <span className="text-info">measured</span>}
                {m.files.length > 0 && <span className="font-mono text-fg-subtle">{m.files.join(', ')}</span>}
              </div>
              <p className="text-fg">{m.text}</p>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
