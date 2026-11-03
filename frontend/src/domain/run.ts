export const RUN_STATUSES = [
  'queued',
  'running',
  'awaiting_approval',
  'completed',
  'partially_completed',
  'failed',
  'cancelled',
] as const

export type RunStatus = (typeof RUN_STATUSES)[number]

export type StatusTone = 'neutral' | 'info' | 'accent' | 'success' | 'warning' | 'danger'

interface RunStatusMeta {
  label: string
  tone: StatusTone
  terminal: boolean
}

export const RUN_STATUS_META: Record<RunStatus, RunStatusMeta> = {
  queued: { label: 'Queued', tone: 'neutral', terminal: false },
  running: { label: 'Running', tone: 'info', terminal: false },
  awaiting_approval: { label: 'Awaiting approval', tone: 'accent', terminal: false },
  completed: { label: 'Completed', tone: 'success', terminal: true },
  partially_completed: { label: 'Partial', tone: 'warning', terminal: true },
  failed: { label: 'Failed', tone: 'danger', terminal: true },
  cancelled: { label: 'Cancelled', tone: 'neutral', terminal: true },
}

export function isActive(status: RunStatus): boolean {
  return !RUN_STATUS_META[status].terminal
}

/** Graph nodes, in pipeline order. Names match the backend's LangGraph node ids. */
export const WORKFLOW_NODES = [
  { id: 'plan', label: 'Planner', agent: 'planner' },
  { id: 'architect', label: 'Architect', agent: 'architect' },
  { id: 'plan_approval', label: 'Plan approval', agent: null },
  { id: 'schema', label: 'Database schema', agent: 'database' },
  { id: 'code', label: 'Coding', agent: 'coder' },
  { id: 'write_tests', label: 'Write tests', agent: 'tester' },
  { id: 'run_tests', label: 'Run tests', agent: 'tester' },
  { id: 'debug', label: 'Debugging', agent: 'debugger' },
  { id: 'review', label: 'Code review', agent: 'reviewer' },
  { id: 'correction_approval', label: 'Fix approval', agent: null },
  { id: 'correct', label: 'Corrections', agent: 'coder' },
  { id: 'document', label: 'Documentation', agent: 'documenter' },
  { id: 'report', label: 'Final report', agent: null },
] as const

export type WorkflowNodeId = (typeof WORKFLOW_NODES)[number]['id']
export type NodeState = 'pending' | 'running' | 'completed' | 'failed' | 'waiting' | 'skipped'

export interface WorkflowEdge {
  from: WorkflowNodeId
  to: WorkflowNodeId
  /** The routing condition, as in backend/app/application/workflow/routing.py. */
  label?: string
  /** A bounded loop back to an earlier step. */
  loop?: boolean
}

/** The graph's edges, mirroring the LangGraph wiring in infrastructure/workflow/langgraph_engine.py. */
export const WORKFLOW_EDGES: readonly WorkflowEdge[] = [
  { from: 'plan', to: 'architect' },
  { from: 'architect', to: 'plan_approval' },
  { from: 'plan_approval', to: 'schema', label: 'approved, database' },
  { from: 'plan_approval', to: 'code', label: 'approved' },
  { from: 'schema', to: 'code' },
  { from: 'plan_approval', to: 'plan', label: 'rejected with feedback', loop: true },
  { from: 'plan_approval', to: 'report', label: 'rejected' },
  { from: 'code', to: 'write_tests' },
  { from: 'write_tests', to: 'run_tests' },
  { from: 'run_tests', to: 'review', label: 'pass' },
  { from: 'run_tests', to: 'debug', label: 'fail, retries left' },
  { from: 'debug', to: 'run_tests', label: 're-test', loop: true },
  { from: 'run_tests', to: 'document', label: 'retry limit / not run' },
  { from: 'review', to: 'correction_approval', label: 'blocking findings' },
  { from: 'review', to: 'document', label: 'clean' },
  { from: 'correction_approval', to: 'correct', label: 'approved' },
  { from: 'correction_approval', to: 'document', label: 'rejected' },
  { from: 'correct', to: 'run_tests', label: 're-test', loop: true },
  { from: 'document', to: 'report' },
]

/** Executions per graph node, in attempt order. */
export function executionsByNode(executions: AgentExecution[]): Map<string, AgentExecution[]> {
  const byNode = new Map<string, AgentExecution[]>()
  for (const e of executions) byNode.set(e.node, [...(byNode.get(e.node) ?? []), e])
  for (const list of byNode.values()) list.sort((a, b) => a.attempt - b.attempt)
  return byNode
}

