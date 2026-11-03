import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { User } from '@/domain/user'
import { useGateways } from './gateways-context'
import type { AuthSession } from './ports'

type AuthStatus = 'loading' | 'signed_out' | 'signed_in'

interface AuthContextValue {
  status: AuthStatus
  user: User | null
  /** False when no identity provider is configured for this build. */
  configured: boolean
  signInWithGoogle(redirectTo: string): Promise<void>
  signInWithPassword(email: string, password: string): Promise<void>
  signUpWithPassword(email: string, password: string, redirectTo: string): Promise<{ needsConfirmation: boolean }>
  sendPasswordReset(email: string, redirectTo: string): Promise<void>
  updatePassword(password: string): Promise<void>
  signOut(): Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { auth } = useGateways()
  const queryClient = useQueryClient()
  const [session, setSession] = useState<AuthSession | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    let active = true
    const apply = (next: AuthSession | null) => {
      if (!active) return
      // Never let one user's cached data render for another (or for a signed-out viewer).
      if (!next) queryClient.clear()
      setSession(next)
      setStatus(next ? 'signed_in' : 'signed_out')
    }
    auth.getSession().then(apply, () => apply(null))
    const unsubscribe = auth.onSessionChange(apply)
    return () => {
      active = false
      unsubscribe()
    }
  }, [auth, queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      configured: auth.configured,
      signInWithGoogle: (redirectTo) => auth.signInWithGoogle(redirectTo),
      signInWithPassword: (email, password) => auth.signInWithPassword(email.trim(), password),
      signUpWithPassword: (email, password, redirectTo) =>
        auth.signUpWithPassword(email.trim(), password, redirectTo),
      sendPasswordReset: (email, redirectTo) => auth.sendPasswordReset(email.trim(), redirectTo),
      updatePassword: (password) => auth.updatePassword(password),
      signOut: () => auth.signOut(),
    }),
    [auth, session, status],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react/only-export-components -- hook co-located with its provider
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
