import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { WORKFLOW_EDGES, WORKFLOW_NODES, executionsByNode, type AgentExecution, type ReviewFinding, type TestResult } from '@/domain/run'
import { createFakeGateways, makeRun } from '@/test/fakes'
import { renderApp } from '@/test/render'

function execution(node: string, attempt: number, overrides: Partial<AgentExecution> = {}): AgentExecution {
  return {
    id: `${node}-${attempt}`,
    node,
    agent: null,
    attempt,
    status: 'completed',
    summary: null,
    error: null,
    inputTokens: 0,
    outputTokens: 0,
    startedAt: new Date('2026-10-22T10:00:00Z'),
    finishedAt: new Date('2026-10-22T10:00:12Z'),
    ...overrides,
  }
}

function testRun(attempt: number, overrides: Partial<TestResult> = {}): TestResult {
  return {
    attempt,
    command: 'pytest',
    executed: true,
    exitCode: 0,
    total: 6,
    passed: 6,
    failed: 0,
    errors: 0,
    skipped: 0,
    durationMs: 1200,
    outputExcerpt: null,
    failures: [],
    unavailableReason: null,
    ...overrides,
  }
}

const finding = (overrides: Partial<ReviewFinding> = {}): ReviewFinding => ({
  id: 'f-1',
  cycle: 1,
  severity: 'high',
  category: 'security',
  title: 'S602: subprocess call with shell=True',
  description: 'shell=True runs a shell.',
  filePath: 'app/main.py',
  line: 3,
  suggestion: null,
  source: 'tool',
  toolName: 'ruff',
  ...overrides,
})

describe('workflow topology', () => {
  const ids = new Set<string>(WORKFLOW_NODES.map((n) => n.id))

  it('only connects known steps, and every step is reachable from the planner and ends at the report', () => {
    for (const e of WORKFLOW_EDGES) expect(ids.has(e.from) && ids.has(e.to)).toBe(true)
    const reachable = new Set(['plan'])
    for (let changed = true; changed; ) {
      changed = false
      for (const e of WORKFLOW_EDGES) if (reachable.has(e.from) && !reachable.has(e.to)) changed = reachable.add(e.to).size > 0
    }
    expect(reachable).toEqual(ids)
    expect(WORKFLOW_EDGES.filter((e) => e.from === 'report')).toEqual([])
  })

  it('has exactly the three bounded loops of the backend graph', () => {
    expect(WORKFLOW_EDGES.filter((e) => e.loop).map((e) => `${e.from}->${e.to}`).sort()).toEqual(
      ['correct->run_tests', 'debug->run_tests', 'plan_approval->plan'].sort(),
    )
  })

  it('groups executions by node in attempt order', () => {
    const grouped = executionsByNode([execution('run_tests', 2), execution('plan', 1), execution('run_tests', 1)])
    expect(grouped.get('run_tests')!.map((e) => e.attempt)).toEqual([1, 2])
  })
})

function runPage() {
  const gateways = createFakeGateways()
  gateways.runs.get.mockResolvedValue(makeRun({ id: 'r-1', status: 'completed', debugIterations: 1 }))
  gateways.runs.agents.mockResolvedValue([
    execution('plan', 1, { agent: 'planner', summary: '4 tasks', inputTokens: 900, outputTokens: 300 }),
    execution('run_tests', 1, { status: 'failed', error: 'tests failed' }),
    execution('debug', 1, { agent: 'debugger', summary: 'fixed import' }),
    execution('run_tests', 2, { summary: '6/6 passed' }),
  ])
  gateways.runs.artifacts.mockResolvedValue([
    { path: 'app/main.py', kind: 'source', sha256: 'a', sizeBytes: 90, createdBy: 'debugger', updatedAt: new Date() },
    { path: 'tests/test_main.py', kind: 'test', sha256: 'b', sizeBytes: 50, createdBy: 'tester', updatedAt: new Date() },
  ])
  gateways.runs.artifactContent.mockImplementation(async (_id: string, path: string) =>
    path === 'app/main.py' ? 'import subprocess\n\nsubprocess.run(cmd, shell=True)\n' : 'def test_x():\n    assert True\n',
  )
  gateways.runs.findings.mockResolvedValue([finding()])
  gateways.runs.tests.mockResolvedValue([
    testRun(1, { exitCode: 1, passed: 5, failed: 1, failures: [{ name: 'test_x', message: 'boom', file_path: 'tests/test_main.py', line: 2 }] }),
    testRun(2),
  ])
  return gateways
}

