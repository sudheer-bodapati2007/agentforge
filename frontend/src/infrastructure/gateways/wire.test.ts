import { describe, expect, it } from 'vitest'
import { toEvent, toRun } from './http-run-gateway'
import { fromWire } from './wire'

describe('fromWire', () => {
  it('camelizes top-level keys and parses only the named date fields', () => {
    const value = fromWire<Record<string, unknown>>(
      { project_id: 'p', created_at: '2026-10-01T10:00:00Z', finished_at: null, note_2_x: 'n' },
      ['createdAt', 'finishedAt'],
    )
    expect(value.projectId).toBe('p')
    expect(value.createdAt).toBeInstanceOf(Date)
    expect(value.finishedAt).toBeNull()
    expect(value.note2X).toBe('n')
  })

  it('leaves nested contracts untouched', () => {
    const run = toRun({ id: 'r', created_at: '2026-10-01T10:00:00Z', final_report: { tasks_not_verified: ['a'] } })
    expect(run.finalReport).toEqual({ tasks_not_verified: ['a'] })
    const event = toEvent({ id: 1, type: 'x', node: null, payload: { input_tokens: 3 }, created_at: '2026-10-01T10:00:00Z' })
    expect(event.payload).toEqual({ input_tokens: 3 })
  })
})