export interface Run {
  id: string
  projectId: string
  projectName: string
  status: RunStatus
  currentNode: string | null
  requireApproval: boolean
  cancelRequested: boolean
  debugIterations: number
  maxDebugIterations: number
  llmModel: string | null
  demoModel: boolean
  createdAt: Date
  startedAt: Date | null
  finishedAt: Date | null
  durationSeconds: number | null
  error: string | null
  inputTokens: number
  outputTokens: number
  estimatedCostUsd: number | null
  finalReport: FinalReport | null
}

export interface FinalReport {
  outcome: string
  model: { name: string; demo: boolean }
  verified: {
    tests: TestResultLike | null
    test_runs: number
    debug_iterations: number
    tool_findings: unknown[]
    files: string[]
  }
  generated: {
    summary: string | null
    features: string[]
    acceptance_criteria: string[]
    assumptions: string[]
    open_questions: string[]
    llm_findings: unknown[]
  }
  limitations: string[]
  tasks_not_verified: string[]
  usage: { input_tokens: number; output_tokens: number; estimated_cost_usd: number | null }
}

interface TestResultLike {
  executed: boolean
  total: number
  passed: number
  failed: number
  errors: number
  skipped: number
  succeeded?: boolean
  unavailable_reason?: string | null
}

export interface RunEvent {
  id: number
  type: string
  node: string | null
  payload: Record<string, unknown>
  createdAt: Date
}

export interface AgentExecution {
  id: string
  node: string
  agent: string | null
  attempt: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  summary: string | null
  error: string | null
  inputTokens: number
  outputTokens: number
  startedAt: Date | null
  finishedAt: Date | null
}

export interface Artifact {
  path: string
  kind: 'source' | 'test' | 'doc' | string
  sha256: string
  sizeBytes: number
  createdBy: string | null
  updatedAt: Date
}

export interface TestFailure {
  name: string
  message: string
  file_path?: string | null
  line?: number | null
}

/** Projects with a PostgreSQL database. Keeps the API's (snake_case) shape: it is a nested contract. */
export interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  default: string | null
  primary_key: boolean
}

export interface SchemaTable {
  name: string
  columns: SchemaColumn[]
  foreign_keys: { columns: string[]; references: string }[]
  unique: string[][]
  indexes: { name: string; columns: string[]; unique: boolean }[]
}

export interface DatabaseReport {
  migrations: { file: string; ok: boolean; error: string | null }[]
  schema: SchemaTable[]
  error: string | null
}

export function migrated(report: DatabaseReport): boolean {
  return report.error === null && report.migrations.every((m) => m.ok)
}

export interface TestResult {
  attempt: number
  command: string
  executed: boolean
  exitCode: number | null
  total: number
  passed: number
  failed: number
  errors: number
  skipped: number
  durationMs: number | null
  outputExcerpt: string | null
  failures: TestFailure[]
  unavailableReason: string | null
  database?: DatabaseReport | null
}

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

export interface ReviewFinding {
  id: string
  cycle: number
  severity: Severity
  category: string
  title: string
  description: string
  filePath: string | null
  line: number | null
  suggestion: string | null
  source: 'tool' | 'llm'
  toolName: string | null
}

export interface ApprovalRequest {
  id: string
  kind: 'plan' | 'corrections' | string
  cycle: number
  status: 'pending' | 'approved' | 'rejected'
  reason: string
  affectedResources: string[]
  securityNotes: string | null
  details: Record<string, unknown>
  decisionComment: string | null
  requestedAt: Date
  decidedAt: Date | null
}

/**
 * Derive each node's visual state purely from confirmed backend records, so the
 * graph never shows progress the backend has not reported.
 */
export function nodeStates(run: Run, executions: AgentExecution[]): Record<WorkflowNodeId, NodeState> {
  const states = Object.fromEntries(WORKFLOW_NODES.map((n) => [n.id, 'pending'])) as Record<WorkflowNodeId, NodeState>
  for (const execution of executions) {
    const id = execution.node as WorkflowNodeId
    if (!(id in states)) continue
    const mapped: NodeState =
      execution.status === 'completed' ? 'completed' : execution.status === 'failed' ? 'failed' : execution.status === 'running' ? 'running' : 'pending'
    // A later attempt overrides an earlier one (e.g. run_tests failing, then passing).
    states[id] = mapped
  }
  if (run.status === 'awaiting_approval' && run.currentNode && run.currentNode in states) {
    states[run.currentNode as WorkflowNodeId] = 'waiting'
  }
  const approvalsPassed = executions.some((e) => e.node === 'code' || e.node === 'schema')
  if (approvalsPassed && states.plan_approval === 'pending') states.plan_approval = run.requireApproval ? 'completed' : 'skipped'
  if (!isActive(run.status)) {
    for (const node of WORKFLOW_NODES) if (states[node.id] === 'pending' || states[node.id] === 'running') states[node.id] = states[node.id] === 'running' ? 'failed' : 'skipped'
  }
  return states
}
