import { useEffect } from 'react'
import { ws } from '../api/ws'
import { toast } from './useToast'

type Level = 'success' | 'danger' | 'warning' | 'info'

interface NotificationPayload {
  level?: Level
  title?: string
  message?: string
}

export function useNotificationsBridge(): void {
  useEffect(() => {
    const unsub = ws.subscribe('notifications', (payload) => {
      const p = payload as NotificationPayload
      const level: Level = p.level ?? 'info'
      const message = p.message ?? ''
      const title = p.title
      if (level === 'success') toast.success(message, title)
      else if (level === 'danger') toast.danger(message, title)
      else if (level === 'warning') toast.warning(message, title)
      else toast.info(message, title)
    })
    return unsub
  }, [])
}
