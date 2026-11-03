import { describe, expect, it } from 'vitest'
import { formatDuration, formatPercent, formatUsd, NO_DATA } from './format'

describe('format helpers', () => {
  it('renders null as no-data, never as zero', () => {
    expect(formatPercent(null)).toBe(NO_DATA)
    expect(formatDuration(null)).toBe(NO_DATA)
    expect(formatUsd(null)).toBe(NO_DATA)
  })

  it('formats real values', () => {
    expect(formatPercent(0)).toBe('0.0%')
    expect(formatPercent(1)).toBe('100%')
    expect(formatPercent(0.625)).toBe('62.5%')
    expect(formatDuration(75)).toBe('1m 15s')
    expect(formatUsd(0.004)).toBe('<$0.01')
    expect(formatUsd(1.5)).toBe('$1.50')
  })
})
