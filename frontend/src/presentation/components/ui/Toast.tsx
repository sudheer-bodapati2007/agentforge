import clsx from 'clsx'
import { CircleCheck, CircleX, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

type ToastTone = 'success' | 'error'
interface Toast {
  id: number
  tone: ToastTone
  message: string
}

interface ToastApi {
  success(message: string): void
  error(message: string): void
}

const ToastContext = createContext<ToastApi | null>(null)
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), [])
  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = nextId++
      setToasts((all) => [...all.slice(-3), { id, tone, message }])
      window.setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )
  const api = useMemo<ToastApi>(
    () => ({ success: (m) => push('success', m), error: (m) => push('error', m) }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === 'error' ? 'alert' : 'status'}
            className={clsx(
              'pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-elevated px-3 py-2.5 text-[13px] shadow-panel',
              toast.tone === 'success' ? 'border-success/30' : 'border-danger/30',
            )}
          >
            {toast.tone === 'success' ? (
              <CircleCheck className="mt-px size-4 shrink-0 text-success" aria-hidden />
            ) : (
              <CircleX className="mt-px size-4 shrink-0 text-danger" aria-hidden />
            )}
            <p className="flex-1 text-fg">{toast.message}</p>
            <button
              type="button"
              aria-label="Dismiss notification"
              onClick={() => dismiss(toast.id)}
              className="text-fg-subtle hover:text-fg"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react/only-export-components -- hook co-located with its provider
export function useToast(): ToastApi {
  const api = useContext(ToastContext)
  if (!api) throw new Error('useToast must be used inside <ToastProvider>')
  return api
}
