import type { RouteObject } from 'react-router-dom'
import { RequireAuth } from '@/presentation/components/RequireAuth'
import { AppShell } from '@/presentation/layouts/AppShell'
import { ProjectCrumb, type RouteHandle } from '@/presentation/layouts/TopBar'
import { ActivityPage } from '@/presentation/pages/ActivityPage'
import { DashboardPage } from '@/presentation/pages/DashboardPage'
import { EvaluationsPage } from '@/presentation/pages/EvaluationsPage'
import { HistoryPage } from '@/presentation/pages/HistoryPage'
import { KnowledgeBasePage } from '@/presentation/pages/KnowledgeBasePage'
import { LoginPage } from '@/presentation/pages/LoginPage'
import { NewProjectPage } from '@/presentation/pages/NewProjectPage'
import { NotFoundPage } from '@/presentation/pages/NotFoundPage'
import { ProjectsPage } from '@/presentation/pages/ProjectsPage'
import { ResetPasswordPage } from '@/presentation/pages/ResetPasswordPage'
import { RunPage } from '@/presentation/pages/RunPage'
import { RunsPage } from '@/presentation/pages/RunsPage'
import { ProjectWorkspacePage } from '@/presentation/pages/ProjectWorkspacePage'
import { SettingsPage } from '@/presentation/pages/SettingsPage'

const handle = (h: RouteHandle) => h

export const routes: RouteObject[] = [
  { path: 'login', element: <LoginPage /> },
  { path: 'reset-password', element: <ResetPasswordPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage />, handle: handle({ crumb: () => ({ label: 'Dashboard' }) }) },
      {
        path: 'projects',
        handle: handle({ crumb: () => ({ label: 'Projects', to: '/projects' }) }),
        children: [
          { index: true, element: <ProjectsPage /> },
          { path: 'new', element: <NewProjectPage />, handle: handle({ crumb: () => ({ label: 'New project' }) }) },
          {
            path: ':projectId',
            element: <ProjectWorkspacePage />,
            handle: handle({
              projectScoped: true,
              crumb: (params) => ({ label: <ProjectCrumb id={params.projectId ?? ''} /> }),
            }),
          },
        ],
      },
      {
        path: 'workflows',
        handle: handle({ crumb: () => ({ label: 'All workflows', to: '/workflows' }) }),
        element: <RunsPage />,
      },
      {
        path: 'runs/:runId',
        element: <RunPage />,
        handle: handle({ crumb: (params) => ({ label: `Run ${(params.runId ?? '').slice(0, 8)}` }) }),
      },
      { path: 'evaluations', element: <EvaluationsPage />, handle: handle({ crumb: () => ({ label: 'Evaluations' }) }) },
      { path: 'activity', element: <ActivityPage />, handle: handle({ crumb: () => ({ label: 'Agent Activity' }) }) },
      { path: 'knowledge', element: <KnowledgeBasePage />, handle: handle({ crumb: () => ({ label: 'Knowledge Base' }) }) },
      { path: 'history', element: <HistoryPage />, handle: handle({ crumb: () => ({ label: 'Execution History' }) }) },
      { path: 'settings', element: <SettingsPage />, handle: handle({ crumb: () => ({ label: 'Settings' }) }) },
      { path: '*', element: <NotFoundPage />, handle: handle({ crumb: () => ({ label: 'Not found' }) }) },
    ],
  },
]
