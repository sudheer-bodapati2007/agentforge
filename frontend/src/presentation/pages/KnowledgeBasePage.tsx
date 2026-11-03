import { BookOpen, ChevronDown, ChevronRight, FileText, RefreshCw, Search, ShieldAlert, Trash2, Upload } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { errorMessage } from '@/application/errors'
import {
  useDeleteDocument,
  useDocumentChunks,
  useDocuments,
  useKnowledgeSearch,
  useReindexDocument,
  useUploadDocument,
} from '@/application/use-cases/knowledge'
import { useProjects } from '@/application/use-cases/projects'
import { ALLOWED_EXTENSIONS, uploadProblem, type KnowledgeDocument, type SearchResult } from '@/domain/knowledge'
import { PageHeader } from '../components/PageHeader'
import { Button, ButtonLink } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { Badge } from '../components/ui/StatusBadge'
import { useToast } from '../components/ui/Toast'
import { NO_DATA, formatBytes, formatRelativeTime } from '../lib/format'

function ChunkList({ projectId, documentId }: { projectId: string; documentId: string }) {
  const query = useDocumentChunks(projectId, documentId)
  if (query.isError) return <ErrorState error={query.error} title="Could not load chunks" onRetry={() => query.refetch()} />
  if (!query.data) return <LoadingBlock label="Loading chunks" rows={2} />
  return (
    <ol className="space-y-2" aria-label="Chunks">
      {query.data.map((chunk) => (
        <li key={chunk.id} className="rounded-md border border-line bg-canvas p-2.5">
          <p className="mb-1 text-[11px] text-fg-subtle">
            #{chunk.ordinal + 1} · lines {chunk.startLine}–{chunk.endLine}
            {chunk.heading && ` · ${chunk.heading}`}
          </p>
          <pre className="max-h-40 overflow-auto font-mono text-xs whitespace-pre-wrap text-fg-muted">{chunk.text}</pre>
        </li>
      ))}
    </ol>
  )
}

