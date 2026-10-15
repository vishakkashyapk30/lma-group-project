// Errors raised by the API client and the demo backend.

/** An HTTP-level error from the backend (or the demo backend imitating it). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** 403: the action needs an approval that is not on record (e.g. export before Gate 2, plan §16). */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** 409: the gate checklist is not cleared. */
  get isConflict(): boolean {
    return this.status === 409;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

/** Human message for any thrown value. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
