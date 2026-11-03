import type { DashboardMetrics } from '@/domain/dashboard'
import type { Benchmark } from '@/domain/evaluation'
import type { DocumentChunk, DocumentList, KnowledgeDocument, SearchResult, UploadOutcome } from '@/domain/knowledge'
import type { Project, ProjectDraft, ProjectPage } from '@/domain/project'
import type {
  AgentExecution,
  ApprovalRequest,
  Artifact,
  ReviewFinding,
  Run,
  RunEvent,
  RunStatus,
  TestResult,
} from '@/domain/run'
import type { SystemStatus } from '@/domain/system'
import type { User } from '@/domain/user'

/** Ports the application layer depends on. Infrastructure provides implementations. */
export interface ProjectGateway {
  list(params?: { search?: string; limit?: number; offset?: number }): Promise<ProjectPage>
  get(id: string): Promise<Project>
  create(draft: ProjectDraft): Promise<Project>
  update(id: string, changes: Partial<ProjectDraft>): Promise<Project>
  remove(id: string): Promise<void>
}

export interface DashboardGateway {
  metrics(): Promise<DashboardMetrics>
}

export interface SystemGateway {
  status(): Promise<SystemStatus>
}

export interface KnowledgeGateway {
  list(projectId: string): Promise<DocumentList>
  upload(projectId: string, filename: string, content: string): Promise<UploadOutcome>
  chunks(projectId: string, documentId: string): Promise<DocumentChunk[]>
  reindex(projectId: string, documentId: string): Promise<KnowledgeDocument>
  remove(projectId: string, documentId: string): Promise<void>
  search(projectId: string, query: string, k?: number): Promise<SearchResult>
}

export interface EvaluationGateway {
  /** Most recent benchmarks first. */
  recent(limit?: number): Promise<Benchmark[]>
}

export interface RunListParams {
  projectId?: string
  status?: RunStatus
  limit?: number
  offset?: number
}

export interface RunGateway {
  start(projectId: string, options: { requireApproval: boolean }, idempotencyKey: string): Promise<Run>
  list(params?: RunListParams): Promise<{ items: Run[]; total: number }>
  get(runId: string): Promise<Run>
  cancel(runId: string): Promise<Run>
  resume(runId: string): Promise<Run>
  events(runId: string, after?: number): Promise<RunEvent[]>
  /**
   * Live event stream. Calls `onEvent` for every event in order, reconnecting with
   * Last-Event-ID after network drops; resolves when the run reaches a terminal state
   * or the signal aborts.
   */
  stream(runId: string, onEvent: (event: RunEvent) => void, signal: AbortSignal): Promise<void>
  agents(runId: string): Promise<AgentExecution[]>
  artifacts(runId: string): Promise<Artifact[]>
  artifactContent(runId: string, path: string): Promise<string>
  download(runId: string): Promise<{ blob: Blob; filename: string }>
  tests(runId: string): Promise<TestResult[]>
  findings(runId: string): Promise<ReviewFinding[]>
  approvals(runId: string): Promise<ApprovalRequest[]>
  decide(runId: string, approvalId: string, approve: boolean, comment: string): Promise<ApprovalRequest>
}

export interface AuthSession {
  accessToken: string
  user: User
}

/** Identity provider (Supabase Auth). The backend independently verifies every token. */
export interface AuthGateway {
  /** False when the provider is not configured; sign-in is then impossible. */
  readonly configured: boolean
  getSession(): Promise<AuthSession | null>
  onSessionChange(listener: (session: AuthSession | null) => void): () => void
  signInWithGoogle(redirectTo: string): Promise<void>
  signInWithPassword(email: string, password: string): Promise<void>
  /** `needsConfirmation` is true when the user must click the link in their inbox first. */
  signUpWithPassword(email: string, password: string, redirectTo: string): Promise<{ needsConfirmation: boolean }>
  /** Always resolves the same way whether or not the account exists (no email enumeration). */
  sendPasswordReset(email: string, redirectTo: string): Promise<void>
  /** Sets a new password for the current (recovery) session. */
  updatePassword(password: string): Promise<void>
  signOut(): Promise<void>
}

export interface Gateways {
  auth: AuthGateway
  projects: ProjectGateway
  runs: RunGateway
  dashboard: DashboardGateway
  system: SystemGateway
  evaluations: EvaluationGateway
  knowledge: KnowledgeGateway
}
