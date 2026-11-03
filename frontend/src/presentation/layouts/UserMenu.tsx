import { LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/application/auth-context'
import { displayName, initials, type User } from '@/domain/user'

function Avatar({ user }: { user: User }) {
  const [broken, setBroken] = useState(false)
  if (user.avatarUrl && !broken) {
    return (
      <img
        src={user.avatarUrl}
        alt=""
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className="size-7 rounded-full border border-line-strong object-cover"
      />
    )
  }
  return (
    <span className="grid size-7 place-items-center rounded-full border border-accent/30 bg-accent-soft text-[11px] font-semibold text-accent">
      {initials(user)}
    </span>
  )
}

export function UserMenu() {
  const { user, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${displayName(user)}`}
        className="rounded-full focus-visible:outline-offset-2"
      >
        <Avatar user={user} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute top-full right-0 z-40 mt-2 w-64 rounded-lg border border-line-strong bg-elevated p-1 shadow-panel"
        >
          <div className="flex items-center gap-2.5 border-b border-line px-2.5 py-2.5">
            <Avatar user={user} />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-fg">{displayName(user)}</p>
              {user.email && <p className="truncate text-xs text-fg-subtle">{user.email}</p>}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              void signOut()
            }}
            className="mt-1 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-fg-muted hover:bg-hover hover:text-fg"
          >
            <LogOut className="size-4" aria-hidden />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
