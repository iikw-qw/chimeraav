/**
 * Zustand store: аккаунты соцсетей.
 */

import { create } from 'zustand'
import api from '../api/client'

export interface Account {
  id: string
  user_id: string
  device_id?: string
  platform: string
  username: string
  password_encrypted?: string
  display_name?: string
  status: string
  proxy_url?: string
  followers_count: number
  following_count: number
  posts_count: number
  warmup_enabled: boolean
  login_status: string
  last_activity_at?: string
  created_at: string
  updated_at: string
}

interface AccountState {
  accounts: Account[]
  isLoading: boolean
  fetchAccounts: (params?: Record<string, any>) => Promise<void>
  addAccount: (data: Partial<Account>) => Promise<Account>
  updateAccount: (id: string, data: Partial<Account>) => Promise<void>
  deleteAccount: (id: string) => Promise<void>
}

export const useAccountStore = create<AccountState>((set, get) => ({
  accounts: [],
  isLoading: false,

  fetchAccounts: async (params) => {
    set({ isLoading: true })
    try {
      const { data } = await api.get('/accounts', { params })
      set({ accounts: data, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },

  addAccount: async (accountData) => {
    const { data } = await api.post('/accounts', accountData)
    set({ accounts: [data, ...get().accounts] })
    return data
  },

  updateAccount: async (id, accountData) => {
    const { data } = await api.put(`/accounts/${id}`, accountData)
    set({ accounts: get().accounts.map((a) => (a.id === id ? data : a)) })
  },

  deleteAccount: async (id) => {
    await api.delete(`/accounts/${id}`)
    set({ accounts: get().accounts.filter((a) => a.id !== id) })
  },
}))
