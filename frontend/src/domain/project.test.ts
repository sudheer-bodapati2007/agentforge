import { describe, expect, it } from 'vitest'
import { EMPTY_DRAFT, validateProjectDraft } from './project'

describe('validateProjectDraft', () => {
  it('requires a name and sufficiently detailed requirements', () => {
    const errors = validateProjectDraft({ ...EMPTY_DRAFT, name: '   ', requirements: 'too short' })
    expect(errors.name).toBeDefined()
    expect(errors.requirements).toMatch(/at least 20/)
  })

  it('accepts a valid draft and trims before measuring', () => {
    const errors = validateProjectDraft({ ...EMPTY_DRAFT, name: ' API ', requirements: `  ${'r'.repeat(20)}  ` })
    expect(errors).toEqual({})
  })

  it('limits optional fields', () => {
    const errors = validateProjectDraft({
      ...EMPTY_DRAFT,
      name: 'a',
      requirements: 'r'.repeat(20),
      framework: 'f'.repeat(81),
    })
    expect(errors.framework).toBeDefined()
  })
})
