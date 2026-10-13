import { Menu, BrowserWindow, app, shell } from 'electron'

export function createMenu(): void {
  const navItems: Electron.MenuItemConstructorOptions[] = Array.from({ length: 9 }).map(
    (_, i) => ({
      label: `Раздел ${i + 1}`,
      accelerator: `CmdOrCtrl+${i + 1}`,
      click: () => {
        const win = BrowserWindow.getFocusedWindow()
        win?.webContents.send('navigate', `/section/${i + 1}`)
      },
    }),
  )

  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: 'File',
      submenu: [
        { role: 'quit', label: 'Выход' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { type: 'separator' },
        ...navItems,
      ],
    },
    {
      label: 'Help',
      submenu: [
        { label: `Версия ${app.getVersion()}`, enabled: false },
        {
          label: 'GitHub',
          click: () => shell.openExternal('https://github.com'),
        },
      ],
    },
  ]

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}
