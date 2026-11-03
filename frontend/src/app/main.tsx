import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import type { Gateways } from '@/application/ports'
import {
  createSupabaseAuthGateway,
  createUnconfiguredAuthGateway,
} from '@/infrastructure/auth/supabase-auth-gateway'
import {
  createDashboardGateway,
  createEvaluationGateway,
  createProjectGateway,
  createSystemGateway,
} from '@/infrastructure/gateways/http-gateways'
import { createKnowledgeGateway } from '@/infrastructure/gateways/http-knowledge-gateway'
import { createRunGateway } from '@/infrastructure/gateways/http-run-gateway'
import { createHttpClient } from '@/infrastructure/http/http-client'
import '@/styles/index.css'
import { AppProviders } from './AppProviders'
import { createQueryClient } from './query-client'
import { routes } from './routes'

// Composition root: the only place that chooses concrete infrastructure.
const env = import.meta.env
const auth =
  env.VITE_SUPABASE_URL && env.VITE_SUPABASE_PUBLISHABLE_KEY
    ? createSupabaseAuthGateway(env.VITE_SUPABASE_URL, env.VITE_SUPABASE_PUBLISHABLE_KEY)
    : createUnconfiguredAuthGateway()

const http = createHttpClient(env.VITE_API_BASE_URL ?? '/api', {
  getAccessToken: async () => (await auth.getSession())?.accessToken ?? null,
  // The backend rejected our token (revoked, expired beyond refresh, wrong project):
  // drop the local session so the user is sent back to sign-in.
  onUnauthorized: () => void auth.signOut(),
})

const gateways: Gateways = {
  auth,
  projects: createProjectGateway(http),
  runs: createRunGateway(http),
  dashboard: createDashboardGateway(http),
  system: createSystemGateway(http),
  evaluations: createEvaluationGateway(http),
  knowledge: createKnowledgeGateway(http),
}
const router = createBrowserRouter(routes)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders gateways={gateways} queryClient={createQueryClient()}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
