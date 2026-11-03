import { ChevronRight, Menu, Play } from 'lucide-react'
import { Fragment, useState, type ReactNode } from 'react'
import { Link, useMatches, useParams } from 'react-router-dom'
import { useProject } from '@/application/use-cases/projects'
import { useSystemStatus } from '@/application/use-cases/system'
import { canStartWorkflow, workflowUnavailableReason } from '@/domain/system'
import { StartRunDialog } from '../components/runs/StartRunDialog'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/StatusBadge'
import { UserMenu } from './UserMenu'

export interface RouteHandle {
  crumb?: (params: Record<string, string | undefined>) => { label: ReactNode; to?: string }
  /** Routes scoped to a single project show the Run Project control. */
  projectScoped?: boolean
}

export function ProjectCrumb({ id }: { id: string }) {
  const { data } = useProject(id)
  return <>{data?.name ?? 'Project'}</>
}

function Breadcrumbs() {
  const matches = useMatches()
  const params = useParams()
  const crumbs = matches
    .map((m) => (m.handle as RouteHandle | undefined)?.crumb?.(params))
    .filter((c): c is NonNullable<typeof c> => Boolean(c))

  return (
    <ol aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
      {crumbs.map((crumb, i) => {
        const last = i === crumbs.length - 1
        return (
          <Fragment key={i}>
            {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />}
            <li className={last ? 'truncate font-medium text-fg' : 'shrink-0 text-fg-muted'}>
              {crumb.to && !last ? (
                <Link to={crumb.to} className="hover:text-fg">
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current={last ? 'page' : undefined}>{crumb.label}</span>
              )}
            </li>
          </Fragment>
        )
      })}
    </ol>
  )
}

function BackendStatus() {
  const { data, isError, isPending } = useSystemStatus()
  if (isPending) return <Badge tone="neutral">Connecting…</Badge>
  if (isError) return <Badge tone="danger">API offline</Badge>
  if (data.database.state !== 'ok') return <Badge tone="danger">Database error</Badge>
  // Visibility lives on wrappers: a `hidden` class on Badge would lose to its own inline-flex.
  return (
    <>
      <span className="hidden sm:contents">
        <Badge tone="success">API · {data.databaseBackend}</Badge>
      </span>
      <span className="hidden lg:contents">
        <Badge tone={data.llm.state === 'ok' ? 'success' : 'warning'}>
          {data.llm.provider ? `LLM · ${data.llm.provider}` : 'LLM not configured'}
        </Badge>
      </span>
    </>
  )
}

function RunProjectButton({ projectId }: { projectId: string }) {
  const { data: status } = useSystemStatus()
  const [open, setOpen] = useState(false)
  const enabled = canStartWorkflow(status)
  const reason = workflowUnavailableReason(status)
  return (
    <>
      <Button
        variant="primary"
        size="sm"
        icon={<Play className="size-3.5" />}
        disabled={!enabled}
        title={enabled ? 'Start a workflow run' : reason}
        aria-describedby={enabled ? undefined : 'run-unavailable-reason'}
        onClick={() => setOpen(true)}
      >
        Run Project
      </Button>
      {!enabled && (
        <span id="run-unavailable-reason" className="sr-only">
          {reason}
        </span>
      )}
      <StartRunDialog projectId={projectId} open={open} onClose={() => setOpen(false)} />
    </>
  )
}

export function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const matches = useMatches()
  const params = useParams()
  const projectScoped = matches.some((m) => (m.handle as RouteHandle | undefined)?.projectScoped)

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas/80 px-4 backdrop-blur">
      <button
        type="button"
        onClick={onOpenMenu}
        className="-ml-1 rounded-md p-1.5 text-fg-muted hover:bg-hover hover:text-fg md:hidden"
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </button>
      <Breadcrumbs />
      <div className="ml-auto flex items-center gap-2">
        <BackendStatus />
        {projectScoped && params.projectId && <RunProjectButton projectId={params.projectId} />}
        <UserMenu />
      </div>
    </header>
  )
}
