import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export interface ProxyRow {
  id: string
  address: string
  port: number
  protocol: string
  username?: string | null
  password?: string | null
  country?: string | null
  is_active: boolean
  leak_check_passed: boolean
  last_checked?: string | null
}

export const PROXIES_QUERY_KEY = ['proxies'] as const

async function fetchProxies(): Promise<ProxyRow[]> {
  const { data } = await api.get<ProxyRow[]>('/api/proxies')
  return data
}

export function useProxies() {
  return useQuery({
    queryKey: PROXIES_QUERY_KEY,
    queryFn: fetchProxies,
    staleTime: 30_000,
  })
}

export async function createProxy(payload: Omit<ProxyRow, 'id' | 'leak_check_passed' | 'last_checked'>) {
  const { data } = await api.post<ProxyRow>('/api/proxies', payload)
  return data
}

export async function updateProxy(id: string, payload: Partial<ProxyRow>) {
  const { data } = await api.put<ProxyRow>(`/api/proxies/${id}`, payload)
  return data
}

export async function deleteProxy(id: string) {
  await api.delete(`/api/proxies/${id}`)
}

export async function checkAllProxies() {
  const { data } = await api.post<{ status: string }>('/api/proxies/check-all')
  return data
}