describe('run workspace', () => {
  it('selecting a step shows each of its attempts', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', runPage())
    const steps = await screen.findByRole('list', { name: 'Workflow progress' })
    await user.click(within(steps).getByRole('button', { name: 'Run tests: done, 2 attempts' }))
    const details = screen.getByRole('region', { name: 'Run tests details' })
    expect(within(details).getByText('attempt 1')).toBeInTheDocument()
    expect(within(details).getByText('tests failed')).toBeInTheDocument()
    expect(within(details).getByText('6/6 passed')).toBeInTheDocument()
    expect(within(details).getByText(/next: Code review \(pass\)/)).toBeInTheDocument()

    await user.click(within(steps).getByRole('button', { name: 'Planner: done' }))
    expect(within(screen.getByRole('region', { name: 'Planner details' })).getByText(/1,200 tok/)).toBeInTheDocument()
    await user.click(within(steps).getByRole('button', { name: 'Planner: done' }))
    expect(screen.queryByRole('region', { name: 'Planner details' })).not.toBeInTheDocument()
  })

  it('marks files with findings and revisions, and shows findings on their line', async () => {
    renderApp('/runs/r-1', runPage())
    const user = userEvent.setup()
    await user.click(await screen.findByRole('tab', { name: /Files/ }))
    const tree = await screen.findByRole('navigation', { name: 'Generated files' })
    expect(within(tree).getByRole('button', { name: 'app/main.py, 1 review finding(s), revised by the debugger' })).toBeInTheDocument()
    expect(await screen.findByRole('note')).toHaveTextContent('S602: subprocess call with shell=True')
  })

  it('keeps a finding that cites a line past the end of the file', async () => {
    const gateways = runPage()
    gateways.runs.findings.mockResolvedValue([finding({ line: 99, source: 'llm', title: 'Possible None dereference' })])
    const user = userEvent.setup()
    renderApp('/runs/r-1', gateways)
    await user.click(await screen.findByRole('tab', { name: /Files/ }))
    expect(await screen.findByRole('note')).toHaveTextContent(/Possible None dereference.*LLM reviewer; line 99 is past the end of the file/)
  })

  it('jumps from a review finding and from a failing test to the exact line', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', runPage())
    await user.click(await screen.findByRole('tab', { name: /Review/ }))
    await user.click(await screen.findByRole('button', { name: 'app/main.py:3' }))
    expect(await screen.findByText('app/main.py:3')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelector('[data-line="3"]')?.className).toContain('bg-warning-soft'))

    await user.click(screen.getByRole('tab', { name: /Tests/ }))
    await user.click(screen.getByRole('button', { name: 'Run 1: 5/6 passed, 1 failed, 0 errors' }))
    await user.click(screen.getByRole('button', { name: 'tests/test_main.py:2' }))
    expect(await screen.findByText('tests/test_main.py:2')).toBeInTheDocument()
  })

  it('moves between tabs with the keyboard, focus following the selection', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', runPage())
    const report = await screen.findByRole('tab', { name: /Report/ })
    report.focus()
    await user.keyboard('{ArrowRight}')
    const events = screen.getByRole('tab', { name: /Events/ })
    expect(events).toHaveAttribute('aria-selected', 'true')
    expect(events).toHaveFocus()
    await user.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: /Files/ })).toHaveFocus()
    await user.keyboard('{End}')
    expect(events).toHaveFocus()
  })

  it('charts every test run', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', runPage())
    await user.click(await screen.findByRole('tab', { name: /Tests/ }))
    expect(await screen.findByText('Tests per run')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run 1: 5/6 passed, 1 failed, 0 errors' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Run 2: 6/6 passed, 0 failed, 0 errors' })).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('database projects', () => {
  const schema = [
    {
      name: 'books',
      columns: [
        { name: 'id', type: 'INTEGER', nullable: false, default: "nextval('books_id_seq'::regclass)", primary_key: true },
        { name: 'author_id', type: 'INTEGER', nullable: false, default: null, primary_key: false },
      ],
      foreign_keys: [{ columns: ['author_id'], references: 'authors(id)' }],
      unique: [],
      indexes: [{ name: 'ix_books_author_id', columns: ['author_id'], unique: false }],
    },
  ]

  function databaseRun(database: TestResult['database'], overrides: Partial<TestResult> = {}) {
    const gateways = runPage()
    gateways.runs.tests.mockResolvedValue([testRun(1, { database, ...overrides })])
    gateways.runs.findings.mockResolvedValue([])
    return gateways
  }

  it('shows applied migrations and the schema read back from the database', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', databaseRun({ migrations: [{ file: '0001_initial.sql', ok: true, error: null }], schema, error: null }))
    await user.click(await screen.findByRole('tab', { name: /Database/ }))
    expect(screen.getByText('Migrations applied')).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Migrations' })).getByText('db/migrations/0001_initial.sql')).toBeInTheDocument()
    const table = screen.getByRole('region', { name: 'Table books' })
    expect(within(table).getByLabelText('primary key')).toBeInTheDocument()
    expect(within(table).getByText('authors(id)')).toBeInTheDocument()
    expect(within(table).getByText('ix_books_author_id')).toBeInTheDocument()
  })

  it('a failed migration is shown with its SQL error and the tests are not "verified"', async () => {
    const user = userEvent.setup()
    const failed = { migrations: [{ file: '0001_initial.sql', ok: false, error: 'relation "missing" does not exist' }], schema: [], error: null }
    renderApp('/runs/r-1', databaseRun(failed))
    await user.click(await screen.findByRole('tab', { name: /Database/ }))
    expect(screen.getByText('Migrations failed')).toBeInTheDocument()
    expect(screen.getByText('relation "missing" does not exist')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /Tests/ }))
    expect(screen.getByText('Failing')).toBeInTheDocument() // all 6 tests passed, but the schema did not apply
  })

  it('projects without a database have no Database tab', async () => {
    renderApp('/runs/r-1', runPage())
    await screen.findByRole('tab', { name: /Tests/ })
    expect(screen.queryByRole('tab', { name: /Database/ })).not.toBeInTheDocument()
  })

  it('the schema step sits between plan approval and coding', () => {
    expect(WORKFLOW_EDGES.filter((e) => e.from === 'schema' || e.to === 'schema').map((e) => `${e.from}->${e.to}`)).toEqual([
      'plan_approval->schema',
      'schema->code',
    ])
  })
})

