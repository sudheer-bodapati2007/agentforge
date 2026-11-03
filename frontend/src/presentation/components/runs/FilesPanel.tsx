import clsx from 'clsx'
import { Copy, FileCode2, FileText, FlaskConical, Wrench } from 'lucide-react'
import { useArtifactContent } from '@/application/use-cases/runs'
import type { Artifact, ReviewFinding } from '@/domain/run'
import { CodeView, type LineAnnotation } from '../code/CodeView'
import { Button } from '../ui/Button'
import { EmptyState, LoadingBlock } from '../ui/States'
import { useToast } from '../ui/Toast'

const ICONS = {
  source: <FileCode2 className="size-3.5" aria-hidden />,
  test: <FlaskConical className="size-3.5" aria-hidden />,
  doc: <FileText className="size-3.5" aria-hidden />,
}

/** An author whose write means the file was changed after its first version. (Review
 * corrections are recorded as "coder", like the first version, so they cannot be told apart.) */
const REVISERS = new Set(['debugger'])

/**
 * Code workspace: file tree (grouped by folder, with review findings and later revisions
 * marked) and a viewer that shows findings under the lines they refer to.
 */
export function FilesPanel({
  runId,
  artifacts,
  findings = [],
  selected,
  line = null,
  onSelect,
}: {
  runId: string
  artifacts: Artifact[]
  /** Findings of the latest review cycle. */
  findings?: ReviewFinding[]
  selected: string | null
  line?: number | null
  onSelect: (path: string, line?: number | null) => void
}) {
  const toast = useToast()
  const path = selected ?? artifacts[0]?.path ?? null
  const content = useArtifactContent(runId, path)

  if (artifacts.length === 0) {
    return <EmptyState icon={<FileCode2 className="size-5" />} title="No files yet" description="Generated files appear as the coding agents write them." />
  }

  const findingsByFile = new Map<string, ReviewFinding[]>()
  for (const f of findings) if (f.filePath) findingsByFile.set(f.filePath, [...(findingsByFile.get(f.filePath) ?? []), f])
  const annotations: LineAnnotation[] = (findingsByFile.get(path ?? '') ?? [])
    .filter((f) => f.line)
    .map((f) => ({ line: f.line!, severity: f.severity, title: f.title, source: f.source }))
  const unplaced = (findingsByFile.get(path ?? '') ?? []).filter((f) => !f.line)

  const groups = new Map<string, Artifact[]>()
  for (const artifact of artifacts) {
    const folder = artifact.path.includes('/') ? artifact.path.slice(0, artifact.path.lastIndexOf('/')) : '.'
    groups.set(folder, [...(groups.get(folder) ?? []), artifact])
  }

  return (
    <div className="grid min-h-[24rem] gap-3 md:grid-cols-[15rem_minmax(0,1fr)]">
      <nav aria-label="Generated files" className="max-h-[32rem] overflow-y-auto rounded-md border border-line bg-canvas p-1.5">
        {[...groups.entries()].sort().map(([folder, files]) => (
          <div key={folder} className="mb-1">
            {folder !== '.' && <p className="px-2 pt-1.5 pb-0.5 font-mono text-[11px] text-fg-subtle">{folder}/</p>}
            {files.map((a) => {
              const count = findingsByFile.get(a.path)?.length ?? 0
              const revised = a.createdBy !== null && REVISERS.has(a.createdBy)
              return (
                <button
                  key={a.path}
                  type="button"
                  onClick={() => onSelect(a.path)}
                  aria-current={a.path === path || undefined}
                  aria-label={`${a.path}${count ? `, ${count} review finding(s)` : ''}${revised ? `, revised by the ${a.createdBy}` : ''}`}
                  className={clsx(
                    'flex w-full items-center gap-1.5 rounded px-2 py-1 text-left font-mono text-xs',
                    a.path === path ? 'bg-accent-soft text-fg' : 'text-fg-muted hover:bg-hover hover:text-fg',
                  )}
                >
                  {ICONS[a.kind as keyof typeof ICONS] ?? ICONS.source}
                  <span className="truncate">{a.path.split('/').pop()}</span>
                  <span className="ml-auto flex items-center gap-1">
                    {revised && <Wrench className="size-3 text-info" aria-hidden />}
                    {count > 0 && (
                      <span className="rounded-full bg-warning-soft px-1.5 text-[10px] text-warning" aria-hidden>
                        {count}
                      </span>
                    )}
                    <span className="text-[10px] text-fg-subtle">{a.createdBy}</span>
                  </span>
                </button>
              )
            })}
          </div>
        ))}
      </nav>
      <div className="flex min-w-0 flex-col rounded-md border border-line bg-canvas">
        <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-1.5">
          <span className="truncate font-mono text-xs text-fg">
            {path}
            {line ? `:${line}` : ''}
          </span>
          <Button
            size="sm"
            variant="ghost"
            icon={<Copy className="size-3.5" />}
            disabled={!content.data}
            onClick={() => {
              void navigator.clipboard?.writeText(content.data ?? '').then(() => toast.success('Copied to clipboard'))
            }}
          >
            Copy
          </Button>
        </div>
        {unplaced.length > 0 && (
          <ul className="border-b border-line px-3 py-1.5 text-[11px] text-fg-muted">
            {unplaced.map((f) => (
              <li key={f.id}>
                <span className="mr-1.5 font-medium uppercase">{f.severity}</span>
                {f.title} <span className="text-fg-subtle">(whole file)</span>
              </li>
            ))}
          </ul>
        )}
        <div className="max-h-[32rem] min-h-0 flex-1 overflow-auto">
          {content.isPending ? (
            <div className="p-3">
              <LoadingBlock label="Loading file" rows={6} />
            </div>
          ) : content.isError ? (
            <p className="p-3 text-xs text-danger">{content.error.message}</p>
          ) : (
            <CodeView path={path ?? ''} code={content.data ?? ''} highlightLine={line} annotations={annotations} />
          )}
        </div>
      </div>
    </div>
  )
}
