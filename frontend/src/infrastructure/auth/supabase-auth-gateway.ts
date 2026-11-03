import { createClient, type AuthError, type Session } from '@supabase/supabase-js'
import { AppError } from '@/application/errors'
import type { AuthGateway, AuthSession } from '@/application/ports'

/**
 * Supabase Auth adapter, used for sign-in only. Data never goes through Supabase's
 * Data API: the browser talks to the AgentForge backend, which verifies the token.
 */
export function toAuthSession(session: Session | null): AuthSession | null {
  if (!session) return null
  const metadata = (session.user.user_metadata ?? {}) as Record<string, unknown>
  const text = (value: unknown) => (typeof value === 'string' && value ? value : null)
  return {
    accessToken: session.access_token,
    user: {
      id: session.user.id,
      email: session.user.email ?? null,
      name: text(metadata.full_name) ?? text(metadata.name),
      avatarUrl: text(metadata.avatar_url) ?? text(metadata.picture),
    },
  }
}

/** Translate Supabase Auth error codes into messages a person can act on. */
export function toFriendlyAuthError(error: Pick<AuthError, 'message' | 'code'>): AppError {
  switch (error.code) {
    case 'invalid_credentials':
      return new AppError('unauthorized', 'Incorrect email or password.')
    case 'email_not_confirmed':
      return new AppError('unauthorized', 'Please confirm your email first. Check your inbox for the link.')
    case 'over_email_send_rate_limit':
    case 'over_request_rate_limit':
      return new AppError('unknown', 'Too many attempts. Please wait a few minutes and try again.')
    case 'weak_password':
      return new AppError('validation', 'That password is too weak. Use a longer, less common one.')
    case 'same_password':
      return new AppError('validation', 'Choose a password different from your current one.')
    case 'email_address_invalid':
      return new AppError('validation', 'That email address cannot be used.')
    case 'signup_disabled':
      return new AppError('unknown', 'New sign-ups are currently disabled.')
    default:
      return new AppError('unknown', error.message || 'Authentication failed')
  }
}

export function createSupabaseAuthGateway(url: string, publishableKey: string): AuthGateway {
  const client = createClient(url, publishableKey, {
    auth: {
      flowType: 'pkce', // authorization code + PKCE; no tokens in the redirect URL
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  })

  return {
    configured: true,
    async getSession() {
      // Returns the stored session, refreshing it first if the access token has expired.
      const { data, error } = await client.auth.getSession()
      if (error) throw new AppError('unauthorized', error.message)
      return toAuthSession(data.session)
    },
    onSessionChange(listener) {
      // Keep the callback synchronous: supabase-js holds a lock while it runs.
      const { data } = client.auth.onAuthStateChange((_event, session) => listener(toAuthSession(session)))
      return () => data.subscription.unsubscribe()
    },
    async signInWithGoogle(redirectTo) {
      const { error } = await client.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo, queryParams: { prompt: 'select_account' } },
      })
      if (error) throw toFriendlyAuthError(error)
    },
    async signInWithPassword(email, password) {
      const { error } = await client.auth.signInWithPassword({ email, password })
      if (error) throw toFriendlyAuthError(error)
    },
    async signUpWithPassword(email, password, redirectTo) {
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: redirectTo },
      })
      if (error) throw toFriendlyAuthError(error)
      // With email confirmation on, no session is issued until the link is clicked.
      // Supabase deliberately returns the same response for already-registered emails.
      return { needsConfirmation: !data.session }
    },
    async sendPasswordReset(email, redirectTo) {
      const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo })
      // Rate limits are worth surfacing; anything else is hidden so responses don't
      // reveal whether an account exists.
      if (error && (error.code === 'over_email_send_rate_limit' || error.code === 'over_request_rate_limit'))
        throw toFriendlyAuthError(error)
    },
    async updatePassword(password) {
      const { error } = await client.auth.updateUser({ password })
      if (error) throw toFriendlyAuthError(error)
    },
    async signOut() {
      await client.auth.signOut()
    },
  }
}

async function notConfigured(): Promise<never> {
  throw new AppError(
    'unknown',
    'Sign-in is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.',
  )
}

/** Used when VITE_SUPABASE_* are missing: the app renders, but nobody can sign in. */
export function createUnconfiguredAuthGateway(): AuthGateway {
  return {
    configured: false,
    async getSession() {
      return null
    },
    onSessionChange() {
      return () => {}
    },
    signInWithGoogle: notConfigured,
    signInWithPassword: notConfigured,
    signUpWithPassword: notConfigured,
    sendPasswordReset: notConfigured,
    updatePassword: notConfigured,
    async signOut() {},
  }
}
