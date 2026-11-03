/** Knowledge base (Phase 4): project documents the agents retrieve from. */

export type DocumentKind = 'markdown' | 'text' | 'python'

/** Mirrors the backend rules; the backend validates again and is authoritative. */
export const ALLOWED_EXTENSIONS = ['.md', '.markdown', '.txt', '.rst', '.py'] as const
export const MAX_DOCUMENT_BYTES = 400_000

export interface KnowledgeDocument {
  id: string
  projectId: string
  filename: string
  kind: DocumentKind
  sizeBytes: number
  sha256: string
  chunkCount: number
  embedder: string
  redactedLines: number
  /** Indexed with a different embedder than the current one: not searchable until re-indexed. */
  stale: boolean
  createdAt: Date
  updatedAt: Date
}

export interface DocumentList {
  items: KnowledgeDocument[]
  embedder: string
}

export interface UploadOutcome {
  document: KnowledgeDocument
  created: boolean
  unchanged: boolean
}

export interface DocumentChunk {
  id: string
  ordinal: number
  text: string
  heading: string | null
  startLine: number
  endLine: number
}

export interface SearchHit {
  documentId: string
  source: string
  location: string
  heading: string | null
  startLine: number
  endLine: number
  text: string
  denseScore: number | null
  sparseScore: number | null
  fusedScore: number
  rerankScore: number | null
  score: number
}

export interface SearchResult {
  query: string
  embedder: string
  mode: string
  reranker: string | null
  results: SearchHit[]
}

/** A reason the file cannot be uploaded, or null. Saves a round trip for obvious cases. */
export function uploadProblem(name: string, sizeBytes: number): string | null {
  const dot = name.lastIndexOf('.')
  const extension = dot >= 0 ? name.slice(dot).toLowerCase() : ''
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(extension)) {
    return `only ${ALLOWED_EXTENSIONS.join(', ')} files are supported`
  }
  if (sizeBytes === 0) return 'the file is empty'
  if (sizeBytes > MAX_DOCUMENT_BYTES) return `files are limited to ${MAX_DOCUMENT_BYTES / 1000} KB`
  return null
}
