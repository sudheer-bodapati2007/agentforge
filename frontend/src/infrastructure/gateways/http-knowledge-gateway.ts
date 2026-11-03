import type { KnowledgeGateway } from '@/application/ports'
import type { DocumentChunk, KnowledgeDocument, SearchHit, SearchResult } from '@/domain/knowledge'
import type { HttpClient } from '../http/http-client'
import { fromWire, listFromWire } from './wire'

export const toDocument = (dto: object) => fromWire<KnowledgeDocument>(dto, ['createdAt', 'updatedAt'])

export function createKnowledgeGateway(http: HttpClient): KnowledgeGateway {
  const base = (projectId: string) => `/projects/${encodeURIComponent(projectId)}`
  const doc = (projectId: string, documentId: string) => `${base(projectId)}/documents/${encodeURIComponent(documentId)}`
  return {
    async list(projectId) {
      const dto = await http.request<{ items: object[]; embedder: string }>('GET', `${base(projectId)}/documents`)
      return { items: dto.items.map(toDocument), embedder: dto.embedder }
    },
    async upload(projectId, filename, content) {
      const dto = await http.request<{ document: object; created: boolean; unchanged: boolean }>(
        'POST',
        `${base(projectId)}/documents`,
        { body: { filename, content } },
      )
      return { document: toDocument(dto.document), created: dto.created, unchanged: dto.unchanged }
    },
    chunks: async (projectId, documentId) =>
      listFromWire<DocumentChunk>()(await http.request<object[]>('GET', `${doc(projectId, documentId)}/chunks`)),
    reindex: async (projectId, documentId) => toDocument(await http.request<object>('POST', `${doc(projectId, documentId)}/reindex`)),
    remove: async (projectId, documentId) => {
      await http.request<void>('DELETE', doc(projectId, documentId))
    },
    async search(projectId, query, k) {
      const dto = await http.request<{ results: object[] }>('GET', `${base(projectId)}/knowledge/search`, { query: { q: query, k } })
      return { ...fromWire<SearchResult>(dto), results: listFromWire<SearchHit>()(dto.results) }
    },
  }
}
