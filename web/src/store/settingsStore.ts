/**
 * Zustand store: настройки (глобальные + пользовательские).
 */

import { create } from 'zustand'
import api from '../api/client'

interface SettingsState {
  settings: Record<string, any>
  isLoading: boolean
  fetchSettings: () => Promise<void>
  updateSetting: (key: string, value: any, isGlobal?: boolean) => Promise<void>
  getSetting: (key: string, defaultValue?: any) => any
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: {},
  isLoading: false,

  fetchSettings: async () => {
    set({ isLoading: true })
    try {
      const { data } = await api.get('/settings')
      const settingsMap: Record<string, any> = {}
      for (const s of data) {
        settingsMap[s.key] = s.value
      }
      set({ settings: settingsMap, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },

  updateSetting: async (key, value, isGlobal = false) => {
    await api.put(`/settings?is_global=${isGlobal}`, { key, value })
    set({ settings: { ...get().settings, [key]: value } })
  },

  getSetting: (key, defaultValue = null) => {
    return get().settings[key] ?? defaultValue
  },
}))
