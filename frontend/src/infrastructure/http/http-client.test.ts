import { describe, expect, it, vi } from 'vitest'
import { AppError } from '@/application/errors'
import { createHttpClient } from './http-client'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('createHttpClient', () => {
  it('builds URLs with query params and skips empty values', async () => {
    const fetchImpl = vi.fn(async () => json(200, { ok: true }))
    await createHttpClient('/api', { fetchImpl }).request('GET', '/projects', {
      query: { q: 'abc', limit: 5, offset: undefined },
    })
    expect(fetchImpl).toHaveBeenCalledWith('/api/projects?q=abc&limit=5', expect.objectContaining({ method: 'GET' }))
  })

  it('turns structured validation errors into AppError with field errors', async () => {
    const fetchImpl = vi.fn(async () =>
      json(422, {
        error: {
          code: 'validation_error',
          message: 'Request validation failed',
          details: [{ loc: ['body', 'requirements'], msg: 'too short' }],
        },
      }),
    )
    const error = await createHttpClient('/api', { fetchImpl })
      .request('POST', '/projects', { body: {} })
      .catch((e: unknown) => e)
    expect(error).toBeInstanceOf(AppError)
    expect((error as AppError).kind).toBe('validation')
    expect((error as AppError).fieldErrors).toEqual([{ field: 'requirements', message: 'too short' }])
  })

  it('maps 404 to not_found and network failures to network', async () => {
    const notFound = (await createHttpClient('/api', {
      fetchImpl: vi.fn(async () => json(404, { error: { code: 'not_found', message: 'gone' } })),
    })
      .request('GET', '/x')
      .catch((e: unknown) => e)) as AppError
    expect(notFound.kind).toBe('not_found')
    expect(notFound.message).toBe('gone')

    const offline = (await createHttpClient('/api', {
      fetchImpl: vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    })
      .request('GET', '/x')
      .catch((e: unknown) => e)) as AppError
    expect(offline.kind).toBe('network')
  })

  it('handles 204 No Content', async () => {
    const client = createHttpClient('/api', { fetchImpl: vi.fn(async () => new Response(null, { status: 204 })) })
    await expect(client.request('DELETE', '/x')).resolves.toBeUndefined()
  })

  it('attaches the bearer token and reports 401s', async () => {
    const fetchImpl = vi.fn(async (_url: string, _init?: RequestInit) =>
      json(401, { error: { code: 'unauthorized', message: 'Access token has expired' } }),
    )
    const onUnauthorized = vi.fn()
    const client = createHttpClient('/api', {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      getAccessToken: async () => 'tok-123',
      onUnauthorized,
    })
    const error = (await client.request('GET', '/projects').catch((e: unknown) => e)) as AppError
    expect(fetchImpl.mock.calls[0][1]?.headers).toEqual({ Authorization: 'Bearer tok-123' })
    expect(error.kind).toBe('unauthorized')
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('sends no Authorization header when signed out', async () => {
    const fetchImpl = vi.fn(async (_url: string, _init?: RequestInit) => json(200, {}))
    await createHttpClient('/api', {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      getAccessToken: async () => null,
    }).request('GET', '/health')
    expect(fetchImpl.mock.calls[0][1]?.headers).toEqual({})
  })
})
