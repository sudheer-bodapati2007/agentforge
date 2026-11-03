import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { AuthProvider } from '@/application/auth-context'
import { GatewaysProvider } from '@/application/gateways-context'
import type { Gateways } from '@/application/ports'
import { ToastProvider } from '@/presentation/components/ui/Toast'

/** Shared by the real app and by tests, which inject fake gateways. */
export function AppProviders({
  gateways,
  queryClient,
  children,
}: {
  gateways: Gateways
  queryClient: QueryClient
  children: ReactNode
}) {
  return (
    <GatewaysProvider gateways={gateways}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </GatewaysProvider>
  )
}
