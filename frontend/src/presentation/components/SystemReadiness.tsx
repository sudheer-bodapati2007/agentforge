import { Box, Cpu, Database, Workflow } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ComponentState, ComponentStatus, SystemStatus } from '@/domain/system'
import type { StatusTone } from '@/domain/run'
import { Badge } from './ui/StatusBadge'

const STATE_META: Record<ComponentState, { label: string; tone: StatusTone }> = {
  ok: { label: 'Ready', tone: 'success' },
  error: { label: 'Error', tone: 'danger' },
  not_configured: { label: 'Not configured', tone: 'warning' },
  not_implemented: { label: 'Not built yet', tone: 'neutral' },
}

function Row({ icon, name, status, extra }: { icon: ReactNode; name: string; status: ComponentStatus; extra?: string }) {
  const meta = STATE_META[status.state]
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className="mt-0.5 text-fg-muted" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-fg">
          {name}
          {extra && <span className="ml-2 font-mono text-xs font-normal text-fg-subtle">{extra}</span>}
        </p>
        {status.detail && <p className="text-xs text-fg-subtle">{status.detail}</p>}
      </div>
      <Badge tone={meta.tone}>{meta.label}</Badge>
    </li>
  )
}

/** Live readiness as reported by GET /api/system/status. */
export function SystemReadiness({ status }: { status: SystemStatus }) {
  return (
    <ul className="divide-y divide-line">
      <Row icon={<Database className="size-4" />} name="Database" status={status.database} extra={status.databaseBackend} />
      <Row
        icon={<Cpu className="size-4" />}
        name="LLM provider"
        status={status.llm}
        extra={status.llm.provider ? `${status.llm.provider}${status.llm.model ? ` · ${status.llm.model}` : ''}` : undefined}
      />
      <Row icon={<Workflow className="size-4" />} name="Workflow engine" status={status.workflowEngine} />
      <Row icon={<Box className="size-4" />} name="Execution sandbox" status={status.sandbox} />
    </ul>
  )
}
