import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppError } from '@/application/errors'
import { passFraction, taskRows } from '@/domain/evaluation'
import { createFakeGateways, makeBenchmark, makeEvaluationResult } from '@/test/fakes'
import { renderApp } from '@/test/render'

describe('evaluation domain rules', () => {
  it('distinguishes "did not run" from "ran and nothing passed"', () => {
    expect(passFraction({ executed: false, passed: 0, total: 0, errors: 0 })).toBeNull()
    expect(passFraction({ executed: true, passed: 0, total: 0, errors: 1 })).toBe(0)
    expect(passFraction({ executed: true, passed: 3, total: 4, errors: 0 })).toBe(0.75)
  })

  it('groups results into one row per task in result order', () => {
    const rows = taskRows([
      makeEvaluationResult({ taskId: 'b' }),
      makeEvaluationResult({ taskId: 'a' }),
      makeEvaluationResult({ taskId: 'b', system: 'single_agent' }),
    ])
    expect(rows.map((r) => r.taskId)).toEqual(['b', 'a'])
    expect(Object.keys(rows[0].bySystem)).toEqual(['multi_agent', 'single_agent'])
  })
})

describe('Evaluations page', () => {
  it('is reachable from the sidebar', async () => {
    const user = userEvent.setup()
    renderApp('/')
    await user.click(await screen.findByRole('link', { name: 'Evaluations' }))
    expect(await screen.findByRole('heading', { name: 'Evaluations' })).toBeInTheDocument()
  })

  it('explains how to produce results when none exist', async () => {
    renderApp('/evaluations')
    expect(await screen.findByText('No benchmark has been run yet')).toBeInTheDocument()
    expect(screen.getByText(/run_benchmark\.py/)).toBeInTheDocument()
  })

  it('compares both systems and never shows undefined rates as zero', async () => {
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([makeBenchmark()])
    renderApp('/evaluations', gateways)

    const summary = await screen.findByRole('table', { name: 'Benchmark summary per system' })
    const solved = within(summary).getByRole('row', { name: /Tasks solved/ })
    expect(within(solved).getByText('4/6 (66.7%)')).toBeInTheDocument()
    expect(within(solved).getByText('2/6 (33.3%)')).toBeInTheDocument()
    const ownSuite = within(summary).getByRole('row', { name: /Own test suite green/ })
    expect(within(ownSuite).getByText('—')).toBeInTheDocument()
    const cost = within(summary).getByRole('row', { name: /Est\. cost/ })
    expect(within(cost).getAllByText('—')).toHaveLength(2)
    expect(screen.queryByText(/scripted demo model/)).not.toBeInTheDocument()
  })

  it('lists every result with crashes explained', async () => {
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([makeBenchmark()])
    renderApp('/evaluations', gateways)

    const table = await screen.findByRole('table', { name: 'Every task and system result' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('14/14')).toBeInTheDocument()
    expect(within(rows[0]).getByText('solved')).toBeInTheDocument()
    expect(within(rows[1]).getByText('0/0')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Crashed: model returned invalid JSON')).toBeInTheDocument()
    expect(within(rows[1]).queryByText('solved')).not.toBeInTheDocument()
  })

  it('describes every bar for assistive technology and on hover', async () => {
    const user = userEvent.setup()
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([makeBenchmark()])
    renderApp('/evaluations', gateways)

    const bar = await screen.findByRole('img', { name: 'Multi-agent workflow: 14/14 reference tests passed, solved' })
    expect(screen.getByRole('img', { name: 'Single-agent baseline: 0/0 reference tests passed' })).toBeInTheDocument()
    await user.hover(bar)
    expect(screen.getByRole('tooltip')).toHaveTextContent('14/14 reference tests passed')
    await user.unhover(bar)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('shows "not run" when a reference suite never executed', async () => {
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([
      makeBenchmark({ results: [makeEvaluationResult({ solved: false, referenceTests: { executed: false, passed: 0, total: 0, errors: 0 } })] }),
    ])
    renderApp('/evaluations', gateways)
    expect(await screen.findByRole('img', { name: 'Multi-agent workflow: reference tests did not run' })).toBeInTheDocument()
  })

  it('warns when results came from the scripted demo model', async () => {
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([makeBenchmark({ demoModel: true })])
    renderApp('/evaluations', gateways)
    expect(await screen.findByRole('alert')).toHaveTextContent('scripted demo model, which is not AI')
  })

  it('switches between recent benchmarks', async () => {
    const user = userEvent.setup()
    const gateways = createFakeGateways()
    gateways.evaluations.recent.mockResolvedValue([
      makeBenchmark({ id: 'bench-new' }),
      makeBenchmark({ id: 'bench-old', modelNames: ['google:gemini-2.5-flash'] }),
    ])
    renderApp('/evaluations', gateways)
    expect(await screen.findByText('bench-new', { selector: 'span' })).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Benchmark' }), 'bench-old')
    expect(screen.getByText('google:gemini-2.5-flash')).toBeInTheDocument()
  })

  it('surfaces a failed request with a retry action', async () => {
    const user = userEvent.setup()
    const gateways = createFakeGateways()
    gateways.evaluations.recent
      .mockRejectedValueOnce(new AppError('network', 'Cannot reach the AgentForge API.'))
      .mockResolvedValueOnce([makeBenchmark()])
    renderApp('/evaluations', gateways)
    expect(await screen.findByText('Could not load benchmark results')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('table', { name: 'Benchmark summary per system' })).toBeInTheDocument()
  })
})
