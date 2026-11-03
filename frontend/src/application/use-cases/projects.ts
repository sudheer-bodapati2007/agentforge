import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ProjectDraft } from '@/domain/project'
import { useGateways } from '../gateways-context'

export const projectKeys = {
  all: ['projects'] as const,
  list: (search: string) => ['projects', 'list', search] as const,
  detail: (id: string) => ['projects', 'detail', id] as const,
}

export function useProjects(search = '') {
  const { projects } = useGateways()
  return useQuery({
    queryKey: projectKeys.list(search),
    queryFn: () => projects.list({ search: search || undefined }),
    placeholderData: keepPreviousData,
  })
}

export function useProject(id: string | undefined) {
  const { projects } = useGateways()
  return useQuery({
    queryKey: projectKeys.detail(id ?? ''),
    queryFn: () => projects.get(id!),
    enabled: Boolean(id),
  })
}

/** Project changes affect the dashboard too, so both caches are invalidated. */
function useInvalidateProjectData() {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: projectKeys.all }),
      client.invalidateQueries({ queryKey: ['dashboard'] }),
    ])
}

export function useCreateProject() {
  const { projects } = useGateways()
  const invalidate = useInvalidateProjectData()
  return useMutation({
    mutationFn: (draft: ProjectDraft) => projects.create(draft),
    onSuccess: invalidate,
  })
}

export function useUpdateProject(id: string) {
  const { projects } = useGateways()
  const client = useQueryClient()
  const invalidate = useInvalidateProjectData()
  return useMutation({
    mutationFn: (changes: Partial<ProjectDraft>) => projects.update(id, changes),
    onSuccess: (project) => {
      client.setQueryData(projectKeys.detail(id), project)
      return invalidate()
    },
  })
}

export function useDeleteProject() {
  const { projects } = useGateways()
  const client = useQueryClient()
  const invalidate = useInvalidateProjectData()
  return useMutation({
    mutationFn: (id: string) => projects.remove(id),
    onSuccess: (_result, id) => {
      client.removeQueries({ queryKey: projectKeys.detail(id) })
      return invalidate()
    },
  })
}
