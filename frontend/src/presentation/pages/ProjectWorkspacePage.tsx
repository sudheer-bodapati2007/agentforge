import { FileText, History, Pencil, SearchX, Settings2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AppError, errorMessage } from '@/application/errors'
import { useDeleteProject, useProject, useUpdateProject } from '@/application/use-cases/projects'
import { useRuns } from '@/application/use-cases/runs'
import { useSystemStatus } from '@/application/use-cases/system'
import { draftFromProject, LANGUAGE_LABELS, type Project } from '@/domain/project'
import { PageHeader } from '../components/PageHeader'
import { RunList } from '../components/runs/RunList'
import { ProjectForm } from '../components/ProjectForm'
import { Button, ButtonLink } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/States'
import { useToast } from '../components/ui/Toast'
import { formatDateTime, formatRelativeTime } from '../lib/format'

function DetailRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-xs text-fg-subtle">{label}</dt>
      <dd className={value ? 'text-right text-[13px] text-fg' : 'text-[13px] text-fg-subtle'}>{value ?? 'Not specified'}</dd>
    </div>
  )
}

function ProjectRuns({ projectId, engineReady }: { projectId: string; engineReady: boolean }) {
  const runs = useRuns({ projectId, limit: 10 })
  if (runs.isError) {
    return (
      <div className="p-4">
        <ErrorState error={runs.error} title="Could not load runs" onRetry={() => runs.refetch()} />
      </div>
    )
  }
  if (!runs.data) {
    return (
      <div className="p-4">
        <LoadingBlock label="Loading runs" rows={2} />
      </div>
    )
  }
  if (runs.data.items.length === 0) {
    return (
      <EmptyState
        className="py-6"
        title="No runs yet"
        description={
          engineReady
            ? 'Use Run Project in the top bar to start the agent workflow.'
            : 'Run Project unlocks when the backend reports an LLM provider and run workers are ready.'
        }
      />
    )
  }
  return <RunList runs={runs.data.items} />
}

function Workspace({ project }: { project: Project }) {
  const navigate = useNavigate()
  const toast = useToast()
  const { data: status } = useSystemStatus()
  const update = useUpdateProject(project.id)
  const remove = useDeleteProject()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const startEditing = () => {
    update.reset()
    setEditing(true)
  }

  const handleDelete = () =>
    remove.mutate(project.id, {
      onSuccess: () => {
        toast.success(`Project “${project.name}” deleted`)
        navigate('/projects')
      },
      onError: (error) => {
        setConfirmDelete(false)
        toast.error(errorMessage(error))
      },
    })

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title={project.name}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>Created {formatDateTime(project.createdAt)}</span>
            <span className="text-fg-subtle">Updated {formatRelativeTime(project.updatedAt)}</span>
          </span>
        }
        actions={
          !editing && (
            <>
              <Button size="sm" icon={<Pencil className="size-3.5" />} onClick={startEditing}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="ghost"
                icon={<Trash2 className="size-3.5" />}
                onClick={() => setConfirmDelete(true)}
                className="hover:text-danger"
              >
                Delete
              </Button>
            </>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Panel title={editing ? 'Edit project' : 'Requirements'} icon={<FileText className="size-4" />}>
          {editing ? (
            <ProjectForm
              initial={draftFromProject(project)}
              submitLabel="Save changes"
              submitting={update.isPending}
              serverError={update.error}
              onCancel={() => setEditing(false)}
              onSubmit={(draft) =>
                update.mutate(draft, {
                  onSuccess: () => {
                    toast.success('Project updated')
                    setEditing(false)
                  },
                })
              }
            />
          ) : (
            <div className="space-y-4">
              <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-fg">{project.requirements}</p>
              {project.constraints && (
                <div className="rounded-md border border-line bg-canvas p-3">
                  <p className="mb-1 text-xs font-medium text-fg-muted">Constraints</p>
                  <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-fg">{project.constraints}</p>
                </div>
              )}
            </div>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="Configuration" icon={<Settings2 className="size-4" />} bodyClassName="py-1">
            <dl className="divide-y divide-line">
              <DetailRow label="Language" value={LANGUAGE_LABELS[project.language]} />
              <DetailRow label="Framework" value={project.framework} />
              <DetailRow label="Database" value={project.databasePreference} />
              <DetailRow
                label="Max debug iterations"
                value={status ? String(status.maxDebugIterations) : null}
              />
            </dl>
          </Panel>

          <Panel title="Workflow runs" icon={<History className="size-4" />} bodyClassName="p-0">
            <ProjectRuns projectId={project.id} engineReady={status?.workflowEngine.state === 'ok'} />
          </Panel>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete project?"
        description={
          <>
            This permanently deletes <strong className="text-fg">{project.name}</strong> and all of its workflow runs,
            test results and review findings.
          </>
        }
        confirmLabel="Delete project"
        tone="danger"
        busy={remove.isPending}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}

export function ProjectWorkspacePage() {
  const { projectId } = useParams()
  const query = useProject(projectId)

  if (query.isError) {
    if (query.error instanceof AppError && query.error.kind === 'not_found') {
      return (
        <EmptyState
          className="py-24"
          icon={<SearchX className="size-5" />}
          title="Project not found"
          description="It may have been deleted, or the link is incorrect."
          action={<ButtonLink to="/projects">Back to projects</ButtonLink>}
        />
      )
    }
    return (
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <ErrorState error={query.error} title="Could not load project" onRetry={() => query.refetch()} />
      </div>
    )
  }

  if (!query.data) {
    return (
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <LoadingBlock label="Loading project" rows={5} />
      </div>
    )
  }

  // Keyed so local edit state resets when navigating between projects.
  return <Workspace key={query.data.id} project={query.data} />
}
