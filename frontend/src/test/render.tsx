import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import type { Gateways } from '@/application/ports'
import { AppProviders } from '@/app/AppProviders'
import { routes } from '@/app/routes'
import { createFakeGateways } from './fakes'

/** Renders the real route tree at `path` with injected (fake) gateways. */
export function renderApp<G extends Gateways>(path: string, gateways: G = createFakeGateways() as unknown as G) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const result = render(
    <AppProviders gateways={gateways} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { ...result, router, gateways }
}
