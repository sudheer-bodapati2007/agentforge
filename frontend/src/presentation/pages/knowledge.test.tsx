import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { AppError } from '@/application/errors'
import { MAX_DOCUMENT_BYTES, uploadProblem } from '@/domain/knowledge'
import type { RunEvent } from '@/domain/run'
import { createFakeGateways, makeDocument, makeProject, makeRun, makeSearchHit } from '@/test/fakes'
import { renderApp } from '@/test/render'
import { describeEvent } from '../lib/events'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.open = false
  }
})

function withProject(...projects: ReturnType<typeof makeProject>[]) {
  const gateways = createFakeGateways()
  const list = projects.length ? projects : [makeProject()]
  gateways.projects.list.mockResolvedValue({ items: list, total: list.length })
  return gateways
}

describe('upload rules', () => {
  it('catches obvious problems before a round trip', () => {
    expect(uploadProblem('guide.md', 10)).toBeNull()
    expect(uploadProblem('Notes.TXT', 10)).toBeNull()
    expect(uploadProblem('virus.exe', 10)).toMatch(/only \.md/)
    expect(uploadProblem('noextension', 10)).toMatch(/only/)
    expect(uploadProblem('empty.md', 0)).toMatch(/empty/)
    expect(uploadProblem('big.md', MAX_DOCUMENT_BYTES + 1)).toMatch(/400 KB/)
  })
})

