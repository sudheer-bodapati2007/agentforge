export interface User {
  id: string
  email: string | null
  name: string | null
  avatarUrl: string | null
}

export function displayName(user: User): string {
  return user.name ?? user.email ?? 'Signed-in user'
}

export function initials(user: User): string {
  const source = user.name ?? user.email ?? '?'
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2)).toUpperCase()
}

/** Client-side checks for fast feedback; Supabase Auth enforces its own policy too. */
export const PASSWORD_MIN_LENGTH = 8
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export interface CredentialErrors {
  email?: string
  password?: string
}

export function validateCredentials(
  email: string,
  password: string | null,
  mode: 'sign_in' | 'sign_up' = 'sign_in',
): CredentialErrors {
  const errors: CredentialErrors = {}
  if (!EMAIL_PATTERN.test(email.trim())) errors.email = 'Enter a valid email address'
  if (password !== null) {
    if (!password) errors.password = 'Enter your password'
    else if (mode === 'sign_up' && password.length < PASSWORD_MIN_LENGTH)
      errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters`
  }
  return errors
}

/**
 * Only same-origin relative paths are allowed as post-login destinations
 * (prevents open redirects such as `?next=//evil.example`).
 */
export function safeRedirectPath(next: string | null | undefined): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/'
  if (next.startsWith('/login')) return '/'
  return next
}
