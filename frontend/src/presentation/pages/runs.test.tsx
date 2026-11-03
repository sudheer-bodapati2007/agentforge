import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { nodeStates, type AgentExecution } from '@/domain/run'
import { createSseParser } from '@/infrastructure/gateways/http-run-gateway'
import { AppError } from '@/application/errors'
import { createFakeGateways, makeApproval, makeRun, makeStatus } from '@/test/fakes'
import { renderApp } from '@/test/render'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.open = false
  }
})

const readyStatus = () =>
  makeStatus({
    workflowEngine: { state: 'ok', detail: null },
    llm: { state: 'ok', detail: null, provider: 'google', model: 'gemini', apiKeyPresent: true },
  })

function execution(node: string, status: AgentExecution['status'], attempt = 1): AgentExecution {
  return { id: `${node}-${attempt}`, node, agent: null, attempt, status, summary: null, error: null, inputTokens: 0, outputTokens: 0, startedAt: null, finishedAt: null }
}

describe('nodeStates', () => {
  it('reflects only confirmed backend records', () => {
    const states = nodeStates(makeRun({ status: 'running', requireApproval: false }), [
      execution('plan', 'completed'),
      execution('architect', 'running'),
    ])
    expect(states.plan).toBe('completed')
    expect(states.architect).toBe('running')
    expect(states.code).toBe('pending')
  })

  it('shows the latest attempt and the waiting approval', () => {
    const run = makeRun({ status: 'awaiting_approval', currentNode: 'plan_approval' })
    expect(nodeStates(run, [execution('plan', 'completed')]).plan_approval).toBe('waiting')
    const retested = nodeStates(makeRun({ status: 'running' }), [execution('run_tests', 'failed', 1), execution('run_tests', 'completed', 2)])
    expect(retested.run_tests).toBe('completed')
  })

  it('marks never-reached nodes as skipped once the run is over', () => {
    const states = nodeStates(makeRun({ status: 'completed', requireApproval: false }), [execution('plan', 'completed'), execution('code', 'completed')])
    expect(states.debug).toBe('skipped')
    expect(states.plan_approval).toBe('skipped')
  })
})

describe('SSE parser', () => {
  it('handles chunk boundaries, comments and multi-line data', () => {
    const messages: { id: string | null; event: string; data: string }[] = []
    const feed = createSseParser((m) => messages.push(m))
    feed('id: 1\nevent: node.started\nda')
    feed('ta: {"a":1}\n\n: keep-alive\n\n')
    feed('id: 2\r\nevent: end\r\ndata: x\r\ndata: y\r\n\r\n')
    expect(messages).toEqual([
      { id: '1', event: 'node.started', data: '{"a":1}' },
      { id: '2', event: 'end', data: 'x\ny' },
    ])
  })
})

