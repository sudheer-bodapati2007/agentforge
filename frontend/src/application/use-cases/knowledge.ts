import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useGateways } from '../gateways-context'

export const knowledgeKeys = {
  documents: (projectId: string) => ['knowledge', projectId, 'documents'] as const,
  chunks: (projectId: string, documentId: string) => ['knowledge', projectId, 'chunks', documentId] as const,
  search: (projectId: string, query: string) => ['knowledge', projectId, 'search', query] as const,
}

export function useDocuments(projectId: string | undefined) {
  const { knowledge } = useGateways()
  return useQuery({
    queryKey: knowledgeKeys.documents(projectId ?? ''),
    queryFn: () => knowledge.list(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useDocumentChunks(projectId: string, documentId: string | null) {
  const { knowledge } = useGateways()
  return useQuery({
    queryKey: knowledgeKeys.chunks(projectId, documentId ?? ''),
    queryFn: () => knowledge.chunks(projectId, documentId!),
    enabled: Boolean(documentId),
  })
}

/** Runs only for a submitted query (not on every keystroke). */
export function useKnowledgeSearch(projectId: string | undefined, query: string) {
  const { knowledge } = useGateways()
  return useQuery({
    queryKey: knowledgeKeys.search(projectId ?? '', query),
    queryFn: () => knowledge.search(projectId!, query),
    enabled: Boolean(projectId && query.trim()),
  })
}

/** Any document change invalidates the list, its chunks and earlier search results. */
function useInvalidateKnowledge() {
  const client = useQueryClient()
  return (projectId: string) => client.invalidateQueries({ queryKey: ['knowledge', projectId] })
}

export function useUploadDocument(projectId: string) {
  const { knowledge } = useGateways()
  const invalidate = useInvalidateKnowledge()
  return useMutation({
    mutationFn: (file: { name: string; content: string }) => knowledge.upload(projectId, file.name, file.content),
    onSuccess: () => invalidate(projectId),
  })
}

export function useDeleteDocument(projectId: string) {
  const { knowledge } = useGateways()
  const invalidate = useInvalidateKnowledge()
  return useMutation({
    mutationFn: (documentId: string) => knowledge.remove(projectId, documentId),
    onSuccess: () => invalidate(projectId),
  })
}

export function useReindexDocument(projectId: string) {
  const { knowledge } = useGateways()
  const invalidate = useInvalidateKnowledge()
  return useMutation({
    mutationFn: (documentId: string) => knowledge.reindex(projectId, documentId),
    onSuccess: () => invalidate(projectId),
  })
}
