import clsx from 'clsx'
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

const CONTROL =
  'w-full rounded-md border bg-canvas px-3 text-sm text-fg placeholder:text-fg-subtle transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40'

function controlClass(error?: string) {
  return clsx(CONTROL, error ? 'border-danger/60' : 'border-line-strong focus:border-accent/60')
}

interface FieldShellProps {
  label: string
  hint?: ReactNode
  error?: string
  optional?: boolean
  children: (props: { id: string; describedBy: string | undefined }) => ReactNode
}

function FieldShell({ label, hint, error, optional, children }: FieldShellProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="flex items-baseline gap-2 text-[13px] font-medium text-fg">
        {label}
        {optional && <span className="text-xs font-normal text-fg-subtle">Optional</span>}
      </label>
      {children({ id, describedBy })}
      {error ? (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="text-xs text-fg-subtle">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

type BaseProps = { label: string; hint?: ReactNode; error?: string; optional?: boolean }

export function TextField({ label, hint, error, optional, className, ...rest }: BaseProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional}>
      {({ id, describedBy }) => (
        <input
          id={id}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={describedBy}
          className={clsx(controlClass(error), 'h-9', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

export function TextAreaField({ label, hint, error, optional, className, ...rest }: BaseProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional}>
      {({ id, describedBy }) => (
        <textarea
          id={id}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={describedBy}
          className={clsx(controlClass(error), 'min-h-28 resize-y py-2 leading-relaxed', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

export function SelectField({
  label,
  hint,
  error,
  optional,
  className,
  children,
  ...rest
}: BaseProps & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional}>
      {({ id, describedBy }) => (
        <select
          id={id}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={describedBy}
          className={clsx(controlClass(error), 'h-9', className)}
          {...rest}
        >
          {children}
        </select>
      )}
    </FieldShell>
  )
}
