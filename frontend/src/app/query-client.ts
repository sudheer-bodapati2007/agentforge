import { QueryClient } from '@tanstack/react-query'
import { AppError } from '@/application/errors'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        // Retrying cannot fix a missing resource or a rejected request.
        retry: (failureCount, error) =>
          !(
            error instanceof AppError &&
            (error.kind === 'not_found' || error.kind === 'validation' || error.kind === 'unauthorized')
          ) &&
          failureCount < 2,
      },
    },
  })
}
