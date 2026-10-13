import { useEffect, useRef } from 'react'

export function useWebSocket(path: string, onMessage: (data: any) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(1)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    let cancelled = false

    function connect() {
      if (cancelled) return
      const ws = new WebSocket(`ws://localhost:17842${path}`)
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 1
      }

      ws.onmessage = (event) => {
        try {
          const data =
            event.data instanceof Blob
              ? event.data
              : JSON.parse(event.data)
          onMessageRef.current(data)
        } catch {
          onMessageRef.current(event.data)
        }
      }

      ws.onclose = () => {
        if (cancelled) return
        const delay = Math.min(retryRef.current * 1000, 8000)
        retryRef.current *= 2
        setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [path])

  return wsRef
}
