// useStreamSocket — opens a WebSocket to /api/ws/view/{device_id}, dispatches
// each binary frame to the caller, surfaces connection state, and reconnects
// with capped exponential backoff on disconnect.
//
// The socket is binary-only on the inbound side (NAL units). Optional JSON
// pings keep proxies happy.

import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/client'

export type StreamConnState = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

export interface UseStreamSocketOptions {
  deviceId: string | null
  onFrame: (frame: Uint8Array, recvTs: number) => void
  enabled?: boolean
}

function wsBaseUrl(): string {
  // Convert http(s) → ws(s)
  return API_BASE_URL.replace(/^http/, 'ws')
}

export function useStreamSocket({
  deviceId,
  onFrame,
  enabled = true,
}: UseStreamSocketOptions): { state: StreamConnState; lastError: string | null } {
  const [state, setState] = useState<StreamConnState>('idle')
  const [lastError, setLastError] = useState<string | null>(null)
  const onFrameRef = useRef(onFrame)
  onFrameRef.current = onFrame

  useEffect(() => {
    if (!enabled || !deviceId) {
      setState('idle')
      return
    }

    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let pingTimer: ReturnType<typeof setInterval> | null = null
    let backoff = 500
    let cancelled = false

    const connect = () => {
      if (cancelled) return
      setState('connecting')
      const url = `${wsBaseUrl()}/api/ws/view/${encodeURIComponent(deviceId)}`
      socket = new WebSocket(url)
      socket.binaryType = 'arraybuffer'

      socket.onopen = () => {
        backoff = 500
        setState('open')
        setLastError(null)
        pingTimer = setInterval(() => {
          if (socket && socket.readyState === WebSocket.OPEN) {
            try {
              socket.send(JSON.stringify({ type: 'ping', ts: Date.now() }))
            } catch {
              /* ignore */
            }
          }
        }, 5000)
      }

      socket.onmessage = (ev) => {
        if (typeof ev.data === 'string') {
          // ignore pong/control JSON
          return
        }
        // ArrayBuffer
        const ts = performance.now()
        const view = new Uint8Array(ev.data as ArrayBuffer)
        onFrameRef.current(view, ts)
      }

      socket.onerror = () => {
        setState('error')
        setLastError('WebSocket error')
      }

      socket.onclose = (ev) => {
        if (pingTimer) clearInterval(pingTimer)
        pingTimer = null
        socket = null
        setState('closed')
        if (cancelled) return
        // 4404 = stream not currently active. Slow-reconnect; producer might
        // come up later. All other codes: normal exponential backoff.
        const delay = ev.code === 4404 ? 5000 : backoff
        backoff = Math.min(backoff * 2, 15_000)
        reconnectTimer = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (pingTimer) clearInterval(pingTimer)
      if (socket) {
        try {
          socket.close()
        } catch {
          /* ignore */
        }
      }
      setState('idle')
    }
  }, [deviceId, enabled])

  return { state, lastError }
}
