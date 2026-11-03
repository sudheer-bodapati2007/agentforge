import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { safeRedirectPath } from '@/domain/user'
import { createFakeGateways } from '@/test/fakes'
import { renderApp } from '@/test/render'

describe('authentication', () => {
  it('sends signed-out visitors to the login page, remembering where they were going', async () => {
    const { router } = renderApp('/projects/new', createFakeGateways(null))
    expect(await screen.findByRole('button', { name: 'Continue with Google' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe('?next=%2Fprojects%2Fnew')
  })

  it('does not call the API while signed out', async () => {
    const gateways = createFakeGateways(null)
    renderApp('/', gateways)
    await screen.findByRole('button', { name: 'Continue with Google' })
    expect(gateways.dashboard.metrics).not.toHaveBeenCalled()
    expect(gateways.system.status).not.toHaveBeenCalled()
  })

  it('starts Google sign-in with a redirect back to the intended page', async () => {
    const gateways = createFakeGateways(null)
    renderApp('/login?next=%2Fsettings', gateways)
    await userEvent.click(await screen.findByRole('button', { name: 'Continue with Google' }))
    expect(gateways.auth.signInWithGoogle).toHaveBeenCalledWith(
      `${window.location.origin}/login?next=%2Fsettings`,
    )
  })

  it('shows provider errors returned on the redirect', async () => {
    renderApp('/login?error=access_denied&error_description=User%20cancelled', createFakeGateways(null))
    expect(await screen.findByRole('alert')).toHaveTextContent('User cancelled')
  })

  it('sends signed-in users from /login to their destination', async () => {
    const { router } = renderApp('/login?next=%2Fsettings')
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings'))
  })

  it('ignores off-site redirect targets', async () => {
    const { router } = renderApp('/login?next=%2F%2Fevil.example')
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('signs out from the user menu and returns to login', async () => {
    const gateways = createFakeGateways()
    const { router } = renderApp('/', gateways)
    await userEvent.click(await screen.findByRole('button', { name: /Account menu for Ada Lovelace/ }))
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))

    expect(gateways.auth.signOut).toHaveBeenCalledOnce()
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('explains when sign-in is not configured', async () => {
    const gateways = createFakeGateways(null)
    const unconfigured = { ...gateways, auth: { ...gateways.auth, configured: false } }
    renderApp('/login', unconfigured)
    expect(await screen.findByRole('button', { name: 'Continue with Google' })).toBeDisabled()
    expect(screen.getByText(/Sign-in is not configured/)).toBeInTheDocument()
  })
})

describe('safeRedirectPath', () => {
  it.each([
    [null, '/'],
    ['/projects/1', '/projects/1'],
    ['//evil.example', '/'],
    ['/\\evil.example', '/'],
    ['https://evil.example', '/'],
    ['/login?next=/x', '/'],
  ])('%s -> %s', (input, expected) => {
    expect(safeRedirectPath(input)).toBe(expected)
  })
})
