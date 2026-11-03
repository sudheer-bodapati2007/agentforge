import { AppError } from '@/application/errors'
import type { DashboardGateway, EvaluationGateway, ProjectGateway, SystemGateway } from '@/application/ports'
import type { DashboardMetrics, RecentProject, RecentRun } from '@/domain/dashboard'
import type { Benchmark, EvaluationResult, SystemSummary } from '@/domain/evaluation'
import type { Project, ProjectDraft } from '@/domain/project'
import type { LLMStatus, SystemStatus } from '@/domain/system'
import type { HttpClient } from '../http/http-client'
import { fromWire, listFromWire, toCamel, toSnake } from './wire'

export const toProject = (dto: object) => fromWire<Project>(dto, ['createdAt', 'updatedAt'])

const OPTIONAL_DRAFT_FIELDS = new Set<keyof ProjectDraft>(['framework', 'databasePreference', 'constraints'])

/** Trimmed snake_case body; blank optional fields are sent as null so the backend clears them. */
function toWire(draft: Partial<ProjectDraft>): Record<string, string | null> {
  return Object.fromEntries(
    (Object.entries(draft) as [keyof ProjectDraft, string][]).map(([key, value]) => {
      const trimmed = value.trim()
      return [toSnake(key), OPTIONAL_DRAFT_FIELDS.has(key) && !trimmed ? null : trimmed]
    }),
  )
}

/** Re-key backend validation errors to draft field names so the UI never sees wire names. */
async function withDraftFieldErrors<T>(call: Promise<T>): Promise<T> {
  try {
    return await call
  } catch (error) {
    if (error instanceof AppError && error.fieldErrors.length) {
      throw new AppError(error.kind, error.message, {
        status: error.status,
        fieldErrors: error.fieldErrors.map((e) => ({ ...e, field: toCamel(e.field) })),
      })
    }
    throw error
  }
}

export function createProjectGateway(http: HttpClient): ProjectGateway {
  const path = (id: string) => `/projects/${encodeURIComponent(id)}`
  return {
    async list(params = {}) {
      const dto = await http.request<{ items: object[]; total: number }>('GET', '/projects', {
        query: { q: params.search, limit: params.limit, offset: params.offset },
      })
      return { items: dto.items.map(toProject), total: dto.total }
    },
    get: async (id) => toProject(await http.request<object>('GET', path(id))),
    create: async (draft) =>
      toProject(await withDraftFieldErrors(http.request<object>('POST', '/projects', { body: toWire(draft) }))),
    update: async (id, changes) =>
      toProject(await withDraftFieldErrors(http.request<object>('PATCH', path(id), { body: toWire(changes) }))),
    remove: async (id) => {
      await http.request<void>('DELETE', path(id))
    },
  }
}

export function toDashboardMetrics(dto: { recent_runs: object[]; recent_projects: object[] }): DashboardMetrics {
  return {
    ...fromWire<DashboardMetrics>(dto),
    recentRuns: listFromWire<RecentRun>(['createdAt'])(dto.recent_runs),
    recentProjects: listFromWire<RecentProject>(['updatedAt'])(dto.recent_projects),
  }
}

export function createDashboardGateway(http: HttpClient): DashboardGateway {
  return {
    metrics: async () => toDashboardMetrics(await http.request('GET', '/dashboard/metrics')),
  }
}

export function toSystemStatus(dto: { llm: object }): SystemStatus {
  return { ...fromWire<SystemStatus>(dto), llm: fromWire<LLMStatus>(dto.llm) }
}

interface BenchmarkDto {
  summaries: object[]
  results: { own_tests: object; reference_tests: object }[]
}

// Test tallies keep their wire shape: their keys (executed, passed, total, errors) are single words.
export function toBenchmark(dto: BenchmarkDto): Benchmark {
  return {
    ...fromWire<Benchmark>(dto, ['createdAt']),
    summaries: listFromWire<SystemSummary>()(dto.summaries),
    results: listFromWire<EvaluationResult>()(dto.results),
  }
}

export function createEvaluationGateway(http: HttpClient): EvaluationGateway {
  return {
    async recent(limit) {
      const dto = await http.request<{ benchmarks: BenchmarkDto[] }>('GET', '/evaluations', { query: { limit } })
      return dto.benchmarks.map(toBenchmark)
    },
  }
}

export function createSystemGateway(http: HttpClient): SystemGateway {
  return {
    status: async () => toSystemStatus(await http.request('GET', '/system/status')),
  }
}
