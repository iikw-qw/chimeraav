import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export interface TemplateRow {
  id: string
  name: string
  style: 'welcome' | 'intriguing' | 'friendly' | 'custom'
  template_text: string
  language: string
  is_active: boolean
  created_at: string
}

export const TEMPLATES_QUERY_KEY = ['templates'] as const

async function fetchTemplates(): Promise<TemplateRow[]> {
  const { data } = await api.get<TemplateRow[]>('/api/templates')
  return data
}

export function useTemplates() {
  return useQuery({
    queryKey: TEMPLATES_QUERY_KEY,
    queryFn: fetchTemplates,
    staleTime: 30_000,
  })
}

export async function createTemplate(payload: Omit<TemplateRow, 'id' | 'created_at'>) {
  const { data } = await api.post<TemplateRow>('/api/templates', payload)
  return data
}

export async function updateTemplate(id: string, payload: Partial<TemplateRow>) {
  const { data } = await api.put<TemplateRow>(`/api/templates/${id}`, payload)
  return data
}

export async function deleteTemplate(id: string) {
  await api.delete(`/api/templates/${id}`)
}
