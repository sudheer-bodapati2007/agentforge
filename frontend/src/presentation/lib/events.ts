import type { RunEvent } from '@/domain/run'

/** A short, human-readable line for an event, from the fields most events carry. */
export function describeEvent(event: RunEvent): string {
  const p = event.payload
  const pick = (key: string) => (typeof p[key] === 'string' || typeof p[key] === 'number' ? String(p[key]) : null)
  if (event.type === 'tool.called' && p.tool === 'retrieve_documentation' && Array.isArray(p.results)) {
    const sources = (p.results as { source?: string }[]).map((r) => r.source).filter(Boolean)
    return `retrieved ${sources.length} passage(s): ${[...new Set(sources)].join(', ')}`
  }
  if (event.type === 'tests.completed') {
    return p.executed
      ? `${p.passed}/${p.total} passed, ${p.failed} failed, ${p.errors} errors`
      : `not executed: ${pick('unavailable_reason') ?? 'unknown'}`
  }
  return pick('summary') ?? pick('diagnosis') ?? pick('tool') ?? pick('outcome') ?? pick('error') ?? pick('status') ?? ''
}
