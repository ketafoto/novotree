/**
 * Extract a human-readable message from an Axios error.
 *
 * FastAPI errors have the shape { detail: string }.
 * Falls back to `fallback` when the server didn't send a detail field.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })
    ?.response?.data?.detail;
  return typeof detail === 'string' && detail.trim() ? detail : fallback;
}
