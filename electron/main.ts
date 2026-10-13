import { app, BrowserWindow } from 'electron'
import path from 'path'
import { startPython, stopPython } from './sidecar'
import { createTray, destroyTray } from './tray'
import { registerIPC } from './ipc-handlers'
import { createMenu } from './menu'
import { store } from './store'
import { BrowserViewManager } from './browser-view'
import { applyAutostart, ensureToolsInstalled } from './system'

// Treat as dev only if explicitly requested. `app.isPackaged` is false even for
// `npm run start` (loose electron .), so it can't be the signal — otherwise we'd
// try to load the Vite dev server at localhost:5173 in production and the
// window stays black.
const isDev =
  process.env.NODE_ENV === 'development' || process.argv.includes('--dev')

let mainWindow: BrowserWindow | null = null
let browserView: BrowserViewManager | null = null

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
  process.exit(0)
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    if (!mainWindow.isVisible()) mainWindow.show()
    mainWindow.focus()
  }
})

function createWindow(): void {
  const bounds = store.get('windowBounds')

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    minWidth: 1100,
    minHeight: 700,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#06070B',
    show: false,
    webPreferences: {
      webSecurity: false,
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  browserView = new BrowserViewManager(mainWindow)

  const saveBounds = (): void => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (mainWindow.isMaximized() || mainWindow.isMinimized() || mainWindow.isFullScreen()) return
    store.set('windowBounds', mainWindow.getBounds())
  }
  mainWindow.on('resize', saveBounds)
  mainWindow.on('move', saveBounds)

  mainWindow.on('close', (e) => {
    const prefs = store.get('preferences')
    if (prefs?.minimizeToTray && !(app as unknown as { isQuitting?: boolean }).isQuitting) {
      e.preventDefault()
      mainWindow?.hide()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
    browserView = null
  })
}

app.whenReady().then(async () => {
  try {
    await startPython(isDev)
  } catch (err) {
    console.error('[chimera] Failed to start Python sidecar:', err)
  }

  createWindow()
  createTray(() => mainWindow)
  createMenu()
  registerIPC(
    () => mainWindow,
    () => browserView,
  )

  const prefs = store.get('preferences')
  if (prefs?.autoLaunch !== undefined) {
    try {
      applyAutostart(prefs.autoLaunch === true)
    } catch (err) {
      console.warn('[chimera] applyAutostart failed:', err)
    }
  }

  // Non-blocking: install missing platform tools (ADB / libimobiledevice)
  // once the sidecar is healthy.
  void ensureToolsInstalled()
})

app.on('window-all-closed', () => {
  const prefs = store.get('preferences')
  if (!prefs?.minimizeToTray && process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  ;(app as unknown as { isQuitting?: boolean }).isQuitting = true
})

app.on('will-quit', async () => {
  destroyTray()
  await stopPython()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
