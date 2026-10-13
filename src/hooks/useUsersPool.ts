import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'

export interface PoolUser {
  key: string
  source: 'comment' | 'dm'
  account_id: string
  platform: string
  username: string | null
  user_id: string | null
  preview: string | null
  created_at: string
  welcome_sent: boolean
}

export const USERS_POOL_QUERY_KEY = ['users-pool'] as const

export interface UsersPoolFilters {
  account_id?: string
  platform?: string
  source?: 'comment' | 'dm'
  limit?: number
}

async function fetchUsersPool(filters: UsersPoolFilters): Promise<PoolUser[]> {
  const { data } = await api.get<PoolUser[]>('/api/users-pool', {
    params: {
      account_id: filters.account_id || undefined,
      platform: filters.platform || undefined,
      source: filters.source || undefined,
      limit: filters.limit ?? 500,
    },
  })
  return data
}

export function useUsersPool(filters: UsersPoolFilters = {}) {
  const qc = useQueryClient()

  useEffect(() => {
    const unsubA = ws.subscribe('comments', () => {
      qc.invalidateQueries({ queryKey: USERS_POOL_QUERY_KEY })
    })
    const unsubB = ws.subscribe('incoming_messages', () => {
      qc.invalidateQueries({ queryKey: USERS_POOL_QUERY_KEY })
    })
    return () => {
      unsubA()
      unsubB()
    }
  }, [qc])

  return useQuery({
    queryKey: [...USERS_POOL_QUERY_KEY, filters],
    queryFn: () => fetchUsersPool(filters),
    refetchInterval: 20_000,
  })
}

export interface BulkWelcomePayload {
  keys?: string[]
  count?: number
  selection?: 'first' | 'random' | 'newest'
  account_id?: string
  message_text?: string
  delay_seconds?: number
}

export async function sendPoolBulkWelcome(
  payload: BulkWelcomePayload,
): Promise<{ queued: number; status: string }> {
  const { data } = await api.post<{ queued: number; status: string }>(
    '/api/users-pool/bulk-welcome',
    payload,
  )
  return data
}
