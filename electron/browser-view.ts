import { BrowserView, BrowserWindow, shell } from 'electron'

const SOCIAL_HOSTS = [
  'instagram.com',
  'tiktok.com',
  'telegram.org',
  't.me',
  'twitter.com',
  'x.com',
  'facebook.com',
  'vk.com',
  'youtube.com',
  'youtu.be',
  'linkedin.com',
  'reddit.com',
  'threads.net',
]

function isSocial(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase()
    return SOCIAL_HOSTS.some((h) => host === h || host.endsWith(`.${h}`))
  } catch {
    return false
  }
}

export class BrowserViewManager {
  private view: BrowserView | null = null
  private visible = false

  constructor(private win: BrowserWindow) {
    win.on('resize', () => this.layout())
  }

  async openUrl(url: string): Promise<void> {
    if (!isSocial(url)) {
      await shell.openExternal(url)
      return
    }

    if (!this.view) {
      this.view = new BrowserView({
        webPreferences: {
          contextIsolation: true,
          nodeIntegration: false,
        },
      })
      this.view.setAutoResize({ width: true, height: true })
      this.view.webContents.setWindowOpenHandler(({ url: target }) => {
        if (isSocial(target)) {
          this.view?.webContents.loadURL(target)
        } else {
          shell.openExternal(target)
        }
        return { action: 'deny' }
      })
    }

    if (!this.visible) {
      this.win.setBrowserView(this.view)
      this.visible = true
    }
    this.layout()
    await this.view.webContents.loadURL(url)
  }

  close(): void {
    if (this.view && this.visible) {
      this.win.setBrowserView(null)
      this.visible = false
    }
  }

  toggle(): void {
    if (!this.view) return
    if (this.visible) {
      this.close()
    } else {
      this.win.setBrowserView(this.view)
      this.visible = true
      this.layout()
    }
  }

  goBack(): void {
    if (this.view?.webContents.canGoBack()) this.view.webContents.goBack()
  }

  goForward(): void {
    if (this.view?.webContents.canGoForward()) this.view.webContents.goForward()
  }

  reload(): void {
    this.view?.webContents.reload()
  }

  private layout(): void {
    if (!this.view || !this.visible) return
    const [w, h] = this.win.getContentSize()
    const width = Math.floor(w * 0.6)
    this.view.setBounds({ x: w - width, y: 0, width, height: h })
  }
}
