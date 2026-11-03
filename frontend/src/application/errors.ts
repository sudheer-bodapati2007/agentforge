export interface FieldError {
  field: string
  message: string
}

export type AppErrorKind =
  | 'network'
  | 'unauthorized'
  | 'not_found'
  | 'validation'
  | 'conflict'
  | 'rate_limited'
  | 'server'
  | 'unknown'

/** Transport-independent error the UI can render. Gateways translate failures into this. */
export class AppError extends Error {
  readonly kind: AppErrorKind
  readonly status: number | null
  readonly fieldErrors: FieldError[]

  constructor(
    kind: AppErrorKind,
    message: string,
    options: { status?: number | null; fieldErrors?: FieldError[] } = {},
  ) {
    super(message)
    this.name = 'AppError'
    this.kind = kind
    this.status = options.status ?? null
    this.fieldErrors = options.fieldErrors ?? []
  }
}

/** One-line text for toasts: the summary plus the backend's reasons, which forms show per field. */
export function errorMessage(error: unknown): string {
  const appError = toAppError(error)
  const reasons = [...new Set(appError.fieldErrors.map((f) => f.message))]
  return reasons.length ? `${appError.message}: ${reasons.join('; ')}` : appError.message
}

export function toAppError(error: unknown): AppError {
  if (error instanceof AppError) return error
  return new AppError('unknown', error instanceof Error ? error.message : 'Something went wrong')
}
