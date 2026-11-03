import { Play, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '@/application/errors'
import { useStartRun } from '@/application/use-cases/runs'
import { Button } from '../ui/Button'
import { useToast } from '../ui/Toast'

function newKey(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

/** Confirms a run and its approval policy, then starts it with an idempotency key. */
export function StartRunDialog({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const navigate = useNavigate()
  const toast = useToast()
  const start = useStartRun(projectId)
  const [requireApproval, setRequireApproval] = useState(true)
  // One key per opening of the dialog: double-submits and retries reuse it.
  const [key, setKey] = useState(newKey)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      setKey(newKey())
      dialog.showModal?.()
    }
    if (!open && dialog.open) dialog.close?.()
  }, [open])

  const submit = () =>
    start.mutate(
      { requireApproval, idempotencyKey: key },
      {
        onSuccess: (run) => {
          onClose()
          navigate(`/runs/${run.id}`)
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    )

  return (
    <dialog
      ref={ref}
      aria-labelledby="start-run-title"
      onCancel={(e) => {
        e.preventDefault()
        if (!start.isPending) onClose()
      }}
      className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-xl border border-line-strong bg-panel p-0 text-fg shadow-panel backdrop:bg-black/60"
    >
      {open && (
        <div className="p-5">
          <h2 id="start-run-title" className="text-base font-semibold">
            Run the agent workflow
          </h2>
          <p className="mt-2 text-[13px] leading-relaxed text-fg-muted">
            The planner, architect, coding, testing, debugging, review and documentation agents will work on this
            project's requirements. Generated tests run in an isolated sandbox without network access.
          </p>
          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-md border border-line bg-canvas p-3">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-[var(--color-accent)]"
              checked={requireApproval}
              onChange={(e) => setRequireApproval(e.target.checked)}
            />
            <span>
              <span className="flex items-center gap-1.5 text-[13px] font-medium">
                <ShieldCheck className="size-4 text-accent" aria-hidden /> Require my approval
              </span>
              <span className="block text-xs text-fg-subtle">
                Pause before code is generated and before applying fixes for serious review findings.
              </span>
            </span>
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={start.isPending}>
              Cancel
            </Button>
            <Button variant="primary" icon={<Play className="size-4" />} onClick={submit} loading={start.isPending}>
              Start run
            </Button>
          </div>
        </div>
      )}
    </dialog>
  )
}
