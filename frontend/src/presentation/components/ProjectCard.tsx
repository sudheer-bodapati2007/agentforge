import { ChevronRight, FolderGit2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { LANGUAGE_LABELS, type Project } from '@/domain/project'
import { formatRelativeTime } from '../lib/format'
import { Badge, RunStatusBadge } from './ui/StatusBadge'

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="group flex flex-col rounded-lg border border-line bg-panel p-4 shadow-panel transition-colors hover:border-line-strong hover:bg-elevated"
    >
      <div className="flex items-start gap-3">
        <div className="grid size-8 shrink-0 place-items-center rounded-md border border-accent/25 bg-accent-soft text-accent">
          <FolderGit2 className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-fg">{project.name}</h3>
          <p className="text-xs text-fg-subtle">Updated {formatRelativeTime(project.updatedAt)}</p>
        </div>
        <ChevronRight className="size-4 text-fg-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />
      </div>
      <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-fg-muted">{project.requirements}</p>
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <Badge tone="neutral">{LANGUAGE_LABELS[project.language]}</Badge>
        {project.framework && <Badge tone="neutral">{project.framework}</Badge>}
        <span className="ml-auto">
          {project.latestRunStatus ? (
            <RunStatusBadge status={project.latestRunStatus} />
          ) : (
            <span className="text-xs text-fg-subtle">No runs yet</span>
          )}
        </span>
      </div>
    </Link>
  )
}
