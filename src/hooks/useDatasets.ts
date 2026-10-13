import { useQuery } from '@tanstack/react-query'
import { api, API_BASE_URL } from '../api/client'

export interface DatasetFile {
  name: string
  size: number
}

export interface DatasetFilesResponse {
  dataset_id: string
  photos: DatasetFile[]
  videos: DatasetFile[]
}

export interface DatasetRow {
  id: string
  name: string
  path: string
  photo_count: number
  video_count: number
  wear_map?: Record<string, number> | null
  linked_device_id?: string | null
  metadata_cleaned: boolean
  created_at: string
}

export const DATASETS_QUERY_KEY = ['datasets'] as const

async function fetchDatasets(): Promise<DatasetRow[]> {
  const { data } = await api.get<DatasetRow[]>('/api/datasets')
  return data
}

export function useDatasets() {
  return useQuery({
    queryKey: DATASETS_QUERY_KEY,
    queryFn: fetchDatasets,
    staleTime: 30_000,
  })
}

export async function getDataset(id: string): Promise<DatasetRow> {
  const { data } = await api.get<DatasetRow>(`/api/datasets/${id}`)
  return data
}

export async function deleteDataset(id: string): Promise<void> {
  await api.delete(`/api/datasets/${id}`)
}

export async function cleanDatasetMetadata(id: string): Promise<void> {
  await api.post(`/api/datasets/${id}/clean-metadata`)
}

export async function linkDataset(id: string, deviceId: string): Promise<DatasetRow> {
  const { data } = await api.post<DatasetRow>(`/api/datasets/${id}/link/${deviceId}`)
  return data
}

export async function unlinkDataset(id: string): Promise<DatasetRow> {
  const { data } = await api.delete<DatasetRow>(`/api/datasets/${id}/unlink`)
  return data
}

export async function listDatasetFiles(id: string): Promise<DatasetFilesResponse> {
  const { data } = await api.get<DatasetFilesResponse>(`/api/datasets/${id}/files`)
  return data
}

export function useDatasetFiles(id: string | null | undefined) {
  return useQuery({
    queryKey: ['dataset-files', id] as const,
    queryFn: () => listDatasetFiles(id as string),
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function datasetFileUrl(id: string, filename: string): string {
  return `${API_BASE_URL}/api/datasets/${id}/file/${encodeURIComponent(filename)}`
}

export async function uploadDataset(
  name: string,
  files: File[],
  linkedDeviceId?: string,
): Promise<DatasetRow> {
  const form = new FormData()
  form.append('name', name)
  if (linkedDeviceId) form.append('linked_device_id', linkedDeviceId)
  for (const f of files) form.append('files', f)
  const { data } = await api.post<DatasetRow>('/api/datasets/upload', form)
  return data
}
