export type ComponentState = 'ok' | 'error' | 'not_configured' | 'not_implemented'

export interface ComponentStatus {
  state: ComponentState
  detail: string | null
}

export interface LLMStatus extends ComponentStatus {
  provider: string | null
  model: string | null
  apiKeyPresent: boolean
}

export interface SystemStatus {
  appName: string
  version: string
  environment: string
  database: ComponentStatus
  databaseBackend: string
  llm: LLMStatus
  workflowEngine: ComponentStatus
  sandbox: ComponentStatus
  maxDebugIterations: number
}

/** A workflow can only be started once the backend reports both the engine and an LLM as usable. */
export function canStartWorkflow(status: SystemStatus | undefined): boolean {
  return status?.workflowEngine.state === 'ok' && status.llm.state === 'ok'
}

export function workflowUnavailableReason(status: SystemStatus | undefined): string {
  if (!status) return 'Checking backend status…'
  if (status.workflowEngine.state !== 'ok')
    return status.workflowEngine.detail ?? 'Workflow engine unavailable'
  if (status.llm.state !== 'ok') return status.llm.detail ?? 'LLM provider not configured'
  return ''
}
