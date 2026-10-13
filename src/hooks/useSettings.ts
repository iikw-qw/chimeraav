import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export type SettingsMap = Record<string, unknown>

export const SETTINGS_QUERY_KEY = ['settings'] as const

async function fetchSettings(): Promise<SettingsMap> {
  const { data } = await api.get<SettingsMap>('/api/settings')
  return data
}

async function putSettings(items: SettingsMap): Promise<SettingsMap> {
  const { data } = await api.put<SettingsMap>('/api/settings', { items })
  return data
}

export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: fetchSettings,
    staleTime: 30_000,
  })
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: putSettings,
    onSuccess: () => qc.invalidateQueries({ queryKey: SETTINGS_QUERY_KEY }),
  })
}
