import { describe, expect, it, vi } from 'vitest'
import type { HttpClient } from '../http/http-client'
import { createKnowledgeGateway } from './http-knowledge-gateway'

const documentDto = {
  id: 'd/1',
  project_id: 'p-1',
  filename: 'a.md',
  kind: 'markdown',
  size_bytes: 10,
  sha256: 'f'.repeat(64),
  chunk_count: 1,
  embedder: 'hash-384',
  redacted_lines: 0,
  stale: false,
  created_at: '2026-10-22T10:00:00Z',
  updated_at: '2026-10-22T11:00:00Z',
}

describe('knowledge gateway', () => {
  it('uploads as JSON and maps the nested document', async () => {
    const request = vi.fn(async () => ({ document: documentDto, created: false, unchanged: true }))
    const outcome = await createKnowledgeGateway({ request } as unknown as HttpClient).upload('p-1', 'a.md', '# A')
    expect(request).toHaveBeenCalledWith('POST', '/projects/p-1/documents', { body: { filename: 'a.md', content: '# A' } })
    expect(outcome.unchanged).toBe(true)
    expect(outcome.document.updatedAt).toEqual(new Date('2026-10-22T11:00:00Z'))
    expect(outcome.document.chunkCount).toBe(1)
  })

  it('encodes ids in paths and maps search hits', async () => {
    const request = vi.fn(async (_method: string, path: string) =>
      path.endsWith('/search')
        ? { query: 'q', embedder: 'hash-384', mode: 'hybrid', reranker: null, results: [{ document_id: 'd', start_line: 3, rerank_score: null, dense_score: 0.5 }] }
        : undefined,
    )
    const gateway = createKnowledgeGateway({ request } as unknown as HttpClient)
    await gateway.remove('p-1', 'd/1')
    expect(request).toHaveBeenCalledWith('DELETE', '/projects/p-1/documents/d%2F1')
    const result = await gateway.search('p-1', 'q', 3)
    expect(request).toHaveBeenLastCalledWith('GET', '/projects/p-1/knowledge/search', { query: { q: 'q', k: 3 } })
    expect(result.reranker).toBeNull()
    expect(result.results[0]).toEqual({ documentId: 'd', startLine: 3, rerankScore: null, denseScore: 0.5 })
  })
})