describe('Knowledge Base page', () => {
  it('is reachable from the sidebar and asks for a project first', async () => {
    const user = userEvent.setup()
    renderApp('/')
    await user.click(await screen.findByRole('link', { name: 'Knowledge Base' }))
    expect(await screen.findByText('Create a project first')).toBeInTheDocument()
  })

  it('uploads documents and reports what happened', async () => {
    const user = userEvent.setup()
    const gateways = withProject()
    renderApp('/knowledge', gateways)
    expect(await screen.findByText('No documents yet')).toBeInTheDocument()

    const input = screen.getByLabelText('Choose documents to upload')
    await user.upload(input, new File(['# Guide\nUse snake_case.'], 'guide.md', { type: 'text/markdown' }))
    await waitFor(() => expect(gateways.knowledge.upload).toHaveBeenCalledWith('p-1', 'guide.md', '# Guide\nUse snake_case.'))
    expect(await screen.findByText('guide.md added: 3 chunks')).toBeInTheDocument()
  })

  it('refuses unsupported or oversized files without calling the API', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const gateways = withProject()
    renderApp('/knowledge', gateways)
    const input = await screen.findByLabelText('Choose documents to upload')
    await user.upload(input, [
      new File(['MZ'], 'tool.exe'),
      new File(['x'.repeat(MAX_DOCUMENT_BYTES + 1)], 'huge.md'),
    ])
    expect(await screen.findByText(/tool\.exe: only \.md/)).toBeInTheDocument()
    expect(screen.getByText(/huge\.md: files are limited to 400 KB/)).toBeInTheDocument()
    expect(gateways.knowledge.upload).not.toHaveBeenCalled()
  })

  it('shows the backend reason when an upload is rejected', async () => {
    const user = userEvent.setup()
    const gateways = withProject()
    gateways.knowledge.upload.mockRejectedValue(
      new AppError('conflict', 'A project can hold at most 50 documents; delete one first', { status: 409 }),
    )
    renderApp('/knowledge', gateways)
    await user.upload(await screen.findByLabelText('Choose documents to upload'), new File(['x'], 'one-more.md'))
    expect(await screen.findByText(/one-more\.md: A project can hold at most 50 documents/)).toBeInTheDocument()
  })

  it('lists documents with redactions, re-indexes stale ones, shows chunks and deletes', async () => {
    const user = userEvent.setup()
    const gateways = withProject()
    gateways.knowledge.list.mockResolvedValue({
      items: [
        makeDocument({ id: 'd-1', filename: 'deploy.md', redactedLines: 2 }),
        makeDocument({ id: 'd-2', filename: 'old.md', embedder: 'hash-256', stale: true }),
      ],
      embedder: 'hash-384',
    })
    gateways.knowledge.chunks.mockResolvedValue([
      { id: 'c-1', ordinal: 0, text: 'Run make deploy.', heading: 'Deploy', startLine: 1, endLine: 3 },
    ])
    renderApp('/knowledge', gateways)

    expect(await screen.findByText('2 redacted')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('1 document(s) were indexed with a different embedder')

    await user.click(screen.getByRole('button', { name: 'Re-index' }))
    await waitFor(() => expect(gateways.knowledge.reindex).toHaveBeenCalledWith('p-1', 'd-2'))

    await user.click(screen.getByRole('button', { name: 'Show chunks of deploy.md' }))
    const chunks = await screen.findByRole('list', { name: 'Chunks' })
    expect(within(chunks).getByText('Run make deploy.')).toBeInTheDocument()
    expect(within(chunks).getByText(/lines 1–3 · Deploy/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete deploy.md' }))
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(gateways.knowledge.remove).toHaveBeenCalledWith('p-1', 'd-1'))
  })

  it('tests retrieval with every stage visible, and explains an empty result', async () => {
    const user = userEvent.setup()
    const gateways = withProject()
    gateways.knowledge.search
      .mockResolvedValueOnce({ query: 'page size', embedder: 'hash-384', mode: 'hybrid', reranker: 'lexical', results: [makeSearchHit()] })
      .mockResolvedValueOnce({ query: 'sourdough', embedder: 'hash-384', mode: 'hybrid', reranker: 'lexical', results: [] })
    renderApp('/knowledge', gateways)

    const box = await screen.findByRole('textbox', { name: 'Search query' })
    expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
    await user.type(box, 'page size')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    const results = await screen.findByRole('list', { name: 'Retrieved chunks' })
    expect(within(results).getByText('1. conventions.md')).toBeInTheDocument()
    expect(within(results).getByText(/dense 0\.41 · bm25 3\.20 · rerank 0\.66 · final/)).toBeInTheDocument()
    expect(gateways.knowledge.search).toHaveBeenCalledWith('p-1', 'page size')

    await user.clear(box)
    await user.type(box, 'sourdough{enter}')
    expect(await screen.findByText(/No relevant documents/)).toBeInTheDocument()
  })

  it('switches project from the selector and the URL', async () => {
    const user = userEvent.setup()
    const gateways = withProject(makeProject({ id: 'p-1', name: 'Alpha' }), makeProject({ id: 'p-2', name: 'Beta' }))
    renderApp('/knowledge?project=p-2', gateways)
    await waitFor(() => expect(gateways.knowledge.list).toHaveBeenCalledWith('p-2'))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Project' }), 'p-1')
    await waitFor(() => expect(gateways.knowledge.list).toHaveBeenCalledWith('p-1'))
  })
})

const event = (overrides: Partial<RunEvent>): RunEvent => ({ id: 1, type: 'node.finished', node: 'plan', payload: {}, createdAt: new Date('2026-10-22T10:00:00Z'), ...overrides })

describe('Execution History page', () => {
  it('describes events in plain words', () => {
    expect(describeEvent(event({ type: 'tool.called', payload: { tool: 'retrieve_documentation', results: [{ source: 'a.md' }, { source: 'a.md' }, { source: 'b.md' }] } })))
      .toBe('retrieved 3 passage(s): a.md, b.md')
    expect(describeEvent(event({ type: 'tests.completed', payload: { executed: true, passed: 5, total: 6, failed: 1, errors: 0 } }))).toBe('5/6 passed, 1 failed, 0 errors')
    expect(describeEvent(event({ type: 'tests.completed', payload: { executed: false, unavailable_reason: 'Docker is not running' } }))).toBe('not executed: Docker is not running')
    expect(describeEvent(event({ payload: { summary: '3 tasks' } }))).toBe('3 tasks')
    expect(describeEvent(event({ payload: { nested: { x: 1 } } }))).toBe('')
  })

  it('lists runs, filters them and expands one run’s event log', async () => {
    const user = userEvent.setup()
    const gateways = withProject(makeProject({ id: 'p-1', name: 'Alpha' }))
    gateways.runs.list.mockResolvedValue({ items: [makeRun({ id: 'r-12345678', projectName: 'Alpha' })], total: 1 })
    gateways.runs.events.mockResolvedValue([
      event({ id: 1, type: 'node.finished', node: 'plan', payload: { summary: '4 tasks, 3 acceptance criteria' } }),
      event({ id: 2, type: 'tests.completed', node: null, payload: { executed: true, passed: 6, total: 6, failed: 0, errors: 0 } }),
    ])
    renderApp('/history', gateways)

    await user.click(await screen.findByRole('button', { name: 'Show history of run r-123456' }))
    const log = await screen.findByRole('list', { name: 'Event history' })
    expect(within(log).getByText('4 tasks, 3 acceptance criteria')).toBeInTheDocument()
    expect(within(log).getByText('6/6 passed, 0 failed, 0 errors')).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by project' }), 'p-1')
    await waitFor(() => expect(gateways.runs.list).toHaveBeenLastCalledWith(expect.objectContaining({ projectId: 'p-1', offset: 0 })))
  })

  it('says so when filters match nothing', async () => {
    const user = userEvent.setup()
    renderApp('/history', withProject())
    expect(await screen.findByText('No runs yet')).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by status' }), 'failed')
    expect(await screen.findByText('No runs match these filters')).toBeInTheDocument()
  })
})
