import { KeyRound, LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/application/auth-context'
import { PASSWORD_MIN_LENGTH } from '@/domain/user'
import { Button, ButtonLink } from '../components/ui/Button'
import { TextField } from '../components/ui/Field'
import { EmptyState } from '../components/ui/States'
import { useToast } from '../components/ui/Toast'

/**
 * Target of the password-reset email. Supabase exchanges the link's code for a short-lived
 * recovery session; with that session the user may set a new password.
 */
export function ResetPasswordPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (auth.status === 'loading') {
    return (
      <p role="status" className="flex h-full items-center justify-center gap-2 text-[13px] text-fg-muted">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        Verifying your reset link…
      </p>
    )
  }

  if (auth.status === 'signed_out') {
    return (
      <EmptyState
        className="py-24"
        icon={<KeyRound className="size-5" />}
        title="This reset link is invalid or has expired"
        description="Request a new link from the sign-in page. Open it in the same browser you requested it from."
        action={<ButtonLink to="/login">Back to sign in</ButtonLink>}
      />
    )
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const next: typeof errors = {}
    if (password.length < PASSWORD_MIN_LENGTH) next.password = `Use at least ${PASSWORD_MIN_LENGTH} characters`
    if (confirm !== password) next.confirm = 'Passwords do not match'
    setErrors(next)
    if (Object.keys(next).length) return

    setBusy(true)
    setError(null)
    try {
      await auth.updatePassword(password)
      toast.success('Password updated')
      navigate('/', { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update password')
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-full place-items-center bg-canvas px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-lg font-semibold tracking-tight text-fg">Choose a new password</h1>
          {auth.user?.email && <p className="mt-1 text-[13px] text-fg-muted">for {auth.user.email}</p>}
        </div>
        <form onSubmit={submit} noValidate className="space-y-4 rounded-xl border border-line bg-panel p-5 shadow-panel">
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            hint={`At least ${PASSWORD_MIN_LENGTH} characters`}
            autoFocus
          />
          <TextField
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={errors.confirm}
          />
          {error && (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" className="w-full" loading={busy}>
            Update password
          </Button>
        </form>
      </div>
    </main>
  )
}
