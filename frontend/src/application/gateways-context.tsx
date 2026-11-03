import { createContext, useContext, type ReactNode } from 'react'
import type { Gateways } from './ports'

const GatewaysContext = createContext<Gateways | null>(null)

export function GatewaysProvider({ gateways, children }: { gateways: Gateways; children: ReactNode }) {
  return <GatewaysContext.Provider value={gateways}>{children}</GatewaysContext.Provider>
}

// eslint-disable-next-line react/only-export-components -- hook co-located with its provider
export function useGateways(): Gateways {
  const gateways = useContext(GatewaysContext)
  if (!gateways) throw new Error('useGateways must be used inside <GatewaysProvider>')
  return gateways
}
