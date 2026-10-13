import { ipcMain, dialog, shell, app, BrowserWindow } from 'electron'
import { BrowserViewManager } from './browser-view'
import {
  applyAutostart,
  ensureToolsInstalled,
  getAutostart,
  getSystemInfo,
  openDataDirectory,
  revealInExplorer,
  runElevated,
} from './system'

export function registerIPC(
  getWin: () => BrowserWindow | null,
  getBrowser: () => BrowserViewManager | null,
): void {
  ipcMain.handle('window:minimize', () => {
    getWin()?.minimize()
  })
  ipcMain.handle('window:maximize', () => {
    const w = getWin()
    if (!w) return
    if (w.isMaximized()) w.unmaximize()
    else w.maximize()
  })
  ipcMain.handle('window:close', () => {
    getWin()?.close()
  })
  ipcMain.handle('window:isMaximized', () => getWin()?.isMaximized() ?? false)

  ipcMain.handle('browser:open', async (_e, url: string) => {
    await getBrowser()?.openUrl(url)
  })
  ipcMain.handle('browser:close', () => {
    getBrowser()?.close()
  })
  ipcMain.handle('browser:back', () => {
    getBrowser()?.goBack()
  })
  ipcMain.handle('browser:forward', () => {
    getBrowser()?.goForward()
  })
  ipcMain.handle('browser:reload', () => {
    getBrowser()?.reload()
  })
  ipcMain.handle('browser:toggle', () => {
    getBrowser()?.toggle()
  })

  ipcMain.handle('dialog:openFolder', async () => {
    const win = getWin()
    if (!win) return null
    const r = await dialog.showOpenDialog(win, { properties: ['openDirectory'] })
    return r.canceled ? null : r.filePaths[0]
  })
  ipcMain.handle('dialog:openFiles', async () => {
    const win = getWin()
    if (!win) return null
    const r = await dialog.showOpenDialog(win, {
      properties: ['openFile', 'multiSelections'],
    })
    return r.canceled ? null : r.filePaths
  })
  ipcMain.handle('dialog:saveFile', async (_e, defaultPath?: string) => {
    const win = getWin()
    if (!win) return null
    const r = await dialog.showSaveDialog(win, { defaultPath })
    return r.canceled ? null : r.filePath ?? null
  })

  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getDataPath', () => app.getPath('userData'))
  ipcMain.handle('app:openExternal', async (_e, url: string) => {
    await shell.openExternal(url)
  })

  ipcMain.handle('system:info', () => getSystemInfo())
  ipcMain.handle('system:getAutostart', () => getAutostart())
  ipcMain.handle('system:setAutostart', (_e, enabled: boolean) => {
    applyAutostart(enabled)
    return getAutostart()
  })
  ipcMain.handle('system:openDataDir', async () => {
    await openDataDirectory()
  })
  ipcMain.handle('system:revealPath', (_e, target: string) => {
    revealInExplorer(target)
  })
  ipcMain.handle('system:ensureTools', async () => {
    await ensureToolsInstalled()
  })
  ipcMain.handle('system:runElevated', async (_e, cmd: string, args?: string[]) => {
    return await runElevated(cmd, args ?? [])
  })
  ipcMain.handle('system:restartApp', () => {
    app.relaunch()
    app.exit(0)
  })
}
