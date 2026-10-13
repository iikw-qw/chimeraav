import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'

export interface Device {
  id: string
  unique_code?: string | null
  name: string
  platform: string
  status: string
  phone_number?: string | null
  ip_address?: string | null
  serial?: string | null
  battery_level?: number | null
  proxy_id?: string | null
  group_name?: string | null
  is_master: boolean
  last_heartbeat?: string | null
  created_at: string
}

export const DEVICES_QUERY_KEY = ['devices'] as const

async function fetchDevices(): Promise<Device[]> {
  const { data } = await api.get<Device[]>('/api/devices', {
    params: { limit: 500 },
  })
  if (Array.isArray(data) && data.length === 0) {
    const fallback = await api.get<Device[]>('/api/devices/adb')
    if (Array.isArray(fallback.data) && fallback.data.length > 0) {
      return fallback.data
    }
  }
  return data
}

export function useDevices() {
  const qc = useQueryClient()

  useEffect(() => {
    const unsub = ws.subscribe('devices', () => {
      qc.invalidateQueries({ queryKey: DEVICES_QUERY_KEY })
    })
    return unsub
  }, [qc])

  return useQuery({
    queryKey: DEVICES_QUERY_KEY,
    queryFn: fetchDevices,
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export async function setMaster(deviceId: string): Promise<Device> {
  const { data } = await api.put<Device>(`/api/devices/${deviceId}/set-master`, {
    is_master: true,
  })
  return data
}

export function screenshotUrl(deviceId: string): string {
  return `${api.defaults.baseURL ?? ''}/api/devices/${deviceId}/screenshot`
}

export function streamUrl(
  deviceId: string,
  opts: { fps?: number; quality?: number; maxWidth?: number } = {},
): string {
  const params = new URLSearchParams()
  if (opts.fps) params.set('fps', String(opts.fps))
  if (opts.quality) params.set('quality', String(opts.quality))
  if (opts.maxWidth) params.set('max_width', String(opts.maxWidth))
  const qs = params.toString()
  return `${api.defaults.baseURL ?? ''}/api/devices/${deviceId}/stream${qs ? `?${qs}` : ''}`
}

export interface DeviceInfo {
  id: string
  platform: string
  status: string
  model?: string | null
  manufacturer?: string | null
  brand?: string | null
  android_version?: string | null
  sdk?: string | null
  battery_level?: number | null
  resolution?: string | null
}

export async function getDeviceInfo(deviceId: string): Promise<DeviceInfo> {
  const { data } = await api.get<DeviceInfo>(`/api/devices/${deviceId}/info`)
  return data
}

export async function rebootDevice(deviceId: string): Promise<void> {
  await api.post(`/api/devices/${deviceId}/reboot`)
}

export async function disconnectDevice(deviceId: string): Promise<void> {
  await api.post(`/api/devices/${deviceId}/disconnect`)
}

export async function pauseDevice(deviceId: string, paused: boolean): Promise<void> {
  await api.post(`/api/devices/${deviceId}/pause`, { paused })
}

export async function tapDevice(deviceId: string, x: number, y: number): Promise<void> {
  await api.post(`/api/devices/${deviceId}/tap`, { x, y })
}

export async function swipeDevice(
  deviceId: string,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  durationMs = 300,
): Promise<void> {
  await api.post(`/api/devices/${deviceId}/swipe`, {
    x1,
    y1,
    x2,
    y2,
    duration_ms: durationMs,
  })
}

export async function keyDevice(deviceId: string, keycode: number | string): Promise<void> {
  await api.post(`/api/devices/${deviceId}/key`, { keycode })
}

export async function typeDevice(deviceId: string, text: string): Promise<void> {
  await api.post(`/api/devices/${deviceId}/text`, { text })
}

export async function deleteDevice(deviceId: string): Promise<void> {
  await api.delete(`/api/devices/${deviceId}`)
}

export async function humanTapDevice(deviceId: string, x: number, y: number): Promise<void> {
  await api.post(`/api/devices/${deviceId}/human_tap`, { x, y })
}

export async function humanSwipeDevice(
  deviceId: string,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): Promise<void> {
  await api.post(`/api/devices/${deviceId}/human_swipe`, { x1, y1, x2, y2 })
}

export async function humanTypeDevice(
  deviceId: string,
  text: string,
  clearFirst = false,
): Promise<void> {
  await api.post(`/api/devices/${deviceId}/human_type`, { text, clear_first: clearFirst })
}

export async function setCursorTrail(deviceId: string, enabled: boolean): Promise<void> {
  await api.post(`/api/devices/${deviceId}/cursor_trail`, { enabled })
}

export async function refreshDeviceIp(
  deviceId: string,
): Promise<{ device_id: string; ip_address: string | null }> {
  const { data } = await api.post(`/api/devices/${deviceId}/refresh-ip`)
  return data
}

export interface WarmupKickoff {
  duration_seconds?: number
  account_id?: string | null
  scroll_weight?: number
  profile_visit_weight?: number
  like_weight?: number
  follow_weight?: number
}

export async function startWarmup(
  deviceId: string,
  payload: WarmupKickoff = {},
): Promise<{ ok: boolean; device_id: string; duration_seconds: number }> {
  const { data } = await api.post(`/api/devices/${deviceId}/warmup`, {
    duration_seconds: 300,
    ...payload,
  })
  return data
}

export async function galleryPush(
  deviceId: string,
  paths: string[],
): Promise<{ ok: boolean; device_paths: string[]; count: number }> {
  const { data } = await api.post(`/api/devices/${deviceId}/gallery/push`, { paths })
  return data
}

export async function galleryCleanup(
  deviceId: string,
): Promise<{ ok: boolean; removed: number }> {
  const { data } = await api.post(`/api/devices/${deviceId}/gallery/cleanup`)
  return data
}

export async function startStreaming(deviceId: string): Promise<{ ok: boolean; message: string }> {
  const { data } = await api.post(`/api/devices/${deviceId}/start-streaming`)
  return data
}

export interface StartStreamingAllResult {
  total: number
  results: Array<{ device: string; status: string; message: string }>
}

export async function startStreamingAll(): Promise<StartStreamingAllResult> {
  const { data } = await api.post<StartStreamingAllResult>('/api/devices/start-streaming-all')
  return data
}

export async function stopStreaming(deviceId: string): Promise<{ ok: boolean }> {
  const { data } = await api.post(`/api/devices/${deviceId}/stop-streaming`)
  return data
}

export async function stopStreamingAll(): Promise<{ ok: boolean }> {
  const { data } = await api.post('/api/devices/stop-streaming-all')
  return data
}

export const installAgent = startStreaming
export type InstallAllResult = StartStreamingAllResult
export const installAgentAll = startStreamingAll

export interface CursorEvent {
  device_id: string
  kind: 'tap' | 'swipe'
  x?: number | null
  y?: number | null
  duration_ms?: number | null
  waypoints?: Array<{ x: number; y: number; t_ms: number }> | null
}
