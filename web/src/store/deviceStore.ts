/**
 * Zustand store: устройства.
 */

import { create } from 'zustand'
import api from '../api/client'

export interface Device {
  id: string
  user_id: string
  name: string
  device_type: 'android' | 'ios'
  serial_number?: string
  ip_address?: string
  external_ip?: string
  vpn_active: boolean
  proxy_info: Record<string, any>
  status: string
  battery_level?: number
  model?: string
  manufacturer?: string
  os_version?: string
  screen_resolution?: string
  ram_mb?: number
  temperature?: number
  last_seen_at?: string
  created_at: string
  updated_at: string
}

interface DeviceState {
  devices: Device[]
  isLoading: boolean
  fetchDevices: (params?: Record<string, any>) => Promise<void>
  addDevice: (data: Partial<Device>) => Promise<Device>
  updateDevice: (id: string, data: Partial<Device>) => Promise<void>
  deleteDevice: (id: string) => Promise<void>
  sendCommand: (id: string, command: Record<string, any>) => Promise<void>
}

export const useDeviceStore = create<DeviceState>((set, get) => ({
  devices: [],
  isLoading: false,

  fetchDevices: async (params) => {
    set({ isLoading: true })
    try {
      const { data } = await api.get('/devices', { params })
      set({ devices: data, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },

  addDevice: async (deviceData) => {
    const { data } = await api.post('/devices', deviceData)
    set({ devices: [data, ...get().devices] })
    return data
  },

  updateDevice: async (id, deviceData) => {
    const { data } = await api.put(`/devices/${id}`, deviceData)
    set({ devices: get().devices.map((d) => (d.id === id ? data : d)) })
  },

  deleteDevice: async (id) => {
    await api.delete(`/devices/${id}`)
    set({ devices: get().devices.filter((d) => d.id !== id) })
  },

  sendCommand: async (id, command) => {
    await api.post(`/devices/${id}/command`, command)
  },
}))
