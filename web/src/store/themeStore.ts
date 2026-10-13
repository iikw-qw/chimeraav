/**
 * Zustand store: тема (dark/light).
 */

import { create } from 'zustand'

interface ThemeState {
  isDark: boolean
  toggle: () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  isDark: localStorage.getItem('chimera_theme') === 'dark',

  toggle: () => {
    const newDark = !get().isDark
    localStorage.setItem('chimera_theme', newDark ? 'dark' : 'light')
    if (newDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    set({ isDark: newDark })
  },
}))
