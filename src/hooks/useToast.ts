import { create } from 'zustand'

export type ToastStatus = 'success' | 'warning' | 'danger' | 'info'

export interface Toast {
  id: string
  status: ToastStatus
  title?: string
  message: string
  duration: number
}

interface ToastStore {
  toasts: Toast[]
  push: (toast: Omit<Toast, 'id' | 'duration'> & { duration?: number }) => string
  dismiss: (id: string) => void
  clear: () => void
}

const DEFAULT_DURATION = 5000

export const useToast = create<ToastStore>((set, get) => ({
  toasts: [],
  push: (toast) => {
    const id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`
    const duration = toast.duration ?? DEFAULT_DURATION
    set((s) => ({ toasts: [...s.toasts, { ...toast, id, duration }] }))
    if (duration > 0) {
      setTimeout(() => get().dismiss(id), duration)
    }
    return id
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}))

export const toast = {
  success: (message: string, title?: string) =>
    useToast.getState().push({ status: 'success', message, title }),
  warning: (message: string, title?: string) =>
    useToast.getState().push({ status: 'warning', message, title }),
  danger: (message: string, title?: string) =>
    useToast.getState().push({ status: 'danger', message, title }),
  info: (message: string, title?: string) =>
    useToast.getState().push({ status: 'info', message, title }),
}
