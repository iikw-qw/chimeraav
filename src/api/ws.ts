import { useEffect } from 'react'

export const WS_URL =
  (window as any).__CHIMERA_WS_URL__ ||
  'ws://localhost:17842/api/ws'

export type WSMessage = { channel: string; data: unknown }
export type WSHandler = (payload: unknown) => void

class ChimeraWS {
  private socket: WebSocket | null = null
  private reconnectDelay = 1000
  private readonly maxDelay = 30_000
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private handlers = new Map<string, Set<WSHandler>>()
  private subscribed = new Set<string>()
  private closedByUser = false
  private statusListeners = new Set<(s: WSStatus) => void>()
  private _status: WSStatus = 'idle'

  get status(): WSStatus {
    return this._status
  }

  connect(url: string = WS_URL): void {
    this.closedByUser = false
    if (this.socket && this.socket.readyState <= 1) return
    this.setStatus('connecting')

    const socket = new WebSocket(url)
    this.socket = socket

    socket.onopen = () => {
      this.reconnectDelay = 1000
      this.setStatus('open')
      for (const channel of this.subscribed) {
        this.send({ type: 'subscribe', channel })
      }
    }

    socket.onmessage = (ev) => {
      let msg: WSMessage | { type?: string; channel?: string }
      try {
        msg = JSON.parse(ev.data)
      } catch {
        return
      }
      const withChannel = msg as WSMessage
      if (typeof withChannel.channel === 'string' && 'data' in withChannel) {
        const subs = this.handlers.get(withChannel.channel)
        subs?.forEach((h) => {
          try {
            h(withChannel.data)
          } catch (err) {
            console.error('WS handler error:', err)
          }
        })
      }
    }

    socket.onclose = () => {
      this.socket = null
      this.setStatus('closed')
      if (!this.closedByUser) this.scheduleReconnect(url)
    }

    socket.onerror = () => {
      this.setStatus('error')
      // Some browsers/networks fire `error` without `close` — force a clean
      // close so scheduleReconnect kicks in. Otherwise the socket can stay
      // half-open forever and the app silently stops receiving updates
      // (which manifests as "after a few hours nothing reacts anymore").
      try {
        socket.close()
      } catch {
        // ignore
      }
    }
  }

  private scheduleReconnect(url: string): void {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
      this.connect(url)
    }, this.reconnectDelay)
  }

  subscribe(channel: string, handler: WSHandler): () => void {
    let set = this.handlers.get(channel)
    if (!set) {
      set = new Set()
      this.handlers.set(channel, set)
    }
    set.add(handler)

    if (!this.subscribed.has(channel)) {
      this.subscribed.add(channel)
      this.send({ type: 'subscribe', channel })
    }
    return () => this.unsubscribe(channel, handler)
  }

  unsubscribe(channel: string, handler: WSHandler): void {
    const set = this.handlers.get(channel)
    if (!set) return
    set.delete(handler)
    if (set.size === 0) {
      this.handlers.delete(channel)
      this.subscribed.delete(channel)
      this.send({ type: 'unsubscribe', channel })
    }
  }

  send(payload: unknown): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify(payload))
      } catch {
        // ignore
      }
    }
  }

  close(): void {
    this.closedByUser = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.socket?.close()
    this.socket = null
  }

  onStatus(listener: (s: WSStatus) => void): () => void {
    this.statusListeners.add(listener)
    listener(this._status)
    return () => this.statusListeners.delete(listener)
  }

  private setStatus(status: WSStatus): void {
    this._status = status
    this.statusListeners.forEach((l) => l(status))
  }
}

export type WSStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

export const ws = new ChimeraWS()

export function useWSChannel(channel: string, handler: WSHandler): void {
  useEffect(() => {
    const unsub = ws.subscribe(channel, handler)
    return unsub
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel])
}
