import { LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/application/auth-context'

/**
 * Keeps signed-out visitors out of the workspace UI. This is a usability guard only:
 * the backend rejects every unauthenticated API call on its own.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const location = useLocation()

  if (auth.status === 'loading') {
    return (
      <div role="status" aria-label="Checking session" className="grid h-full place-items-center">
        <LoaderCircle className="size-5 animate-spin text-fg-subtle" aria-hidden />
      </div>
    )
  }
  if (auth.status === 'signed_out') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return <>{children}</>
}
