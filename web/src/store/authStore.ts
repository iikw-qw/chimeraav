/**
 * Zustand store: авторизация.
 */

import { create } from 'zustand'
import api from '../api/client'

interface User {
  id: string
  email: string
  telegram_username?: string
  telegram_verified: boolean
  verification_code?: string
  onboarding_completed: boolean
  app_version?: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, telegram_username?: string) => Promise<string>
  logout: () => void
  checkAuth: () => Promise<void>
  verifyTelegram: (code: string) => Promise<void>
  setOnboardingCompleted: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('chimera_token'),
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('chimera_token', data.access_token)
      localStorage.setItem('chimera_user', JSON.stringify(data.user))
      set({ user: data.user, token: data.access_token, isAuthenticated: true, isLoading: false })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Login failed'
      set({ error: msg, isLoading: false })
      throw new Error(msg)
    }
  },

  register: async (email, password, telegram_username) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post('/auth/register', { email, password, telegram_username })
      localStorage.setItem('chimera_token', data.access_token)
      localStorage.setItem('chimera_user', JSON.stringify(data.user))
      set({ user: data.user, token: data.access_token, isAuthenticated: true, isLoading: false })
      return data.verification_code || data.user?.verification_code || ''
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Registration failed'
      set({ error: msg, isLoading: false })
      throw new Error(msg)
    }
  },

  logout: () => {
    localStorage.removeItem('chimera_token')
    localStorage.removeItem('chimera_user')
    set({ user: null, token: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('chimera_token')
    if (!token) {
      set({ isLoading: false, isAuthenticated: false })
      return
    }
    try {
      const { data } = await api.get('/auth/me')
      set({ user: data, isAuthenticated: true, isLoading: false })
    } catch {
      localStorage.removeItem('chimera_token')
      localStorage.removeItem('chimera_user')
      set({ user: null, token: null, isAuthenticated: false, isLoading: false })
    }
  },

  verifyTelegram: async (code) => {
    await api.post('/auth/verify-telegram', { code })
    const user = get().user
    if (user) {
      set({ user: { ...user, telegram_verified: true } })
    }
  },

  setOnboardingCompleted: () => {
    const user = get().user
    if (user) {
      set({ user: { ...user, onboarding_completed: true } })
    }
  },
}))
