import clsx from 'clsx'
import type { ReactNode } from 'react'

interface PanelProps {
  title?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

export function Panel({ title, icon, actions, children, className, bodyClassName }: PanelProps) {
  return (
    <section
      className={clsx('flex min-w-0 flex-col rounded-lg border border-line bg-panel shadow-panel', className)}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 className="flex items-center gap-2 text-[13px] font-semibold text-fg">
            {icon && <span className="text-fg-muted">{icon}</span>}
            {title}
          </h2>
          {actions && <div className="flex items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={clsx('min-h-0 flex-1 p-4', bodyClassName)}>{children}</div>
    </section>
  )
}
