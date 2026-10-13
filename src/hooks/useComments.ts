import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'

export interface CommentMetrics {
  followers?: number
  following?: number
  posts?: number
  account_age_days?: number
  ratio?: number
  has_avatar?: boolean
  verified?: boolean
}

export interface CommentAnalysis {
  quality?: string
  reason?: string
}

export interface CommentRow {
  id: string
  account_id: string
  platform: string
  post_id_external?: string | null
  commenter_username?: string | null
  commenter_user_id?: string | null
  commenter_gender: string
  commenter_language?: string | null
  commenter_metrics?: CommentMetrics | null
  commenter_profile_analysis?: CommentAnalysis | null
  comment_text?: string | null
  reply_text?: string | null
  reply_status: string
  welcome_sent: boolean
  created_at: string
}

export interface CommentsQueryParams {
  platform?: string
  language?: string
  reply_status?: string
  gender?: string
  welcome_sent?: boolean
  limit?: number
}

export const COMMENTS_QUERY_KEY = ['comments'] as const

async function fetchComments(params: CommentsQueryParams): Promise<CommentRow[]> {
  const { data } = await api.get<CommentRow[]>('/api/comments', {
    params: { limit: 500, ...params },
  })
  return data
}

export function useComments(params: CommentsQueryParams = {}) {
  const qc = useQueryClient()

  useEffect(() => {
    const unsub = ws.subscribe('comments', () => {
      qc.invalidateQueries({ queryKey: COMMENTS_QUERY_KEY })
    })
    return unsub
  }, [qc])

  return useQuery({
    queryKey: [...COMMENTS_QUERY_KEY, params],
    queryFn: () => fetchComments(params),
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

export function commentsExportUrl(params: CommentsQueryParams = {}): string {
  const sp = new URLSearchParams()
  if (params.platform) sp.set('platform', params.platform)
  if (params.gender) sp.set('gender', params.gender)
  const qs = sp.toString()
  const base = `${api.defaults.baseURL ?? ''}/api/comments/export`
  return qs ? `${base}?${qs}` : base
}

export async function sendWelcomeForComment(commentId: string): Promise<CommentRow> {
  const { data } = await api.post<CommentRow>(`/api/comments/${commentId}/send-welcome`)
  return data
}
