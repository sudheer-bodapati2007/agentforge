import type { NodeState } from '@/domain/run'

export const STATE_CLASSES: Record<NodeState, string> = {
  pending: 'border-line bg-panel text-fg-subtle',
  running: 'border-info/60 bg-info-soft text-fg shadow-[0_0_0_1px_var(--color-info)] animate-pulse',
  completed: 'border-success/40 bg-success-soft text-fg',
  failed: 'border-danger/50 bg-danger-soft text-fg',
  waiting: 'border-accent/60 bg-accent-soft text-fg shadow-glow',
  skipped: 'border-dashed border-line bg-panel text-fg-subtle/60',
}

export const STATE_LABEL: Record<NodeState, string> = {
  pending: 'pending',
  running: 'running',
  completed: 'done',
  failed: 'failed',
  waiting: 'awaiting approval',
  skipped: 'skipped',
}
