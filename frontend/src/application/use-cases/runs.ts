import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { isActive, type RunEvent, type RunStatus } from '@/domain/run'
import { useGateways } from '../gateways-context'
import type { RunListParams } from '../ports'

export const runKeys = {
  all: ['runs'] as const,
  list: (params: RunListParams) => ['runs', 'list', params] as const,
  detail: (id: string) => ['runs', 'detail', id] as const,
  part: (id: string, part: string) => ['runs', 'detail', id, part] as const,
}

export function useRuns(params: RunListParams = {}) {
  const { runs } = useGateways()
  return useQuery({
    queryKey: runKeys.list(params),
    queryFn: () => runs.list(params),
    // Keep lists fresh while anything is still running.
    refetchInterval: (query) => (query.state.data?.items.some((r) => isActive(r.status)) ? 4000 : false),
  })
}

export function useRun(runId: string | undefined) {
  const { runs } = useGateways()
  return useQuery({
    queryKey: runKeys.detail(runId ?? ''),
    queryFn: () => runs.get(runId!),
    enabled: Boolean(runId),
  })
}

function useRunPart<T>(runId: string, part: string, fetcher: () => Promise<T>) {
  return useQuery({ queryKey: runKeys.part(runId, part), queryFn: fetcher, enabled: Boolean(runId) })
}

/** `live` polls (for pages without the run's event stream, e.g. Agent Activity). */
export function useRunAgents(runId: string, live = false) {
  const { runs } = useGateways()
  return useQuery({
    queryKey: runKeys.part(runId, 'agents'),
    queryFn: () => runs.agents(runId),
    enabled: Boolean(runId),
    refetchInterval: live ? 4000 : false,
  })
}
export function useRunArtifacts(runId: string) {
  const { runs } = useGateways()
  return useRunPart(runId, 'artifacts', () => runs.artifacts(runId))
}
export function useRunTests(runId: string) {
  const { runs } = useGateways()
  return useRunPart(runId, 'tests', () => runs.tests(runId))
}
export function useRunFindings(runId: string) {
  const { runs } = useGateways()
  return useRunPart(runId, 'findings', () => runs.findings(runId))
}
export function useRunApprovals(runId: string) {
  const { runs } = useGateways()
  return useRunPart(runId, 'approvals', () => runs.approvals(runId))
}
export function useArtifactContent(runId: string, path: string | null) {
  const { runs } = useGateways()
  return useQuery({
    queryKey: [...runKeys.part(runId, 'file'), path],
    queryFn: () => runs.artifactContent(runId, path!),
    enabled: Boolean(path),
  })
}

/** Which cached reads an event makes stale. Event-driven invalidation, not polling. */
function partsFor(event: RunEvent): string[] {
  if (event.type.startsWith('node.')) return ['agents']
  if (event.type === 'tool.called' && event.payload.tool === 'write_files') return ['artifacts']
  if (event.type === 'tests.completed') return ['tests', 'agents']
  if (event.type === 'approval.requested' || event.type === 'approval.decided') return ['approvals']
  if (event.type.startsWith('run.')) return ['agents', 'artifacts', 'tests', 'findings', 'approvals']
  return []
}

/**
 * Subscribes to a run's live event stream while it is active and keeps the cache in
 * sync. Returns the events received so far (replayed from the start of the run).
 */
export function useRunStream(runId: string, status: RunStatus | undefined) {
  const { runs } = useGateways()
  const client = useQueryClient()
  const [events, setEvents] = useState<RunEvent[]>([])
  const live = status !== undefined && isActive(status)

  useEffect(() => {
    let cancelled = false
    runs
      .events(runId)
      .then((history) => !cancelled && setEvents(history))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [runId, runs])

  useEffect(() => {
    if (!live) return
    const controller = new AbortController()
    runs
      .stream(
        runId,
        (event) => {
          setEvents((current) => (current.some((e) => e.id === event.id) ? current : [...current, event]))
          for (const part of partsFor(event)) void client.invalidateQueries({ queryKey: runKeys.part(runId, part) })
          if (event.type.startsWith('run.') || event.type.startsWith('node.')) {
            void client.invalidateQueries({ queryKey: runKeys.detail(runId) })
          }
          if (event.type === 'run.finished') void client.invalidateQueries({ queryKey: ['dashboard'] })
        },
        controller.signal,
      )
      .catch(() => undefined)
      .finally(() => void client.invalidateQueries({ queryKey: runKeys.detail(runId) }))
    return () => controller.abort()
  }, [client, live, runId, runs])

  return { events, live }
}

function useInvalidateRun() {
  const client = useQueryClient()
  return (runId: string) =>
    Promise.all([
      client.invalidateQueries({ queryKey: runKeys.detail(runId) }),
      client.invalidateQueries({ queryKey: runKeys.all }),
      client.invalidateQueries({ queryKey: ['projects'] }),
    ])
}

export function useStartRun(projectId: string) {
  const { runs } = useGateways()
  const invalidate = useInvalidateRun()
  return useMutation({
    // One key per click: a retried request (double click, flaky network) cannot start two runs.
    mutationFn: (options: { requireApproval: boolean; idempotencyKey: string }) =>
      runs.start(projectId, { requireApproval: options.requireApproval }, options.idempotencyKey),
    onSuccess: (run) => invalidate(run.id),
  })
}

export function useCancelRun() {
  const { runs } = useGateways()
  const invalidate = useInvalidateRun()
  return useMutation({ mutationFn: (runId: string) => runs.cancel(runId), onSuccess: (run) => invalidate(run.id) })
}

export function useResumeRun() {
  const { runs } = useGateways()
  const invalidate = useInvalidateRun()
  return useMutation({ mutationFn: (runId: string) => runs.resume(runId), onSuccess: (run) => invalidate(run.id) })
}

export function useDecideApproval(runId: string) {
  const { runs } = useGateways()
  const client = useQueryClient()
  const invalidate = useInvalidateRun()
  return useMutation({
    mutationFn: (input: { approvalId: string; approve: boolean; comment: string }) =>
      runs.decide(runId, input.approvalId, input.approve, input.comment),
    onSuccess: () =>
      Promise.all([invalidate(runId), client.invalidateQueries({ queryKey: runKeys.part(runId, 'approvals') })]),
  })
}

export function useDownloadRun() {
  const { runs } = useGateways()
  return useMutation({
    mutationFn: async (runId: string) => {
      const { blob, filename } = await runs.download(runId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    },
  })
}
