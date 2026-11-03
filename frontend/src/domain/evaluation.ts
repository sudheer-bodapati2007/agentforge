/** Benchmark results (Phase 6): the multi-agent workflow vs a single-agent baseline. */

export type SystemKind = 'multi_agent' | 'single_agent'

/** Fixed order: colors and columns follow the system, never its rank. */
export const SYSTEMS: readonly SystemKind[] = ['multi_agent', 'single_agent']

export const SYSTEM_LABELS: Record<SystemKind, string> = {
  multi_agent: 'Multi-agent workflow',
  single_agent: 'Single-agent baseline',
}

export interface TestTally {
  executed: boolean
  passed: number
  total: number
  errors: number
}

export interface EvaluationResult {
  taskId: string
  taskTitle: string
  category: string
  system: SystemKind
  modelName: string
  /** Every hidden reference test passed. */
  solved: boolean
  ownTests: TestTally
  referenceTests: TestTally
  debugIterations: number
  testRuns: number
  findingsTotal: number
  blockingFindings: number
  latencySeconds: number
  inputTokens: number
  outputTokens: number
  estimatedCostUsd: number | null
  humanInterventions: number
  error: string | null
}

/** `null` means "undefined for this data" and must never be shown as zero. */
export interface SystemSummary {
  system: SystemKind
  tasks: number
  solved: number
  solveRate: number | null
  referencePassRate: number | null
  ownSuiteSuccessRate: number | null
  meanDebugIterations: number | null
  medianLatencySeconds: number | null
  totalInputTokens: number
  totalOutputTokens: number
  totalCostUsd: number | null
  blockingFindings: number
  errors: number
}

export interface Benchmark {
  id: string
  createdAt: Date
  modelNames: string[]
  demoModel: boolean
  summaries: SystemSummary[]
  results: EvaluationResult[]
}

/** Same rule as the backend: null when the suite never ran, 0 when it ran and nothing passed. */
export function passFraction(tally: TestTally): number | null {
  if (!tally.executed) return null
  return tally.total ? tally.passed / tally.total : 0
}

export interface TaskRow {
  taskId: string
  taskTitle: string
  category: string
  bySystem: Partial<Record<SystemKind, EvaluationResult>>
}

/** One row per task (in result order) with each system's result side by side. */
export function taskRows(results: EvaluationResult[]): TaskRow[] {
  const rows = new Map<string, TaskRow>()
  for (const result of results) {
    const row = rows.get(result.taskId) ?? {
      taskId: result.taskId,
      taskTitle: result.taskTitle,
      category: result.category,
      bySystem: {},
    }
    row.bySystem[result.system] = result
    rows.set(result.taskId, row)
  }
  return [...rows.values()]
}
