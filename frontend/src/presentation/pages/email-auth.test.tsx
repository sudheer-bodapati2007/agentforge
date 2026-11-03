import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppError } from '@/application/errors'
import { toFriendlyAuthError } from '@/infrastructure/auth/supabase-auth-gateway'
import { createFakeGateways, makeSession } from '@/test/fakes'
import { renderApp } from '@/test/render'

const signedOut = () => createFakeGateways(null)

describe('email and password sign-in', () => {
  it('validates before calling the provider', async () => {
    const gateways = signedOut()
    renderApp('/login', gateways)
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(gateways.auth.signInWithPassword).not.toHaveBeenCalled()
  })

  it('signs in and continues to the intended page', async () => {
    const gateways = signedOut()
    const { router } = renderApp('/login?next=%2Fprojects', gateways)
    await userEvent.type(await screen.findByLabelText('Email'), ' ada@example.com ')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(gateways.auth.signInWithPassword).toHaveBeenCalledWith('ada@example.com', 'correct horse')
    await waitFor(() => expect(router.state.location.pathname).toBe('/projects'))
  })

  it('shows a friendly error for wrong credentials', async () => {
    const gateways = signedOut()
    gateways.auth.signInWithPassword.mockRejectedValueOnce(
      toFriendlyAuthError({ code: 'invalid_credentials', message: 'Invalid login credentials' }),
    )
    renderApp('/login', gateways)
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
  })

  it('creates an account and asks the user to confirm their email', async () => {
    const gateways = signedOut()
    renderApp('/login', gateways)
    await userEvent.click(await screen.findByRole('button', { name: 'Create an account' }))
    expect(screen.getByRole('heading', { name: 'Create your AgentForge account' })).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Use at least 8 characters')).toBeInTheDocument()
    expect(gateways.auth.signUpWithPassword).not.toHaveBeenCalled()

    await userEvent.type(screen.getByLabelText('Password'), '-but-longer')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(gateways.auth.signUpWithPassword).toHaveBeenCalledWith(
      'new@example.com',
      'short-but-longer',
      `${window.location.origin}/login?next=%2F`,
    )
    expect(await screen.findByText(/We sent a confirmation link to new@example.com/)).toBeInTheDocument()
  })

  it('sends a reset link without revealing whether the account exists', async () => {
    const gateways = signedOut()
    renderApp('/login', gateways)
    await userEvent.click(await screen.findByRole('button', { name: 'Forgot password?' }))
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'who@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(gateways.auth.sendPasswordReset).toHaveBeenCalledWith(
      'who@example.com',
      `${window.location.origin}/reset-password`,
    )
    expect(await screen.findByText(/If an account exists for who@example.com/)).toBeInTheDocument()
  })
})

describe('reset password page', () => {
  it('rejects an invalid or expired link', async () => {
    renderApp('/reset-password', signedOut())
    expect(await screen.findByText('This reset link is invalid or has expired')).toBeInTheDocument()
  })

  it('sets a new password with the recovery session', async () => {
    const gateways = createFakeGateways(makeSession({ email: 'ada@example.com' }))
    const { router } = renderApp('/reset-password', gateways)
    await userEvent.type(await screen.findByLabelText('New password'), 'new-password-1')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'new-password-2')
    await userEvent.click(screen.getByRole('button', { name: 'Update password' }))
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText('Confirm new password'))
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'new-password-1')
    await userEvent.click(screen.getByRole('button', { name: 'Update password' }))
    expect(gateways.auth.updatePassword).toHaveBeenCalledWith('new-password-1')
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})

describe('toFriendlyAuthError', () => {
  it.each([
    ['email_not_confirmed', /confirm your email/],
    ['over_email_send_rate_limit', /Too many attempts/],
    ['weak_password', /too weak/],
    [undefined, /raw message/],
  ])('%s', (code, expected) => {
    const error = toFriendlyAuthError({ code, message: 'raw message' })
    expect(error).toBeInstanceOf(AppError)
    expect(error.message).toMatch(expected)
  })
})
