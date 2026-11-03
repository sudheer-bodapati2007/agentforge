import { AppError, type AppErrorKind, type FieldError } from '@/application/errors'

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: { loc?: (string | number)[]; msg?: string }[]
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  headers?: Record<string, string>
  signal?: AbortSignal
}

export interface HttpClient {
  request<T>(method: HttpMethod, path: string, options?: RequestOptions): Promise<T>
  /** Authenticated request returning the raw Response (streams, downloads). Errors are thrown as AppError. */
  raw(method: HttpMethod, path: string, options?: RequestOptions): Promise<Response>
}

export interface HttpClientOptions {
  fetchImpl?: typeof fetch
  /** Supplies the current access token; called per request so refreshed tokens are used. */
  getAccessToken?: () => Promise<string | null>
  /** Called when the backend rejects the credentials (401). */
  onUnauthorized?: () => void
}

function kindForStatus(status: number): AppErrorKind {
  if (status === 401) return 'unauthorized'
  if (status === 404) return 'not_found'
  if (status === 422 || status === 400 || status === 413) return 'validation'
  if (status === 409) return 'conflict'
  if (status === 429) return 'rate_limited'
  if (status >= 500) return 'server'
  return 'unknown'
}

function toFieldErrors(details: NonNullable<ApiErrorBody['error']>['details']): FieldError[] {
  return (details ?? []).map((detail) => {
    const loc = detail.loc ?? []
    // FastAPI locations look like ["body", "requirements"].
    const field = String(loc[0] === 'body' || loc[0] === 'query' ? (loc[1] ?? '') : (loc.at(-1) ?? ''))
    return { field, message: detail.msg ?? 'Invalid value' }
  })
}

export function createHttpClient(baseUrl: string, options: HttpClientOptions = {}): HttpClient {
  const { fetchImpl = (...args) => fetch(...args), getAccessToken, onUnauthorized } = options

  async function send(method: HttpMethod, path: string, opts: RequestOptions = {}): Promise<Response> {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(opts.query ?? {})) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    const url = `${baseUrl}${path}${params.size ? `?${params}` : ''}`

    const headers: Record<string, string> = { ...(opts.headers ?? {}) }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    const token = getAccessToken ? await getAccessToken() : null
    if (token) headers.Authorization = `Bearer ${token}`

    let response: Response
    try {
      response = await fetchImpl(url, {
        method,
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
        signal: opts.signal,
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new AppError('network', 'Cannot reach the AgentForge API. Is the backend running?')
    }

    if (!response.ok) {
      if (response.status === 401) onUnauthorized?.()
      const body = ((await response.json().catch(() => null)) ?? {}) as ApiErrorBody
      throw new AppError(
        kindForStatus(response.status),
        body.error?.message ?? `Request failed with status ${response.status}`,
        { status: response.status, fieldErrors: toFieldErrors(body.error?.details) },
      )
    }
    return response
  }

  return {
    async request<T>(method: HttpMethod, path: string, opts: RequestOptions = {}) {
      const response = await send(method, path, opts)
      if (response.status === 204) return undefined as T
      return (await response.json().catch(() => null)) as T
    },
    raw: send,
  }
}
