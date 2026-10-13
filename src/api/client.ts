import axios, { AxiosError } from 'axios'
import { toast } from '../hooks/useToast'

export const API_BASE_URL =
  (window as any).__CHIMERA_API_URL__ ||
  (typeof process !== 'undefined' && (process as any).env?.CHIMERA_API_URL) ||
  'http://localhost:17842'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
})

// Let axios auto-pick Content-Type: multipart/form-data (with boundary) for
// FormData bodies, application/json for plain objects. A global default
// breaks multipart uploads because it prevents the boundary from being set.

type FastApiDetailItem = { msg?: string; loc?: unknown; type?: string }
type FastApiErrorBody = { detail?: string | FastApiDetailItem[] | FastApiDetailItem }

function formatDetail(detail: unknown): string | null {
  if (detail == null) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (typeof d === 'string') return d
        if (d && typeof d === 'object') {
          const item = d as FastApiDetailItem
          const loc = Array.isArray(item.loc)
            ? (item.loc as unknown[]).join('.')
            : undefined
          return loc && item.msg ? `${loc}: ${item.msg}` : item.msg ?? JSON.stringify(item)
        }
        return String(d)
      })
      .join('; ')
  }
  if (typeof detail === 'object') {
    const item = detail as FastApiDetailItem
    if (item.msg) return item.msg
    try {
      return JSON.stringify(detail)
    } catch {
      return null
    }
  }
  return String(detail)
}

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response) {
      const status = err.response.status
      const data = err.response.data as FastApiErrorBody | string | undefined
      const detail =
        typeof data === 'string'
          ? data
          : formatDetail(data?.detail) ||
            err.message ||
            `Request failed (${status})`

      if (status === 500) {
        toast.danger('Server error. Check logs.')
      }

      return Promise.reject(new Error(detail))
    }
    if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
      toast.danger('Cannot connect to sidecar. Is it running?')
      return Promise.reject(
        new Error(`Нет связи с backend (${API_BASE_URL}). Проверьте что сервер запущен.`),
      )
    }
    return Promise.reject(err instanceof Error ? err : new Error(String(err)))
  },
)

export async function waitForBackend(
  maxAttempts = 24,
  intervalMs = 500,
): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const r = await api.get('/health', { timeout: 1500 })
      if (r.status === 200) return true
    } catch {
      // keep polling
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  return false
}
