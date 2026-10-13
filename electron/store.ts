import Store from 'electron-store'

export interface StoreSchema {
  windowBounds: { width: number; height: number; x?: number; y?: number }
  sidebar: { collapsed: boolean; width: number }
  preferences: {
    minimizeToTray: boolean
    autoLaunch: boolean
    theme: 'dark' | 'light'
    language: string
  }
}

export const store = new Store<StoreSchema>({
  defaults: {
    windowBounds: { width: 1440, height: 900 },
    sidebar: { collapsed: false, width: 240 },
    preferences: {
      minimizeToTray: true,
      autoLaunch: false,
      theme: 'dark',
      language: 'ru',
    },
  },
})
