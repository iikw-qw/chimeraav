/**
 * Zustand store: уведомления.
 */

import { create } from 'zustand'
import api from '../api/client'

export interface Notification {
  id: string
  type: string
  title: string
  message?: string
  read: boolean
  data: Record<string, any>
  created_at: string
}

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  fetchNotifications: () => Promise<void>
  fetchUnreadCount: () => Promise<void>
  markAsRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,

  fetchNotifications: async () => {
    try {
      const { data } = await api.get('/notifications', { params: { limit: 50 } })
      set({ notifications: data })
    } catch { /* ignore */ }
  },

  fetchUnreadCount: async () => {
    try {
      const { data } = await api.get('/notifications/unread-count')
      set({ unreadCount: data.count })
    } catch { /* ignore */ }
  },

  markAsRead: async (id) => {
    await api.put(`/notifications/${id}/read`)
    set({
      notifications: get().notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
      unreadCount: Math.max(0, get().unreadCount - 1),
    })
  },

  markAllRead: async () => {
    await api.put('/notifications/read-all')
    set({
      notifications: get().notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })
  },
}))
