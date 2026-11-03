import { vi } from 'vitest'
import type { AuthSession, Gateways } from '@/application/ports'
import type { DashboardMetrics } from '@/domain/dashboard'
import type { Benchmark, EvaluationResult, SystemSummary } from '@/domain/evaluation'
import type { DocumentChunk, KnowledgeDocument, SearchHit } from '@/domain/knowledge'
import type { Project } from '@/domain/project'
import {
  RUN_STATUSES,
  type AgentExecution,
  type ApprovalRequest,
  type Artifact,
  type ReviewFinding,
  type Run,
  type RunEvent,
  type RunStatus,
  type TestResult,
} from '@/domain/run'
import type { SystemStatus } from '@/domain/system'

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'p-1',
    name: 'Student API',
    requirements: 'Build a student management REST API with attendance tracking.',
    language: 'python',
    framework: 'FastAPI',
    databasePreference: null,
    constraints: null,
    createdAt: new Date('2026-10-01T10:00:00Z'),
    updatedAt: new Date('2026-10-01T10:00:00Z'),
    runCount: 0,
    latestRunStatus: null,
    ...overrides,
  }
}

export function emptyMetrics(overrides: Partial<DashboardMetrics> = {}): DashboardMetrics {
  return {
    totalProjects: 0,
    totalRuns: 0,
    runsByStatus: Object.fromEntries(RUN_STATUSES.map((s) => [s, 0])) as Record<RunStatus, number>,
    completionRate: null,
    testPassRate: null,
    executedTestSuites: 0,
    averageDurationSeconds: null,
    totalEstimatedCostUsd: null,
    recentRuns: [],
    recentProjects: [],
    ...overrides,
  }
}

export function makeDocument(overrides: Partial<KnowledgeDocument> = {}): KnowledgeDocument {
  return {
    id: 'd-1',
    projectId: 'p-1',
    filename: 'conventions.md',
    kind: 'markdown',
    sizeBytes: 2048,
    sha256: 'a'.repeat(64),
    chunkCount: 3,
    embedder: 'hash-384',
    redactedLines: 0,
    stale: false,
    createdAt: new Date('2026-10-22T10:00:00Z'),
    updatedAt: new Date('2026-10-22T10:00:00Z'),
    ...overrides,
  }
}

export function makeSearchHit(overrides: Partial<SearchHit> = {}): SearchHit {
  return {
    documentId: 'd-1',
    source: 'conventions.md',
    location: 'lines 9-10 (Team conventions > Pagination)',
    heading: 'Team conventions > Pagination',
    startLine: 9,
    endLine: 10,
    text: 'List endpoints accept limit and offset; the maximum limit is 100.',
    denseScore: 0.41,
    sparseScore: 3.2,
    fusedScore: 0.0328,
    rerankScore: 0.66,
    score: 0.83,
    ...overrides,
  }
}

export function makeEvaluationResult(overrides: Partial<EvaluationResult> = {}): EvaluationResult {
  return {
    taskId: 'crud',
    taskTitle: 'In-memory todo store (CRUD)',
    category: 'CRUD',
    system: 'multi_agent',
    modelName: 'ollama:qwen2.5-coder:7b',
    solved: true,
    ownTests: { executed: true, passed: 4, total: 4, errors: 0 },
    referenceTests: { executed: true, passed: 14, total: 14, errors: 0 },
    debugIterations: 1,
    testRuns: 2,
    findingsTotal: 0,
    blockingFindings: 0,
    latencySeconds: 75,
    inputTokens: 6000,
    outputTokens: 2000,
    estimatedCostUsd: null,
    humanInterventions: 0,
    error: null,
    ...overrides,
  }
}

export function makeSummary(overrides: Partial<SystemSummary> = {}): SystemSummary {
  return {
    system: 'multi_agent',
    tasks: 6,
    solved: 4,
    solveRate: 4 / 6,
    referencePassRate: 0.85,
    ownSuiteSuccessRate: 1,
    meanDebugIterations: 1.5,
    medianLatencySeconds: 80,
    totalInputTokens: 36000,
    totalOutputTokens: 12000,
    totalCostUsd: null,
    blockingFindings: 0,
    errors: 0,
    ...overrides,
  }
}

export function makeBenchmark(overrides: Partial<Benchmark> = {}): Benchmark {
  return {
    id: '20261022-140000',
    createdAt: new Date('2026-10-22T14:00:00Z'),
    modelNames: ['ollama:qwen2.5-coder:7b'],
    demoModel: false,
    summaries: [makeSummary(), makeSummary({ system: 'single_agent', solved: 2, solveRate: 2 / 6, ownSuiteSuccessRate: null })],
    results: [
      makeEvaluationResult(),
      makeEvaluationResult({
        system: 'single_agent',
        solved: false,
        referenceTests: { executed: true, passed: 0, total: 0, errors: 1 },
        ownTests: { executed: false, passed: 0, total: 0, errors: 0 },
        error: 'model returned invalid JSON',
      }),
    ],
    ...overrides,
  }
}

export function makeStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    appName: 'AgentForge',
    version: '0.1.0',
    environment: 'test',
    database: { state: 'ok', detail: null },
    databaseBackend: 'postgresql',
    llm: {
      state: 'not_configured',
      detail: 'Set LLM_PROVIDER, LLM_MODEL and LLM_API_KEY',
      provider: null,
      model: null,
      apiKeyPresent: false,
    },
    workflowEngine: { state: 'not_implemented', detail: 'LangGraph workflow arrives in Phase 2' },
    sandbox: { state: 'not_implemented', detail: 'Docker test sandbox arrives in Phase 2' },
    maxDebugIterations: 3,
    ...overrides,
  }
}

