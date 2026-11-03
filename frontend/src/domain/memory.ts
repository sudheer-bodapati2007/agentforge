import type { RunEvent } from './run'

/** One entry of a run's shared memory. FACT and VERDICT entries are measured by AgentForge. */
export interface MemoryEntry {
  id: number
  step: string
  author: string
  kind: 'assumption' | 'decision' | 'note' | 'hypothesis' | 'fact' | 'verdict' | string
  text: string
  files: string[]
  outcome: 'confirmed' | 'partly' | 'refuted' | 'unknown' | null
}

export const isMeasured = (entry: MemoryEntry) => entry.kind === 'fact' || entry.kind === 'verdict'

/** The run's shared memory, rebuilt from its `memory.added` events (so it updates live). */
export function memoryFromEvents(events: RunEvent[]): MemoryEntry[] {
  return events
    .filter((e) => e.type === 'memory.added')
    .map((e) => {
      const p = e.payload
      return {
        id: e.id,
        step: String(p.step ?? ''),
        author: String(p.author ?? ''),
        kind: String(p.kind ?? 'note'),
        text: String(p.text ?? ''),
        files: Array.isArray(p.files) ? p.files.map(String) : [],
        outcome: (p.outcome as MemoryEntry['outcome']) ?? null,
      }
    })
}
