import { LoaderCircle, MailCheck, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/application/auth-context'
import {
  PASSWORD_MIN_LENGTH,
  safeRedirectPath,
  validateCredentials,
  type CredentialErrors,
} from '@/domain/user'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/Field'

type Mode = 'sign_in' | 'sign_up' | 'reset'

const TITLES: Record<Mode, string> = {
  sign_in: 'Sign in to AgentForge',
  sign_up: 'Create your AgentForge account',
  reset: 'Reset your password',
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-[18px]" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  )
}

function LinkButton({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <button type="button" onClick={onClick} className="font-medium text-accent hover:underline">
      {children}
    </button>
  )
}

export function LoginPage() {
  const auth = useAuth()
  const [params] = useSearchParams()
  const [mode, setMode] = useState<Mode>('sign_in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<CredentialErrors>({})
  const [busy, setBusy] = useState<'google' | 'email' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const next = safeRedirectPath(params.get('next'))
  // Supabase reports OAuth/link failures (cancelled, expired link) on the redirect URL.
  const providerError = params.get('error_description')

  if (auth.status === 'signed_in') return <Navigate to={next} replace />

  const returnUrl = `${window.location.origin}/login?next=${encodeURIComponent(next)}`

  const switchMode = (target: Mode) => {
    setMode(target)
    setError(null)
    setNotice(null)
    setFieldErrors({})
  }

  const google = async () => {
    setError(null)
    setBusy('google')
    try {
      await auth.signInWithGoogle(returnUrl) // the browser navigates away on success
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start sign-in')
      setBusy(null)
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setNotice(null)
    const errors = validateCredentials(email, mode === 'reset' ? null : password, mode === 'sign_up' ? 'sign_up' : 'sign_in')
    setFieldErrors(errors)
    if (Object.keys(errors).length) return

    setBusy('email')
    try {
      if (mode === 'sign_in') {
        await auth.signInWithPassword(email, password) // session change redirects
      } else if (mode === 'sign_up') {
        const { needsConfirmation } = await auth.signUpWithPassword(email, password, returnUrl)
        if (needsConfirmation) {
          setNotice(`We sent a confirmation link to ${email.trim()}. Open it in this browser to finish signing up.`)
          setPassword('')
        }
      } else {
        await auth.sendPasswordReset(email, `${window.location.origin}/reset-password`)
        setNotice(`If an account exists for ${email.trim()}, a password reset link is on its way.`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  const message = error ?? providerError

  return (
    <main className="grid min-h-full place-items-center bg-canvas px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <img src="/favicon.svg" alt="" className="mb-4 size-11" />
          <h1 className="text-lg font-semibold tracking-tight text-fg">{TITLES[mode]}</h1>
          <p className="mt-1 text-[13px] text-fg-muted">Multi-agent software engineering workspace</p>
        </div>

        <div className="rounded-xl border border-line bg-panel p-5 shadow-panel">
          {auth.status === 'loading' ? (
            <p role="status" className="flex items-center justify-center gap-2 py-2 text-[13px] text-fg-muted">
              <LoaderCircle className="size-4 animate-spin" aria-hidden />
              Checking your session…
            </p>
          ) : (
            <>
              {mode !== 'reset' && (
                <>
                  <button
                    type="button"
                    onClick={google}
                    disabled={busy !== null || !auth.configured}
                    className="flex h-10 w-full items-center justify-center gap-2.5 rounded-md border border-line-strong bg-white text-sm font-medium text-[#1f1f1f] transition-colors hover:bg-[#f2f2f2] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busy === 'google' ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <GoogleMark />}
                    Continue with Google
                  </button>
                  <div className="my-4 flex items-center gap-3 text-xs text-fg-subtle" aria-hidden>
                    <span className="h-px flex-1 bg-line" />
                    or with email
                    <span className="h-px flex-1 bg-line" />
                  </div>
                </>
              )}

              <form onSubmit={submit} noValidate className="space-y-4">
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  error={fieldErrors.email}
                  placeholder="you@example.com"
                />
                {mode !== 'reset' && (
                  <div className="space-y-1.5">
                    <TextField
                      label="Password"
                      type="password"
                      autoComplete={mode === 'sign_up' ? 'new-password' : 'current-password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      error={fieldErrors.password}
                      hint={mode === 'sign_up' ? `At least ${PASSWORD_MIN_LENGTH} characters` : undefined}
                    />
                    {mode === 'sign_in' && (
                      <p className="text-right text-xs">
                        <LinkButton onClick={() => switchMode('reset')}>Forgot password?</LinkButton>
                      </p>
                    )}
                  </div>
                )}
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  loading={busy === 'email'}
                  disabled={busy !== null || !auth.configured}
                >
                  {mode === 'sign_in' ? 'Sign in' : mode === 'sign_up' ? 'Create account' : 'Send reset link'}
                </Button>
              </form>
            </>
          )}

          {notice && (
            <p role="status" className="mt-4 flex gap-2 rounded-md border border-success/25 bg-success-soft p-3 text-xs text-fg">
              <MailCheck className="size-4 shrink-0 text-success" aria-hidden />
              {notice}
            </p>
          )}
          {!auth.configured && (
            <p className="mt-4 flex gap-2 text-xs text-warning">
              <TriangleAlert className="size-4 shrink-0" aria-hidden />
              Sign-in is not configured for this build. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.
            </p>
          )}
          {message && (
            <p role="alert" className="mt-4 text-xs text-danger">
              {message}
            </p>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-fg-muted">
          {mode === 'sign_in' && (
            <>
              New to AgentForge? <LinkButton onClick={() => switchMode('sign_up')}>Create an account</LinkButton>
            </>
          )}
          {mode === 'sign_up' && (
            <>
              Already have an account? <LinkButton onClick={() => switchMode('sign_in')}>Sign in</LinkButton>
            </>
          )}
          {mode === 'reset' && <LinkButton onClick={() => switchMode('sign_in')}>Back to sign in</LinkButton>}
        </p>
      </div>
    </main>
  )
}
