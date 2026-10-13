import { app, Notification, shell } from 'electron'
import { spawn } from 'child_process'
import http from 'http'
import path from 'path'
import fs from 'fs'
import os from 'os'

const PORT = 17842

interface ToolsStatus {
  adb: { available: boolean; path: string | null }
  ios: { available: boolean; path: string | null }
  tools_root: string
}

function getJson<T>(urlPath: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: 'localhost', port: PORT, path: urlPath, timeout: 5000, family: 4 },
      (res) => {
        const chunks: Buffer[] = []
        res.on('data', (c) => chunks.push(c))
        res.on('end', () => {
          try {
            resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')) as T)
          } catch (err) {
            reject(err)
          }
        })
      },
    )
    req.on('error', reject)
    req.on('timeout', () => {
      req.destroy()
      reject(new Error('timeout'))
    })
  })
}

function postJson<T>(urlPath: string, body: unknown, timeoutMs = 600_000): Promise<T> {
  return new Promise((resolve, reject) => {
    const payload = Buffer.from(JSON.stringify(body), 'utf8')
    const req = http.request(
      {
        host: 'localhost',
        port: PORT,
        path: urlPath,
        method: 'POST',
        timeout: timeoutMs,
        family: 4,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': payload.length,
        },
      },
      (res) => {
        const chunks: Buffer[] = []
        res.on('data', (c) => chunks.push(c))
        res.on('end', () => {
          try {
            resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')) as T)
          } catch (err) {
            reject(err)
          }
        })
      },
    )
    req.on('error', reject)
    req.on('timeout', () => {
      req.destroy()
      reject(new Error('timeout'))
    })
    req.write(payload)
    req.end()
  })
}

export async function ensureToolsInstalled(): Promise<void> {
  try {
    const status = await getJson<ToolsStatus>('/api/tools/status')
    if (status.adb.available && status.ios.available) return
    const missing: string[] = []
    if (!status.adb.available) missing.push('ADB')
    if (!status.ios.available) missing.push('libimobiledevice')
    console.log(`[chimera] Auto-installing missing tools: ${missing.join(', ')}`)
    if (Notification.isSupported()) {
      new Notification({
        title: 'Chimera',
        body: `Установка инструментов: ${missing.join(', ')}…`,
      }).show()
    }
    const result = await postJson<{ ok: boolean; error?: string }>(
      '/api/tools/install',
      { target: 'all' },
    )
    if (result.ok) {
      console.log('[chimera] Tools installed successfully')
      if (Notification.isSupported()) {
        new Notification({
          title: 'Chimera',
          body: 'Инструменты установлены. Теперь подключённые устройства будут обнаружены.',
        }).show()
      }
    } else {
      console.warn('[chimera] Tools install failed:', result.error)
    }
  } catch (err) {
    console.warn('[chimera] ensureToolsInstalled skipped:', (err as Error).message)
  }
}

export function applyAutostart(enabled: boolean): void {
  if (process.platform === 'win32' || process.platform === 'darwin') {
    app.setLoginItemSettings({
      openAtLogin: enabled,
      path: process.execPath,
    })
  } else if (process.platform === 'linux') {
    const autostartDir = path.join(os.homedir(), '.config', 'autostart')
    const desktopFile = path.join(autostartDir, 'chimera.desktop')
    if (enabled) {
      fs.mkdirSync(autostartDir, { recursive: true })
      fs.writeFileSync(
        desktopFile,
        [
          '[Desktop Entry]',
          'Type=Application',
          'Name=Chimera',
          `Exec=${process.execPath}`,
          'X-GNOME-Autostart-enabled=true',
        ].join('\n'),
        'utf8',
      )
    } else if (fs.existsSync(desktopFile)) {
      fs.unlinkSync(desktopFile)
    }
  }
}

export function getAutostart(): boolean {
  if (process.platform === 'linux') {
    const desktopFile = path.join(
      os.homedir(),
      '.config',
      'autostart',
      'chimera.desktop',
    )
    return fs.existsSync(desktopFile)
  }
  return app.getLoginItemSettings().openAtLogin
}

export function revealInExplorer(target: string): void {
  shell.showItemInFolder(path.normalize(target))
}

export async function openDataDirectory(): Promise<void> {
  await shell.openPath(app.getPath('userData'))
}

export interface SystemInfo {
  platform: NodeJS.Platform
  arch: string
  release: string
  hostname: string
  username: string
  appVersion: string
  electronVersion: string
  nodeVersion: string
  dataPath: string
  toolsPath: string
  autostart: boolean
}

export function getSystemInfo(): SystemInfo {
  return {
    platform: process.platform,
    arch: process.arch,
    release: os.release(),
    hostname: os.hostname(),
    username: os.userInfo().username,
    appVersion: app.getVersion(),
    electronVersion: process.versions.electron ?? '',
    nodeVersion: process.versions.node,
    dataPath: app.getPath('userData'),
    toolsPath:
      process.platform === 'win32'
        ? path.join(process.env.LOCALAPPDATA ?? os.homedir(), 'Chimera', 'tools')
        : path.join(os.homedir(), '.local', 'share', 'Chimera', 'tools'),
    autostart: getAutostart(),
  }
}

export function runElevated(command: string, args: string[] = []): Promise<number> {
  if (process.platform !== 'win32') {
    return new Promise((resolve, reject) => {
      const child = spawn('sudo', [command, ...args], { stdio: 'inherit' })
      child.on('exit', (code) => resolve(code ?? 0))
      child.on('error', reject)
    })
  }
  const quotedArgs = args
    .map((a) => `'${String(a).replace(/'/g, "''")}'`)
    .join(',')
  const argList = quotedArgs.length ? `-ArgumentList ${quotedArgs}` : ''
  const ps = [
    'Start-Process',
    '-FilePath',
    `'${command.replace(/'/g, "''")}'`,
    argList,
    '-Verb RunAs -Wait -WindowStyle Hidden',
  ]
    .filter(Boolean)
    .join(' ')
  return new Promise((resolve, reject) => {
    const child = spawn(
      'powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
      { windowsHide: true },
    )
    child.on('exit', (code) => resolve(code ?? 0))
    child.on('error', reject)
  })
}
