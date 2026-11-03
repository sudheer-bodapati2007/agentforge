import { useQuery } from '@tanstack/react-query'
import { useGateways } from '../gateways-context'

export function useSystemStatus() {
  const { system } = useGateways()
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => system.status(),
    refetchInterval: 30_000,
  })
}
