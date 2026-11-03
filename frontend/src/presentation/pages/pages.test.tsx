import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { AppError } from '@/application/errors'
import { createFakeGateways, emptyMetrics, makeProject, makeStatus } from '@/test/fakes'
import { renderApp } from '@/test/render'

beforeAll(() => {
  // jsdom does not implement <dialog> modality.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.open = false
  }
})

describe('Dashboard', () => {
  it('shows a loading state, then onboarding for an empty database', async () => {
    const gateways = createFakeGateways()
    let release!: () => void
    gateways.dashboard.metrics.mockImplementation(
      () => new Promise((resolve) => (release = () => resolve(emptyMetrics()))),
    )
    renderApp('/', gateways)
    expect(screen.getByRole('status', { name: 'Checking session' })).toBeInTheDocument()
    expect(await screen.findByRole('status', { name: 'Loading metrics' })).toBeInTheDocument()
    // The skeleton renders before the query function runs; wait for the request itself.
    await waitFor(() => expect(gateways.dashboard.metrics).toHaveBeenCalled())
    release()
    expect(await screen.findByText('Create your first project')).toBeInTheDocument()
    expect(screen.queryByText('Test pass rate')).not.toBeInTheDocument()
  })

  it('renders real metrics and shows null rates as no-data', async () => {
    const gateways = createFakeGateways()
    gateways.dashboard.metrics.mockResolvedValue(emptyMetrics({ totalProjects: 2, totalRuns: 0 }))
    renderApp('/', gateways)
    const card = (await screen.findByText('Test pass rate')).closest('div')!.parentElement!
    expect(within(card).getByText('—')).toBeInTheDocument()
    expect(within(card).getByText('No executed test suites')).toBeInTheDocument()
  })

  it('surfaces a failed request with a retry action', async () => {
    const gateways = createFakeGateways()
    gateways.dashboard.metrics
      .mockRejectedValueOnce(new AppError('network', 'Cannot reach the AgentForge API.'))
      .mockResolvedValue(emptyMetrics())
    renderApp('/', gateways)
    expect(await screen.findByText('Could not load dashboard metrics')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'Retry' })[0])
    expect(await screen.findByText('Create your first project')).toBeInTheDocument()
  })
})

describe('New project', () => {
  it('blocks submission until the draft is valid', async () => {
    const { gateways } = renderApp('/projects/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Create project' }))
    expect(screen.getByText('Project name is required')).toBeInTheDocument()
    expect(gateways.projects.create).not.toHaveBeenCalled()
  })

  it('creates a project and opens its workspace', async () => {
    const { gateways, router } = renderApp('/projects/new')
    await userEvent.type(await screen.findByLabelText('Project name'), 'Inventory API')
    await userEvent.type(screen.getByLabelText('Software requirements'), 'Track stock levels across warehouses with REST endpoints.')
    await userEvent.click(screen.getByRole('button', { name: 'Create project' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/new-1'))
    expect(gateways.projects.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Inventory API', language: 'python' }))
  })

  it('shows server-side field errors inline', async () => {
    const gateways = createFakeGateways()
    gateways.projects.create.mockRejectedValue(
      new AppError('validation', 'Request validation failed', {
        status: 422,
        fieldErrors: [{ field: 'name', message: 'Name rejected by server' }],
      }),
    )
    renderApp('/projects/new', gateways)
    await userEvent.type(await screen.findByLabelText('Project name'), 'X')
    await userEvent.type(screen.getByLabelText('Software requirements'), 'r'.repeat(25))
    await userEvent.click(screen.getByRole('button', { name: 'Create project' }))
    expect(await screen.findByText('Name rejected by server')).toBeInTheDocument()
  })
})

describe('Project workspace', () => {
  it('disables Run Project with the reason the backend reports', async () => {
    renderApp('/projects/p-1')
    const run = await screen.findByRole('button', { name: 'Run Project' })
    expect(run).toBeDisabled()
    await waitFor(() => expect(run).toHaveAccessibleDescription('LangGraph workflow arrives in Phase 2'))
  })

  it('enables Run Project only when engine and LLM are ready', async () => {
    const gateways = createFakeGateways()
    gateways.system.status.mockResolvedValue(
      makeStatus({
        workflowEngine: { state: 'ok', detail: null },
        llm: { state: 'ok', detail: null, provider: 'p', model: 'm', apiKeyPresent: true },
      }),
    )
    renderApp('/projects/p-1', gateways)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Run Project' })).toBeEnabled())
  })

  it('deletes after confirmation and returns to the project list', async () => {
    const gateways = createFakeGateways()
    gateways.projects.get.mockResolvedValue(makeProject({ id: 'p-1', name: 'Doomed' }))
    const { router } = renderApp('/projects/p-1', gateways)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog', { name: 'Delete project?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete project' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects'))
    expect(gateways.projects.remove).toHaveBeenCalledWith('p-1')
  })

  it('shows a not-found state for unknown projects', async () => {
    const gateways = createFakeGateways()
    gateways.projects.get.mockRejectedValue(new AppError('not_found', "Project 'x' not found", { status: 404 }))
    renderApp('/projects/x', gateways)
    expect(await screen.findByText('Project not found')).toBeInTheDocument()
  })
})
