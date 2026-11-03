import { useQuery } from '@tanstack/react-query'
import { useGateways } from '../gateways-context'

export function useBenchmarks(limit = 5) {
  const { evaluations } = useGateways()
  return useQuery({ queryKey: ['evaluations', limit], queryFn: () => evaluations.recent(limit) })
}
