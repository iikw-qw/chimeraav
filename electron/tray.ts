import { app, Menu, Tray, BrowserWindow, nativeImage } from 'electron'
import path from 'path'
import fs from 'fs'

let tray: Tray | null = null
let paused = false
let messages = 0
let devices = 0
let getWinRef: (() => BrowserWindow | null) | null = null

function resolveIcon(): Electron.NativeImage {
  const candidates = [
    path.join(process.resourcesPath || '', 'icon.png'),
    path.join(__dirname, '..', 'resources', 'icon.png'),
    path.join(process.cwd(), 'resources', 'icon.png'),
  ]
  for (const p of candidates) {
    if (p && fs.existsSync(p)) {
      const img = nativeImage.createFromPath(p)
      if (!img.isEmpty()) return img
    }
  }
  return nativeImage.createEmpty()
}

export function createTray(getWin: () => BrowserWindow | null): void {
  getWinRef = getWin
  tray = new Tray(resolveIcon())
  tray.setToolTip('Chimera')
  rebuild()

  tray.on('click', () => {
    const win = getWin()
    if (!win) return
    if (win.isVisible()) win.hide()
    else {
      win.show()
      win.focus()
    }
  })
}

function rebuild(): void {
  if (!tray) return
  const menu = Menu.buildFromTemplate([
    {
      label: 'Открыть',
      click: () => {
        const win = getWinRef?.()
        win?.show()
        win?.focus()
      },
    },
    { label: `Сообщений: ${messages}`, enabled: false },
    { label: `Устройств: ${devices}`, enabled: false },
    { type: 'separator' },
    {
      label: paused ? 'Возобновить' : 'Пауза',
      click: () => {
        paused = !paused
        rebuild()
      },
    },
    { type: 'separator' },
    {
      label: 'Выход',
      click: () => {
        ;(app as unknown as { isQuitting?: boolean }).isQuitting = true
        app.quit()
      },
    },
  ])
  tray.setContextMenu(menu)
}

export function setTrayCounts(m: number, d: number): void {
  messages = m
  devices = d
  rebuild()
}

export function isPaused(): boolean {
  return paused
}

export function destroyTray(): void {
  tray?.destroy()
  tray = null
  getWinRef = null
}
