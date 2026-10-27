/**
 * Thin fetch wrapper for the AGENT-P API. Sends the session cookie, attaches
 * the CSRF token on mutations, and normalizes failures into ApiError
 * (RFC 9457 problem+json, see docs/API_SPECIFICATION.md §1).
 */

export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const API_BASE = `${API_URL}/api/v1`

export interface ProblemDetails {
  type?: string
  title: string
  status: number
  detail?: string
  request_id?: string
  errors?: { loc: (string | number)[]; msg: string }[]
}

export class ApiError extends Error {
  readonly status: number
  readonly problem: ProblemDetails | null
  /** True when the backend could not be reached at all. */
  readonly network: boolean

  constructor(message: string, status: number, problem: ProblemDetails | null, network = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
    this.network = network
  }
}

/**
 * CSRF synchronizer token from /auth/session or /auth/me. Held in memory only: the API sets its
 * session cookie on its own domain, which this SPA (on another domain) cannot read anyway.
 */
let csrfToken: string | null = null
export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  idempotencyKey?: string
  signal?: AbortSignal
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken
  if (opts.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: 'include',
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(`Cannot reach the AGENT-P backend at ${API_URL}`, 0, null, true)
  }

  if (res.status === 204) return undefined as T
  const isJson = (res.headers.get('content-type') ?? '').includes('json')
  const data: unknown = isJson ? await res.json().catch(() => null) : null

  if (!res.ok) {
    const problem = (data as ProblemDetails | null) ?? null
    throw new ApiError(problem?.detail ?? problem?.title ?? `Request failed (${res.status})`, res.status, problem)
  }
  return data as T
}

export const eventStreamUrl = (runId: string, afterSeq: number): string =>
  `${API_BASE}/runs/${encodeURIComponent(runId)}/events/stream?after_seq=${afterSeq}`