describe('starting a run', () => {
  it('starts with the chosen approval policy and an idempotency key, then opens the run', async () => {
    const gateways = createFakeGateways()
    gateways.system.status.mockResolvedValue(readyStatus())
    const { router } = renderApp('/projects/p-1', gateways)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Run Project' })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: 'Run Project' }))
    const dialog = await screen.findByRole('dialog', { name: 'Run the agent workflow' })
    await userEvent.click(within(dialog).getByRole('checkbox'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Start run' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/runs/r-new'))
    const [projectId, options, key] = gateways.runs.start.mock.calls[0]
    expect(projectId).toBe('p-1')
    expect(options).toEqual({ requireApproval: false })
    expect(key.length).toBeGreaterThanOrEqual(8)
  })

  it("shows the backend's reason when a run is rejected", async () => {
    const gateways = createFakeGateways()
    gateways.system.status.mockResolvedValue(readyStatus())
    gateways.runs.start.mockRejectedValue(
      new AppError('validation', 'Request validation failed', {
        status: 422,
        fieldErrors: [{ field: 'language', message: 'only Python projects can be executed' }],
      }),
    )
    renderApp('/projects/p-1', gateways)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Run Project' })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: 'Run Project' }))
    const dialog = await screen.findByRole('dialog', { name: 'Run the agent workflow' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Start run' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Request validation failed: only Python projects can be executed',
    )
  })
})

describe('run page', () => {
  it('shows a pending approval and submits the decision', async () => {
    const gateways = createFakeGateways()
    gateways.runs.get.mockResolvedValue(makeRun({ id: 'r-1', status: 'awaiting_approval', currentNode: 'plan_approval' }))
    gateways.runs.approvals.mockResolvedValue([makeApproval()])
    renderApp('/runs/r-1', gateways)

    expect(await screen.findByText('Approve the plan before code is generated')).toBeInTheDocument()
    expect(screen.getByText('app/main.py')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Comment/), 'Add pagination')
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    expect(gateways.runs.decide).toHaveBeenCalledWith('r-1', 'a-1', false, 'Add pagination')
    expect(screen.getByLabelText('Plan approval: awaiting approval')).toBeInTheDocument()
  })

  it('asks for approval before applying fixes for blocking findings', async () => {
    const gateways = createFakeGateways()
    gateways.runs.get.mockResolvedValue(makeRun({ status: 'awaiting_approval', currentNode: 'correction_approval' }))
    gateways.runs.approvals.mockResolvedValue([
      makeApproval({
        id: 'a-2',
        kind: 'corrections',
        reason: 'Apply fixes for 1 blocking review finding(s), then re-run the tests.',
        affectedResources: ['app/shell.py'],
        securityNotes: 'S602: subprocess call with shell=True',
        details: {},
      }),
    ])
    renderApp('/runs/r-1', gateways)
    expect(await screen.findByText('Approve fixes for blocking review findings')).toBeInTheDocument()
    expect(screen.getByText(/S602/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(gateways.runs.decide).toHaveBeenCalledWith('r-1', 'a-2', true, '')
    expect(screen.getByLabelText('Fix approval: awaiting approval')).toBeInTheDocument()
  })

  it('labels the demo model honestly and shows real test counts', async () => {
    const gateways = createFakeGateways()
    gateways.runs.get.mockResolvedValue(makeRun({ demoModel: true, llmModel: 'scripted-demo' }))
    gateways.runs.tests.mockResolvedValue([
      { attempt: 1, command: 'pytest', executed: true, exitCode: 1, total: 6, passed: 5, failed: 1, errors: 0, skipped: 0, durationMs: 900, outputExcerpt: 'E assert', failures: [{ name: 'tests::test_filter', message: 'assert 1 == 2' }], unavailableReason: null },
      { attempt: 2, command: 'pytest', executed: true, exitCode: 0, total: 6, passed: 6, failed: 0, errors: 0, skipped: 0, durationMs: 800, outputExcerpt: '', failures: [], unavailableReason: null },
    ])
    renderApp('/runs/r-1', gateways)
    expect(await screen.findByText('Demo model (not AI)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: /Tests/ }))
    expect(await screen.findByText('Verified by test runner')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Run 1: 5/6 passed, 1 failed, 0 errors' }))
    expect(screen.getByText('tests::test_filter')).toBeInTheDocument()
  })

  it('offers resume for failed runs', async () => {
    const gateways = createFakeGateways()
    gateways.runs.get.mockResolvedValue(makeRun({ status: 'failed', error: 'The coder model was overloaded' }))
    renderApp('/runs/r-1', gateways)
    expect(await screen.findByText('The coder model was overloaded')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Resume from checkpoint' }))
    expect(gateways.runs.resume).toHaveBeenCalledWith('r-1')
  })

  it('lists all workflow runs', async () => {
    const gateways = createFakeGateways()
    gateways.runs.list.mockResolvedValue({ items: [makeRun({ projectName: 'Inventory API' })], total: 1 })
    renderApp('/workflows', gateways)
    expect(await screen.findByText('Inventory API')).toBeInTheDocument()
  })
})
