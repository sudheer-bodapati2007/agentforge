/**
 * Wire-format adapter: the API speaks snake_case JSON with ISO dates; the domain uses
 * camelCase with Date objects. One generic conversion replaces per-type mapping code.
 *
 * Only top-level keys are converted. Nested objects (event payloads, final reports,
 * failure lists) keep the API's shape on purpose: they are documented contracts.
 */

export const toCamel = (key: string) => key.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase())
export const toSnake = (key: string) => key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)

export function fromWire<T>(dto: object, dateFields: readonly string[] = []): T {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(dto)) {
    const name = toCamel(key)
    out[name] = dateFields.includes(name) && typeof value === 'string' ? new Date(value) : value
  }
  return out as T
}

export const listFromWire =
  <T>(dateFields: readonly string[] = []) =>
  (rows: object[]): T[] =>
    rows.map((row) => fromWire<T>(row, dateFields))
