import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import fs from 'fs'
import http from 'http'

let pyProc: ChildProcess | null = null
let botProc: ChildProcess | null = null
let quitting = false
const PORT = 17842

function isBotRunning(backendCwd: string): boolean {
  const lockFile = path.join(backendCwd, '.bot.lock')
  if (fs.existsSync(lockFile)) {
    try {
      const pid = parseInt(fs.readFileSync(lockFile, 'utf8').trim(), 10)
      if (isNaN(pid)) return false
      try {
        process.kill(pid, 0)
        return true
      } catch {
        return false
      }
    } catch {
      return false
    }
  }
  return false
}
const RESTART_DELAY = 3000

function logDir(): string {
  const dir = path.join(app.getPath('userData'), 'logs')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

function createLogStream(name: string): fs.WriteStream {
  return fs.createWriteStream(path.join(logDir(), `${name}.log`), { flags: 'a' })
}

function ping(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { host: 'localhost', port: PORT, path: '/health', timeout: 1000, family: 4 },
      (res) => {
        const ok = res.statusCode === 200
        res.resume()
        resolve(ok)
      },
    )
    req.on('error', () => resolve(false))
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
  })
}

async function waitForHealth(timeoutMs = 30000, intervalMs = 500): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (await ping()) return
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error(`Python sidecar not healthy after ${timeoutMs}ms`)
}

function spawnChild(
  label: string,
  exe: string,
  args: string[],
  cwd: string,
  env: NodeJS.ProcessEnv,
): ChildProcess {
  const logStream = createLogStream(label)
  const proc = spawn(exe, args, {
    env,
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  proc.stdout?.pipe(logStream)
  proc.stderr?.pipe(logStream)

  proc.on('exit', (code, signal) => {
    console.log(`[chimera] ${label} exited code=${code} signal=${signal}`)
    if (!quitting) {
      console.log(`[chimera] Restarting ${label} in ${RESTART_DELAY}ms...`)
      setTimeout(() => {
        if (!quitting) {
          const restarted = spawnChild(label, exe, args, cwd, env)
          if (label === 'sidecar') pyProc = restarted
          else if (label === 'bot') botProc = restarted
        }
      }, RESTART_DELAY)
    }
  })

  proc.on('error', (err) => {
    console.error(`[chimera] ${label} error:`, err)
  })

  return proc
}

export async function startPython(_isDev: boolean): Promise<void> {
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    CHIMERA_DATA_DIR: app.getPath('userData'),
    CHIMERA_PORT: String(PORT),
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8',
  }

  if (await ping()) {
    console.log('[chimera] Reusing existing Python sidecar on :17842')
    return
  }

  if (!app.isPackaged) {
    const cwd = path.resolve(__dirname, '..')
    const backendCwd = path.join(cwd, 'python-backend')
    const launcher = process.platform === 'win32' ? 'py' : 'python3'

    pyProc = spawnChild(
      'sidecar',
      launcher,
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(PORT)],
      backendCwd,
      env,
    )

    if (!isBotRunning(backendCwd)) {
      botProc = spawnChild(
        'bot',
        launcher,
        ['chimera_bot.py'],
        backendCwd,
        env,
      )
    } else {
      console.log('[chimera] Bot already running, skipping spawn')
    }
  } else {
    const pythonExe = path.join(
      process.env.LOCALAPPDATA || path.join(app.getPath('userData'), '..', '..', 'Local'),
      'Chimera',
      'python',
      'python.exe',
    )
    const backendCwd = path.join(process.resourcesPath, 'backend')

    pyProc = spawnChild(
      'sidecar',
      pythonExe,
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(PORT)],
      backendCwd,
      env,
    )

    if (!isBotRunning(backendCwd)) {
      botProc = spawnChild(
        'bot',
        pythonExe,
        ['chimera_bot.py'],
        backendCwd,
        env,
      )
    } else {
      console.log('[chimera] Bot already running, skipping spawn')
    }
  }

  await waitForHealth()
}

async function killProc(proc: ChildProcess | null): Promise<void> {
  if (!proc) return
  await new Promise<void>((resolve) => {
    const killTimer = setTimeout(() => {
      try {
        proc.kill('SIGKILL')
      } catch {
        /* ignore */
      }
      resolve()
    }, 3000)
    proc.once('exit', () => {
      clearTimeout(killTimer)
      resolve()
    })
    try {
      proc.kill('SIGTERM')
    } catch {
      clearTimeout(killTimer)
      resolve()
    }
  })
}

export async function stopPython(): Promise<void> {
  quitting = true
  await Promise.all([killProc(pyProc), killProc(botProc)])
  pyProc = null
  botProc = null
}