function DocumentRow({ projectId, doc }: { projectId: string; doc: KnowledgeDocument }) {
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const remove = useDeleteDocument(projectId)
  const reindex = useReindexDocument(projectId)
  const toast = useToast()

  return (
    <li className="px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={`${open ? 'Hide' : 'Show'} chunks of ${doc.filename}`}
          className="flex min-w-0 flex-1 items-center gap-2 text-left text-[13px] text-fg hover:text-accent"
        >
          {open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
          <FileText className="size-4 shrink-0 text-fg-muted" aria-hidden />
          <span className="truncate">{doc.filename}</span>
        </button>
        <span className="text-xs text-fg-subtle">{doc.kind}</span>
        <span className="font-mono text-xs text-fg-muted">{formatBytes(doc.sizeBytes)}</span>
        <span className="font-mono text-xs text-fg-muted">{doc.chunkCount} chunks</span>
        {doc.redactedLines > 0 && (
          <span title="Lines that looked like credentials were replaced before indexing">
            <Badge tone="warning" className="gap-1">
              <ShieldAlert className="size-3" aria-hidden /> {doc.redactedLines} redacted
            </Badge>
          </span>
        )}
        {doc.stale ? (
          <Button
            size="sm"
            icon={<RefreshCw className="size-3.5" />}
            disabled={reindex.isPending}
            onClick={() =>
              reindex.mutate(doc.id, {
                onSuccess: () => toast.success(`${doc.filename} re-indexed`),
                onError: (error) => toast.error(errorMessage(error)),
              })
            }
            title={`Indexed with ${doc.embedder}; not searchable until re-indexed with the current embedder`}
          >
            Re-index
          </Button>
        ) : (
          <span className="hidden text-xs text-fg-subtle sm:inline">{formatRelativeTime(doc.updatedAt)}</span>
        )}
        <Button size="sm" variant="ghost" icon={<Trash2 className="size-3.5" />} aria-label={`Delete ${doc.filename}`} onClick={() => setConfirming(true)} />
      </div>
      {open && (
        <div className="mt-2 pl-6">
          <ChunkList projectId={projectId} documentId={doc.id} />
        </div>
      )}
      <ConfirmDialog
        open={confirming}
        title={`Delete ${doc.filename}?`}
        description="The document and its chunks are removed. Runs started afterwards no longer see it."
        confirmLabel="Delete"
        tone="danger"
        busy={remove.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          remove.mutate(doc.id, {
            onSuccess: () => {
              setConfirming(false)
              toast.success(`${doc.filename} deleted`)
            },
            onError: (error) => toast.error(errorMessage(error)),
          })
        }
      />
    </li>
  )
}

function UploadButton({ projectId }: { projectId: string }) {
  const input = useRef<HTMLInputElement>(null)
  const upload = useUploadDocument(projectId)
  const toast = useToast()
  const [busy, setBusy] = useState(false)

  async function onFiles(files: FileList | null) {
    if (!files?.length) return
    setBusy(true)
    for (const file of Array.from(files)) {
      const problem = uploadProblem(file.name, file.size)
      if (problem) {
        toast.error(`${file.name}: ${problem}`)
        continue
      }
      try {
        const outcome = await upload.mutateAsync({ name: file.name, content: await file.text() })
        const verb = outcome.unchanged ? 'is unchanged' : outcome.created ? 'added' : 'replaced'
        const redacted = outcome.document.redactedLines ? ` (${outcome.document.redactedLines} line(s) redacted as possible secrets)` : ''
        toast.success(`${outcome.document.filename} ${verb}: ${outcome.document.chunkCount} chunks${redacted}`)
      } catch (error) {
        toast.error(`${file.name}: ${errorMessage(error)}`)
      }
    }
    setBusy(false)
    if (input.current) input.current.value = ''
  }

  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept={ALLOWED_EXTENSIONS.join(',')}
        className="sr-only"
        aria-label="Choose documents to upload"
        onChange={(e) => void onFiles(e.target.files)}
      />
      <Button variant="primary" icon={<Upload className="size-4" />} disabled={busy} onClick={() => input.current?.click()}>
        {busy ? 'Uploading…' : 'Upload documents'}
      </Button>
    </>
  )
}

const score = (value: number | null) => (value === null ? NO_DATA : value.toFixed(2))

function SearchResults({ result }: { result: SearchResult }) {
  if (result.results.length === 0) {
    return (
      <p className="py-3 text-[13px] text-fg-muted">
        No relevant documents. Nothing in this knowledge base is about this query, so the agents would get no extra context.
      </p>
    )
  }
  return (
    <ol className="space-y-2" aria-label="Retrieved chunks">
      {result.results.map((hit, index) => (
        <li key={`${hit.documentId}:${hit.startLine}`} className="rounded-md border border-line bg-canvas p-3">
          <div className="mb-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs">
            <span className="font-medium text-fg">
              {index + 1}. {hit.source}
            </span>
            <span className="text-fg-subtle">{hit.location}</span>
            <span className="ml-auto font-mono text-fg-muted" title="dense (cosine) · sparse (BM25) · rerank · final">
              dense {score(hit.denseScore)} · bm25 {score(hit.sparseScore)} · rerank {score(hit.rerankScore)} · final{' '}
              <span className="text-fg">{hit.score.toFixed(2)}</span>
            </span>
          </div>
          <pre className="max-h-32 overflow-auto font-mono text-xs whitespace-pre-wrap text-fg-muted">{hit.text}</pre>
        </li>
      ))}
    </ol>
  )
}

