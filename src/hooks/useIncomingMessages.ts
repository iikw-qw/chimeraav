import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'

export interface IncomingMessage {
  id: string
  account_id: string
  sender_username?: string | null
  sender_user_id?: string | null
  message_text?: string | null
  platform: string
  notified_to_telegram: boolean
  notified_at?: string | null
  received_at: string
}

export const INCOMING_QUERY_KEY = ['incoming-messages'] as const
export const UNREAD_QUERY_KEY = ['incoming-unread'] as const

async function fetchIncoming(): Promise<IncomingMessage[]> {
  const { data } = await api.get<IncomingMessage[]>('/api/incoming-messages', {
    params: { limit: 200 },
  })
  return data
}

async function fetchUnread(): Promise<number> {
  const { data } = await api.get<{ unread: number }>('/api/incoming-messages/unread-count')
  return data.unread
}

export function useIncomingMessages() {
  const qc = useQueryClient()
  useEffect(() => {
    return ws.subscribe('incoming_messages', () => {
      qc.invalidateQueries({ queryKey: INCOMING_QUERY_KEY })
      qc.invalidateQueries({ queryKey: UNREAD_QUERY_KEY })
    })
  }, [qc])

  return useQuery({
    queryKey: INCOMING_QUERY_KEY,
    queryFn: fetchIncoming,
    refetchInterval: 15_000,
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: UNREAD_QUERY_KEY,
    queryFn: fetchUnread,
    refetchInterval: 15_000,
  })
}
