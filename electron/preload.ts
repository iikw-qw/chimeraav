import { contextBridge, ipcRenderer } from 'electron'

const chimera = {
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  },
  browser: {
    open: (url: string) => ipcRenderer.invoke('browser:open', url),
    close: () => ipcRenderer.invoke('browser:close'),
    back: () => ipcRenderer.invoke('browser:back'),
    forward: () => ipcRenderer.invoke('browser:forward'),
    reload: () => ipcRenderer.invoke('browser:reload'),
    toggle: () => ipcRenderer.invoke('browser:toggle'),
  },
  dialog: {
    openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
    openFiles: () => ipcRenderer.invoke('dialog:openFiles'),
    saveFile: (defaultPath?: string) => ipcRenderer.invoke('dialog:saveFile', defaultPath),
  },
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getDataPath: () => ipcRenderer.invoke('app:getDataPath'),
    openExternal: (url: string) => ipcRenderer.invoke('app:openExternal', url),
  },
  system: {
    info: () => ipcRenderer.invoke('system:info'),
    getAutostart: () => ipcRenderer.invoke('system:getAutostart'),
    setAutostart: (enabled: boolean) =>
      ipcRenderer.invoke('system:setAutostart', enabled),
    openDataDir: () => ipcRenderer.invoke('system:openDataDir'),
    revealPath: (target: string) => ipcRenderer.invoke('system:revealPath', target),
    ensureTools: () => ipcRenderer.invoke('system:ensureTools'),
    runElevated: (cmd: string, args?: string[]) =>
      ipcRenderer.invoke('system:runElevated', cmd, args),
    restartApp: () => ipcRenderer.invoke('system:restartApp'),
  },
  onNavigate: (cb: (route: string) => void) => {
    const listener = (_: unknown, route: string) => cb(route)
    ipcRenderer.on('navigate', listener)
    return () => ipcRenderer.off('navigate', listener)
  },
  onUpdate: (cb: (info: unknown) => void) => {
    const listener = (_: unknown, info: unknown) => cb(info)
    ipcRenderer.on('update', listener)
    return () => ipcRenderer.off('update', listener)
  },
}

contextBridge.exposeInMainWorld('chimera', chimera)
