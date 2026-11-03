import { AppError } from '@/application/errors'
import type { RunGateway } from '@/application/ports'
import type { AgentExecution, ApprovalRequest, Artifact, ReviewFinding, Run, RunEvent, TestResult } from '@/domain/run'
import type { HttpClient } from '../http/http-client'
import { fromWire, listFromWire } from './wire'

const RUN_DATES = ['createdAt', 'startedAt', 'finishedAt'] as const
export const toRun = (dto: object) => fromWire<Run>(dto, RUN_DATES)
export const toEvent = (dto: object) => fromWire<RunEvent>(dto, ['createdAt'])
const toApproval = (dto: object) => fromWire<ApprovalRequest>(dto, ['requestedAt', 'decidedAt'])

/* ------------------------------------------------------------------ SSE parsing */

export interface SseMessage {
  id: string | null
  event: string
  data: string
}

/** Incremental parser for the text/event-stream format (comments and retries ignored). */
export function createSseParser(onMessage: (message: SseMessage) => void) {
  let buffer = ''
  return (chunk: string) => {
    buffer += chunk.replace(/\r\n/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      let id: string | null = null
      let event = 'message'
      const data: string[] = []
      for (const line of block.split('\n')) {
        if (!line || line.startsWith(':')) continue
        const colon = line.indexOf(':')
        const field = colon === -1 ? line : line.slice(0, colon)
        const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'id') id = value
        else if (field === 'event') event = value
        else if (field === 'data') data.push(value)
      }
      if (data.length || id) onMessage({ id, event, data: data.join('\n') })
      boundary = buffer.indexOf('\n\n')
    }
  }
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(timer)
      resolve()
    })
  })

/* ------------------------------------------------------------------ gateway */

export function createRunGateway(http: HttpClient): RunGateway {
  const base = (runId: string) => `/runs/${encodeURIComponent(runId)}`
  const get = <T>(path: string, query?: Record<string, string | number | undefined>) =>
    http.request<T>('GET', path, { query })
  const list = async <T>(runId: string, part: string, dates: readonly string[] = []) =>
    listFromWire<T>(dates)(await get<object[]>(`${base(runId)}/${part}`))

  return {
    async start(projectId, options, idempotencyKey) {
      return toRun(
        await http.request<object>('POST', `/projects/${encodeURIComponent(projectId)}/runs`, {
          body: { require_approval: options.requireApproval },
          headers: { 'Idempotency-Key': idempotencyKey },
        }),
      )
    },
    async list(params = {}) {
      const dto = await get<{ items: object[]; total: number }>('/runs', {
        project_id: params.projectId,
        status: params.status,
        limit: params.limit,
        offset: params.offset,
      })
      return { items: dto.items.map(toRun), total: dto.total }
    },
    get: async (runId) => toRun(await get<object>(base(runId))),
    cancel: async (runId) => toRun(await http.request<object>('POST', `${base(runId)}/cancel`)),
    resume: async (runId) => toRun(await http.request<object>('POST', `${base(runId)}/resume`)),
    events: async (runId, after = 0) => (await get<object[]>(`${base(runId)}/events`, { after })).map(toEvent),
    async stream(runId, onEvent, signal) {
      let lastId: string | null = null
      let backoff = 1000
      while (!signal.aborted) {
        let ended = false
        try {
          const response = await http.raw('GET', `${base(runId)}/stream`, {
            headers: lastId ? { 'Last-Event-ID': lastId } : {},
            signal,
          })
          const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader()
          const parse = createSseParser((message) => {
            if (message.event === 'end') {
              ended = true
              return
            }
            if (message.id) lastId = message.id
            try {
              onEvent(toEvent(JSON.parse(message.data) as object))
            } catch {
              /* malformed event: skip it */
            }
          })
          backoff = 1000
          for (;;) {
            const { value, done } = await reader.read()
            if (done || ended) break
            parse(value)
          }
          if (ended) return
        } catch (error) {
          if (signal.aborted) return
          if (error instanceof AppError && error.kind !== 'network' && error.kind !== 'server') throw error
        }
        // Dropped connection: reconnect with Last-Event-ID so nothing is lost or repeated.
        await sleep(backoff, signal)
        backoff = Math.min(backoff * 2, 15_000)
      }
    },
    agents: (runId) => list<AgentExecution>(runId, 'agents', ['startedAt', 'finishedAt']),
    artifacts: (runId) => list<Artifact>(runId, 'artifacts', ['updatedAt']),
    tests: (runId) => list<TestResult>(runId, 'tests', ['createdAt']),
    findings: (runId) => list<ReviewFinding>(runId, 'reviews'),
    approvals: async (runId) => (await get<object[]>(`${base(runId)}/approvals`)).map(toApproval),
    async artifactContent(runId, path) {
      return (await get<{ content: string }>(`${base(runId)}/artifacts/content`, { path })).content
    },
    async download(runId) {
      const response = await http.raw('GET', `${base(runId)}/download`)
      const disposition = response.headers.get('Content-Disposition') ?? ''
      const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `run-${runId.slice(0, 8)}.zip`
      return { blob: await response.blob(), filename }
    },
    async decide(runId, approvalId, approve, comment) {
      return toApproval(
        await http.request<object>('POST', `${base(runId)}/approvals/${encodeURIComponent(approvalId)}`, {
          body: { approve, comment: comment.trim() || null },
        }),
      )
    },
  }
}