export function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'r-1',
    projectId: 'p-1',
    projectName: 'Student API',
    status: 'completed',
    currentNode: null,
    requireApproval: true,
    cancelRequested: false,
    debugIterations: 1,
    maxDebugIterations: 3,
    llmModel: 'google:gemini-test',
    demoModel: false,
    createdAt: new Date('2026-10-01T10:00:00Z'),
    startedAt: new Date('2026-10-01T10:00:01Z'),
    finishedAt: new Date('2026-10-01T10:02:01Z'),
    durationSeconds: 120,
    error: null,
    inputTokens: 1200,
    outputTokens: 600,
    estimatedCostUsd: null,
    finalReport: null,
    ...overrides,
  }
}

export function makeApproval(overrides: Partial<ApprovalRequest> = {}): ApprovalRequest {
  return {
    id: 'a-1',
    kind: 'plan',
    cycle: 1,
    status: 'pending',
    reason: 'Review the plan and architecture before code is generated.',
    affectedResources: ['app/main.py'],
    securityNotes: 'Generated code will run in an isolated container without network access.',
    details: { plan_summary: 'A task API', architecture_summary: 'FastAPI app' },
    decisionComment: null,
    requestedAt: new Date('2026-10-01T10:01:00Z'),
    decidedAt: null,
    ...overrides,
  }
}

export function createFakeRuns() {
  return {
    start: vi.fn(async (_projectId: string, _options: { requireApproval: boolean }, _key: string) => makeRun({ id: 'r-new', status: 'queued' })),
    list: vi.fn(async (_params?: unknown) => ({ items: [] as Run[], total: 0 })),
    get: vi.fn(async (id: string) => makeRun({ id })),
    cancel: vi.fn(async (id: string) => makeRun({ id, status: 'cancelled' })),
    resume: vi.fn(async (id: string) => makeRun({ id, status: 'queued' })),
    events: vi.fn(async (_id: string, _after?: number) => [] as RunEvent[]),
    stream: vi.fn(async (_id: string, _onEvent: (e: RunEvent) => void, _signal: AbortSignal) => {}),
    agents: vi.fn(async (_id: string) => [] as AgentExecution[]),
    artifacts: vi.fn(async (_id: string) => [] as Artifact[]),
    artifactContent: vi.fn(async (_id: string, _path: string) => ''),
    download: vi.fn(async (_id: string) => ({ blob: new Blob(['zip']), filename: 'project.zip' })),
    tests: vi.fn(async (_id: string) => [] as TestResult[]),
    findings: vi.fn(async (_id: string) => [] as ReviewFinding[]),
    approvals: vi.fn(async (_id: string) => [] as ApprovalRequest[]),
    decide: vi.fn(async (_id: string, approvalId: string, approve: boolean, _comment: string) =>
      makeApproval({ id: approvalId, status: approve ? 'approved' : 'rejected' }),
    ),
  }
}

export function makeSession(overrides: Partial<AuthSession['user']> = {}): AuthSession {
  return {
    accessToken: 'test-token',
    user: { id: 'u-1', email: 'ada@example.com', name: 'Ada Lovelace', avatarUrl: null, ...overrides },
  }
}

export function createFakeAuth(initial: AuthSession | null = makeSession()) {
  let current = initial
  const listeners = new Set<(s: AuthSession | null) => void>()
  return {
    configured: true,
    getSession: vi.fn(async () => current),
    onSessionChange: vi.fn((listener: (s: AuthSession | null) => void) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    }),
    signInWithGoogle: vi.fn(async (_redirectTo: string) => {}),
    signInWithPassword: vi.fn(async (_email: string, _password: string) => {
      current = makeSession({ email: _email, name: null })
      listeners.forEach((l) => l(current))
    }),
    signUpWithPassword: vi.fn(async (_email: string, _password: string, _redirectTo: string) => ({
      needsConfirmation: true,
    })),
    sendPasswordReset: vi.fn(async (_email: string, _redirectTo: string) => {}),
    updatePassword: vi.fn(async (_password: string) => {}),
    signOut: vi.fn(async () => {
      current = null
      listeners.forEach((l) => l(null))
    }),
  }
}

export function createFakeGateways(session: AuthSession | null = makeSession()) {
  return {
    auth: createFakeAuth(session),
    projects: {
      list: vi.fn(async () => ({ items: [] as Project[], total: 0 })),
      get: vi.fn(async (id: string) => makeProject({ id })),
      create: vi.fn(async () => makeProject({ id: 'new-1' })),
      update: vi.fn(async (id: string) => makeProject({ id })),
      remove: vi.fn(async () => undefined),
    },
    runs: createFakeRuns(),
    dashboard: { metrics: vi.fn(async () => emptyMetrics()) },
    system: { status: vi.fn(async () => makeStatus()) },
    evaluations: { recent: vi.fn(async () => [] as Benchmark[]) },
    knowledge: {
      list: vi.fn(async () => ({ items: [] as KnowledgeDocument[], embedder: 'hash-384' })),
      upload: vi.fn(async (_projectId: string, filename: string) => ({
        document: makeDocument({ filename }),
        created: true,
        unchanged: false,
      })),
      chunks: vi.fn(async () => [] as DocumentChunk[]),
      reindex: vi.fn(async (_projectId: string, id: string) => makeDocument({ id })),
      remove: vi.fn(async () => undefined),
      search: vi.fn(async (_projectId: string, query: string) => ({
        query,
        embedder: 'hash-384',
        mode: 'hybrid',
        reranker: 'lexical' as string | null,
        results: [] as SearchHit[],
      })),
    },
  } satisfies Gateways
}
