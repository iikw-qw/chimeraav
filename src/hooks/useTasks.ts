import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export interface TaskRow {
  id: string
  device_id: string
  account_id: string | null
  task_type: string
  status: string
  priority: number
  payload: Record<string, unknown> | null
  retry_count: number
  scheduled_at: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
}

export const TASKS_QUERY_KEY = ['tasks'] as const
export const DLQ_QUERY_KEY = ['tasks', 'dlq'] as const

async function fetchTasks(): Promise<TaskRow[]> {
  const { data } = await api.get<TaskRow[]>('/api/tasks', { params: { limit: 500 } })
  return data
}

async function fetchDLQ(): Promise<TaskRow[]> {
  const { data } = await api.get<TaskRow[]>('/api/tasks/dlq', { params: { limit: 200 } })
  return data
}

export function useTasks() {
  return useQuery({
    queryKey: TASKS_QUERY_KEY,
    queryFn: fetchTasks,
    refetchInterval: 10_000,
  })
}

export function useDLQ() {
  return useQuery({
    queryKey: DLQ_QUERY_KEY,
    queryFn: fetchDLQ,
    refetchInterval: 15_000,
  })
}

export async function retryTask(id: string): Promise<TaskRow> {
  const { data } = await api.post<TaskRow>(`/api/tasks/${id}/retry`)
  return data
}

export async function deleteTask(id: string): Promise<void> {
  await api.delete(`/api/tasks/${id}`)
}

export async function publishNow(payload: {
  device_id: string
  account_id?: string
  dataset_id: string
  photo_count?: number
}): Promise<TaskRow> {
  const { data } = await api.post<TaskRow>('/api/tasks/publish-now', payload)
  return data
}

export interface BatchScheduleIn {
  device_ids: string[]
  account_id?: string | null
  dataset_id: string
  platform?: string
  days?: number
  posts_per_day?: number
  start_hour?: number
  end_hour?: number
  photo_count?: number
}

export async function scheduleBatch(
  payload: BatchScheduleIn,
): Promise<{ scheduled: number; first: string | null; last: string | null }> {
  const { data } = await api.post('/api/tasks/schedule-batch', payload)
  return data
}
