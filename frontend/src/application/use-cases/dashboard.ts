import { useQuery } from '@tanstack/react-query'
import { useGateways } from '../gateways-context'

export function useDashboardMetrics() {
  const { dashboard } = useGateways()
  return useQuery({ queryKey: ['dashboard', 'metrics'], queryFn: () => dashboard.metrics() })
}
