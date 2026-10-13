import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ws } from '../api/ws'

const IOS_KEY = ['ios-automation'] as const

interface ApiResult {
  ok: boolean
  [key: string]: unknown
}

async function post(path: string, body?: Record<string, unknown>): Promise<ApiResult> {
  const { data } = await api.post<ApiResult>(`/api/ios${path}`, body ?? {})
  return data
}

// ── Device Management ──────────────────────────────────────────

export function useScanDevices() {
  return useMutation({ mutationFn: () => post('/devices/scan') })
}

export function useLoadDevices() {
  return useMutation({ mutationFn: (devices: unknown[]) => post('/devices/load', { devices }) })
}

export function useAutostartDevices() {
  return useMutation({ mutationFn: () => post('/devices/autostart') })
}

export function useLaunchDevice() {
  return useMutation({
    mutationFn: ({ udid, wdaPort }: { udid: string; wdaPort?: number }) =>
      post(`/devices/${udid}/launch`, { wda_port: wdaPort ?? 8100 }),
  })
}

export function useStopDevice() {
  return useMutation({ mutationFn: (udid: string) => post(`/devices/${udid}/stop`) })
}

export function useRestartDevice() {
  return useMutation({ mutationFn: (udid: string) => post(`/devices/${udid}/restart`) })
}

export function usePairDevice() {
  return useMutation({
    mutationFn: ({ udid, p12File, password }: { udid: string; p12File?: string; password?: string }) =>
      post(`/devices/${udid}/pair`, { p12_file: p12File, password }),
  })
}

export function useSetupTunnel() {
  return useMutation({ mutationFn: (udid: string) => post(`/devices/${udid}/tunnel`) })
}

export function useStartWda() {
  return useMutation({
    mutationFn: ({ udid, wdaPort }: { udid: string; wdaPort?: number }) =>
      post(`/devices/${udid}/wda`, { wda_port: wdaPort ?? 8100 }),
  })
}

export function useWdaRecovery() {
  return useMutation({
    mutationFn: ({ udid, reason }: { udid: string; reason?: string }) =>
      post(`/devices/${udid}/wda-recovery`, { reason }),
  })
}

// ── System Cleanup ─────────────────────────────────────────────

export function useCleanupSystem() {
  return useMutation({ mutationFn: () => post('/cleanup') })
}

export function useCleanupDevice() {
  return useMutation({
    mutationFn: ({ udid, port }: { udid: string; port?: number }) =>
      post(`/cleanup/device/${udid}`, { port: port ?? 8100 }),
  })
}

// ── Alert Watcher ──────────────────────────────────────────────

export function useEnableAlertWatcher() {
  return useMutation({
    mutationFn: (deviceName: string) => post('/alert-watcher/enable', { device_name: deviceName }),
  })
}

export function useDisableAlertWatcher() {
  return useMutation({
    mutationFn: (deviceName: string) => post('/alert-watcher/disable', { device_name: deviceName }),
  })
}

export function useStartAlertWatcher() {
  return useMutation({
    mutationFn: ({ deviceName, wdaPort }: { deviceName: string; wdaPort?: number }) =>
      post('/alert-watcher/start', { device_name: deviceName, wda_port: wdaPort ?? 8100 }),
  })
}

export function useDismissAlerts() {
  return useMutation({
    mutationFn: ({ deviceName, wdaPort }: { deviceName: string; wdaPort?: number }) =>
      post('/alert-watcher/dismiss', { device_name: deviceName, wda_port: wdaPort ?? 8100 }),
  })
}

export function useAlertWatcherStatus() {
  return useQuery({
    queryKey: [...IOS_KEY, 'alert-watcher-status'],
    queryFn: async () => {
      const { data } = await api.get<{ active_devices: string[] }>('/api/ios/alert-watcher/status')
      return data
    },
    staleTime: 10_000,
  })
}

// ── OCR ────────────────────────────────────────────────────────

export function useOcrRecognize() {
  return useMutation({
    mutationFn: (data: { udid: string; wdaPort?: number }) =>
      post('/ocr/recognize', { udid: data.udid, wda_port: data.wdaPort ?? 8100 }),
  })
}

export function useOcrFindText() {
  return useMutation({
    mutationFn: (data: { udid: string; target: string; wdaPort?: number }) =>
      post('/ocr/find-text', { udid: data.udid, target: data.target, wda_port: data.wdaPort ?? 8100 }),
  })
}

export function useOcrStatus() {
  return useQuery({
    queryKey: [...IOS_KEY, 'ocr-status'],
    queryFn: async () => {
      const { data } = await api.get<{ ready: boolean }>('/api/ios/ocr/status')
      return data
    },
    staleTime: 10_000,
  })
}

// ── Telegram ───────────────────────────────────────────────────

export function useSendTelegram() {
  return useMutation({
    mutationFn: (data: { type?: string; device?: string; message?: string }) =>
      post('/telegram/send', data),
  })
}

// ── WebSocket-driven live state ────────────────────────────────

export function useIOSAutomationEvents(channel: string, onMessage?: (data: unknown) => void) {
  const qc = useQueryClient()

  useEffect(() => {
    if (!onMessage) return
    const unsub = ws.subscribe(channel, (payload) => {
      onMessage(payload)
      qc.invalidateQueries({ queryKey: IOS_KEY })
    })
    return unsub
  }, [channel, onMessage, qc])
}
