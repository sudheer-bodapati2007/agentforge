import { FolderKanban, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useProjects } from '@/application/use-cases/projects'
import { PageHeader } from '../components/PageHeader'
import { ProjectCard } from '../components/ProjectCard'
import { ButtonLink } from '../components/ui/Button'
import { Panel } from '../components/ui/Panel'
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States'

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const handle = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(handle)
  }, [value, delayMs])
  return debounced
}

export function ProjectsPage() {
  const [search, setSearch] = useState('')
  const query = useProjects(useDebounced(search.trim(), 250))
  const page = query.data

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Projects"
        description={page ? `${page.total} project${page.total === 1 ? '' : 's'}` : 'Loading…'}
        actions={
          <ButtonLink to="/projects/new" variant="primary" icon={<Plus className="size-4" />}>
            New Project
          </ButtonLink>
        }
      />

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          maxLength={120}
          placeholder="Search projects…"
          aria-label="Search projects"
          className="h-9 w-full rounded-md border border-line-strong bg-panel pr-3 pl-9 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/60 focus:ring-2 focus:ring-accent/40 focus:outline-none"
        />
      </div>

      {query.isError ? (
        <ErrorState error={query.error} title="Could not load projects" onRetry={() => query.refetch()} />
      ) : !page ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading projects">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : page.items.length === 0 ? (
        <Panel>
          {search.trim() ? (
            <EmptyState icon={<Search className="size-5" />} title="No matching projects" description={`Nothing matches "${search.trim()}".`} />
          ) : (
            <EmptyState
              icon={<FolderKanban className="size-5" />}
              title="No projects yet"
              description="A project holds your software requirements and every workflow run against them."
              action={
                <ButtonLink to="/projects/new" variant="primary" icon={<Plus className="size-4" />}>
                  Create project
                </ButtonLink>
              }
            />
          )}
        </Panel>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {page.items.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}