function RetrievalTester({ projectId }: { projectId: string }) {
  const [draft, setDraft] = useState('')
  const [submitted, setSubmitted] = useState('')
  const query = useKnowledgeSearch(projectId, submitted)

  function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(draft.trim())
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex gap-2" role="search">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={2000}
          placeholder="Ask what an agent would ask, e.g. what is the maximum page size?"
          aria-label="Search query"
          className="h-9 min-w-0 flex-1 rounded-md border border-line-strong bg-panel px-3 text-sm text-fg placeholder:text-fg-subtle"
        />
        <Button type="submit" icon={<Search className="size-4" />} disabled={!draft.trim()}>
          Search
        </Button>
      </form>
      {query.data && (
        <p className="text-[11px] text-fg-subtle">
          {query.data.mode} retrieval · embedder <span className="font-mono">{query.data.embedder}</span> · reranker{' '}
          <span className="font-mono">{query.data.reranker ?? 'none'}</span>
        </p>
      )}
      {query.isError ? (
        <ErrorState error={query.error} title="Search failed" onRetry={() => query.refetch()} />
      ) : query.isFetching ? (
        <LoadingBlock label="Searching" rows={2} />
      ) : query.data ? (
        <SearchResults result={query.data} />
      ) : (
        <p className="text-[13px] text-fg-subtle">
          Runs the same pipeline the agents use (dense + BM25, fused, reranked, relevance-gated) and shows every score.
        </p>
      )}
    </div>
  )
}

function ProjectKnowledge({ projectId }: { projectId: string }) {
  const documents = useDocuments(projectId)
  const items = documents.data?.items ?? []
  const stale = items.filter((d) => d.stale).length

  return (
    <div className="grid gap-4 xl:grid-cols-5">
      <Panel
        title="Documents"
        icon={<BookOpen className="size-4" />}
        className="xl:col-span-3"
        bodyClassName="p-0"
        actions={<UploadButton projectId={projectId} />}
      >
        {documents.isError ? (
          <div className="p-4">
            <ErrorState error={documents.error} title="Could not load documents" onRetry={() => documents.refetch()} />
          </div>
        ) : !documents.data ? (
          <div className="p-4">
            <LoadingBlock label="Loading documents" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<FileText className="size-5" />}
            title="No documents yet"
            description={`Upload coding standards, API guidelines or reference code (${ALLOWED_EXTENSIONS.join(', ')}, up to 400 KB). The planner, architect and coder retrieve relevant parts during every run.`}
          />
        ) : (
          <>
            {stale > 0 && (
              <p role="status" className="border-b border-line bg-warning-soft px-4 py-2 text-xs text-fg">
                {stale} document(s) were indexed with a different embedder than the current one (
                <span className="font-mono">{documents.data.embedder}</span>) and are not searchable until re-indexed.
              </p>
            )}
            <ul className="divide-y divide-line">
              {items.map((doc) => (
                <DocumentRow key={doc.id} projectId={projectId} doc={doc} />
              ))}
            </ul>
          </>
        )}
      </Panel>
      <Panel title="Test retrieval" icon={<Search className="size-4" />} className="xl:col-span-2">
        <RetrievalTester projectId={projectId} />
      </Panel>
    </div>
  )
}

export function KnowledgeBasePage() {
  const projects = useProjects('')
  const [params, setParams] = useSearchParams()
  const list = projects.data?.items ?? []
  const selected = list.find((p) => p.id === params.get('project')) ?? list[0]

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Knowledge Base"
        description="Project documents the agents retrieve from. Text is chunked, secrets are redacted, and retrieved passages reach the agents as untrusted reference material."
        actions={
          list.length > 0 && (
            <label className="flex items-center gap-2 text-xs text-fg-muted">
              Project
              <select
                className="h-9 max-w-56 rounded-md border border-line-strong bg-panel px-2 text-sm text-fg"
                value={selected?.id}
                onChange={(e) => setParams({ project: e.target.value })}
              >
                {list.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          )
        }
      />
      {projects.isError ? (
        <ErrorState error={projects.error} title="Could not load projects" onRetry={() => projects.refetch()} />
      ) : !projects.data ? (
        <Panel>
          <LoadingBlock label="Loading projects" />
        </Panel>
      ) : !selected ? (
        <Panel>
          <EmptyState
            icon={<BookOpen className="size-5" />}
            title="Create a project first"
            description="Documents belong to a project; its runs retrieve from them."
            action={<ButtonLink to="/projects/new">New project</ButtonLink>}
          />
        </Panel>
      ) : (
        <ProjectKnowledge key={selected.id} projectId={selected.id} />
      )}
    </div>
  )
}
