import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'
import type { CommentRow } from './useComments'

export const READY_QUERY_KEY = ['ready-for-welcome'] as const

async function fetchReady(): Promise<CommentRow[]> {
  const { data } = await api.get<CommentRow[]>('/api/comments/ready-for-welcome', {
    params: { limit: 500 },
  })
  return data
}

export function useReadyForWelcome() {
  const qc = useQueryClient()

  useEffect(() => {
    const unsub = ws.subscribe('comments', () => {
      qc.invalidateQueries({ queryKey: READY_QUERY_KEY })
    })
    return unsub
  }, [qc])

  return useQuery({
    queryKey: READY_QUERY_KEY,
    queryFn: fetchReady,
    refetchInterval: 15_000,
  })
}

export interface WelcomeProgress {
  account_id: string
  total: number
  sent: number
  failed: number
}

export function useWelcomeProgress() {
  const [progress, setProgress] = useState<WelcomeProgress | null>(null)
  useEffect(() => {
    return ws.subscribe('welcome_progress', (data) => {
      setProgress(data as WelcomeProgress)
    })
  }, [])
  return progress
}

export async function sendBulkWelcome(payload: {
  comment_ids: string[]
}): Promise<{ queued: number }> {
  const { data } = await api.post<{ queued: number }>(
    '/api/comments/bulk-welcome',
    payload,
  )
  return data
}