describe('run memory', () => {
  const memoryEvent = (id: number, payload: Record<string, unknown>) => ({ id, type: 'memory.added', node: null, payload, createdAt: new Date() })

  it('shows what agents assumed and tried, and what AgentForge measured', async () => {
    const user = userEvent.setup()
    const gateways = runPage()
    gateways.runs.events.mockResolvedValue([
      memoryEvent(1, { step: 'plan', author: 'planner', kind: 'assumption', text: 'Counter lives in memory', files: [], outcome: null }),
      memoryEvent(2, { step: 'debug', author: 'debugger', kind: 'hypothesis', text: 'Attempt 1: get_db is wrong', files: ['app/repository.py'], outcome: null }),
      memoryEvent(3, {
        step: 'run_tests', author: 'agentforge', kind: 'verdict',
        text: 'Debug attempt 1: the same 5 failure(s) remain', files: ['app/repository.py'], outcome: 'refuted',
      }),
      { id: 4, type: 'node.finished', node: 'plan', payload: {}, createdAt: new Date() },
    ])
    renderApp('/runs/r-1', gateways)
    await user.click(await screen.findByRole('tab', { name: /Memory/ }))
    const items = within(screen.getByRole('list', { name: 'Run memory' })).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Assumption')
    expect(items[1]).toHaveTextContent('Hypothesis')
    expect(items[1]).not.toHaveTextContent('measured')
    expect(items[2]).toHaveTextContent('Verdict')
    expect(items[2]).toHaveTextContent('refuted')
    expect(items[2]).toHaveTextContent('measured')
  })

  it('explains an empty memory', async () => {
    const user = userEvent.setup()
    renderApp('/runs/r-1', runPage())
    await user.click(await screen.findByRole('tab', { name: /Memory/ }))
    expect(screen.getByText('Nothing in memory yet')).toBeInTheDocument()
  })
})

describe('Agent Activity page', () => {
  it('shows what each active run is doing and the recently finished ones', async () => {
    const user = userEvent.setup()
    const gateways = createFakeGateways()
    gateways.runs.list.mockResolvedValue({
      items: [
        makeRun({ id: 'r-a', projectName: 'Alpha', status: 'running', currentNode: 'debug' }),
        makeRun({ id: 'r-b', projectName: 'Beta', status: 'awaiting_approval', currentNode: 'plan_approval' }),
        makeRun({ id: 'r-c', projectName: 'Gamma', status: 'completed' }),
      ],
      total: 3,
    })
    gateways.runs.agents.mockImplementation(async (id: string) =>
      id === 'r-a' ? [execution('debug', 2, { agent: 'debugger', status: 'running', finishedAt: null })] : [],
    )
    renderApp('/', gateways)
    await user.click(await screen.findByRole('link', { name: 'Agent Activity' }))

    const active = await screen.findByRole('list', { name: 'Active runs' })
    expect(within(active).getByText('Alpha')).toBeInTheDocument()
    expect(await within(active).findByText('debugger · Debugging (attempt 2)')).toBeInTheDocument()
    expect(within(active).getByText('Waiting for your decision at Plan approval')).toBeInTheDocument()
    expect(within(active).queryByText('Gamma')).not.toBeInTheDocument()
    expect(screen.getByText('Recently finished')).toBeInTheDocument()
    expect(screen.getByText('Working now (2)')).toBeInTheDocument()
  })

  it('says when nothing is running', async () => {
    renderApp('/activity')
    expect(await screen.findByText('No agents are working right now')).toBeInTheDocument()
  })
})
