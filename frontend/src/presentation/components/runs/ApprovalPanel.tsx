import { FileText, ShieldAlert, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '@/application/errors'
import { useDecideApproval } from '@/application/use-cases/runs'
import type { ApprovalRequest } from '@/domain/run'
import { Button } from '../ui/Button'
import { TextAreaField } from '../ui/Field'
import { useToast } from '../ui/Toast'

const TITLES: Record<string, string> = {
  plan: 'Approve the plan before code is generated',
  corrections: 'Approve fixes for blocking review findings',
}

/** Human-in-the-loop decision. The backend enforces that only the owner can decide, once. */
export function ApprovalPanel({ runId, approval }: { runId: string; approval: ApprovalRequest }) {
  const decide = useDecideApproval(runId)
  const toast = useToast()
  const [comment, setComment] = useState('')

  const submit = (approve: boolean) =>
    decide.mutate(
      { approvalId: approval.id, approve, comment },
      {
        onSuccess: () => toast.success(approve ? 'Approved: the workflow will continue' : 'Rejected'),
        onError: (error) => toast.error(errorMessage(error)),
      },
    )

  const summary = approval.details.plan_summary as string | undefined
  const architecture = approval.details.architecture_summary as string | undefined

  return (
    <section
      aria-labelledby="approval-title"
      className="rounded-lg border border-accent/40 bg-accent-soft p-4 shadow-glow"
    >
      <h2 id="approval-title" className="flex items-center gap-2 text-sm font-semibold text-fg">
        <ShieldAlert className="size-4 text-accent" aria-hidden />
        {TITLES[approval.kind] ?? 'Approval required'}
      </h2>
      <p className="mt-1 text-[13px] text-fg-muted">{approval.reason}</p>

      {(summary || architecture) && (
        <dl className="mt-3 space-y-2 text-[13px]">
          {summary && (
            <div>
              <dt className="text-xs text-fg-subtle">Plan</dt>
              <dd className="text-fg">{summary}</dd>
            </div>
          )}
          {architecture && (
            <div>
              <dt className="text-xs text-fg-subtle">Architecture</dt>
              <dd className="text-fg">{architecture}</dd>
            </div>
          )}
        </dl>
      )}

      {approval.affectedResources.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-fg-subtle">Affected files</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {approval.affectedResources.map((path) => (
              <li key={path} className="inline-flex items-center gap-1 rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[11px] text-fg-muted">
                <FileText className="size-3" aria-hidden />
                {path}
              </li>
            ))}
          </ul>
        </div>
      )}

      {approval.securityNotes && (
        <p className="mt-3 rounded-md border border-warning/25 bg-warning-soft p-2 text-xs text-fg">
          <span className="font-medium text-warning">Security: </span>
          {approval.securityNotes}
        </p>
      )}

      <div className="mt-4">
        <TextAreaField
          label="Comment"
          optional
          rows={2}
          value={comment}
          maxLength={2000}
          onChange={(e) => setComment(e.target.value)}
          hint={approval.kind === 'plan' ? 'When rejecting, feedback sends the plan back to the planner (up to 2 revisions).' : undefined}
          placeholder="e.g. Add pagination to the list endpoint"
        />
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="secondary" icon={<ThumbsDown className="size-4" />} onClick={() => submit(false)} loading={decide.isPending && decide.variables?.approve === false} disabled={decide.isPending}>
          Reject
        </Button>
        <Button variant="primary" icon={<ThumbsUp className="size-4" />} onClick={() => submit(true)} loading={decide.isPending && decide.variables?.approve === true} disabled={decide.isPending}>
          Approve
        </Button>
      </div>
    </section>
  )
}
