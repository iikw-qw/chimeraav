// useH264Decoder — wires the WebSocket frame stream into a WebCodecs (or
// fallback) decoder and renders decoded VideoFrames onto a canvas.
//
// The hook is canvas-out: pass a ref to a <canvas> and the hook will resize
// it to the source resolution and `drawImage` each frame. We use a 2D
// context (not WebGL) — Chrome's drawImage path with VideoFrame is hardware
// accelerated and the simplest thing that works.

import { useEffect, useRef, useState } from 'react'
import { createDecoder, type AnyH264Decoder } from '../lib/broadway-fallback'
import { inspect } from '../lib/h264-parser'
import { useStreamSocket, type StreamConnState } from './useStreamSocket'
import { useStreamStats, type StreamRuntimeStats } from './useStreamStats'

export interface UseH264DecoderResult {
  state: StreamConnState
  stats: StreamRuntimeStats
  resolution: { width: number; height: number } | null
  decoderKind: 'webcodecs' | 'fallback' | null
  error: string | null
}

export function useH264Decoder(
  deviceId: string | null,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  enabled = true,
): UseH264DecoderResult {
  const [error, setError] = useState<string | null>(null)
  const [decoderKind, setDecoderKind] = useState<'webcodecs' | 'fallback' | null>(null)
  const [resolution, setResolution] = useState<{ width: number; height: number } | null>(null)

  const decoderRef = useRef<AnyH264Decoder | null>(null)
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null)
  const pendingFrameTsRef = useRef<number[]>([]) // recvTs queue, popped on each decoded frame

  const { stats, recordFrame, recordDrop, reset } = useStreamStats()

  // Build / tear down decoder when device changes.
  useEffect(() => {
    if (!enabled || !deviceId) return
    let cancelled = false

    const factory = createDecoder({
      onFrame: (frame) => {
        if (cancelled) {
          frame.close()
          return
        }
        const w = frame.displayWidth
        const h = frame.displayHeight
        const canvas = canvasRef.current
        if (canvas) {
          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w
            canvas.height = h
            setResolution({ width: w, height: h })
          }
          let ctx = ctxRef.current
          if (!ctx) {
            ctx = canvas.getContext('2d', { alpha: false })
            ctxRef.current = ctx
          }
          if (ctx) {
            try {
              ctx.drawImage(frame, 0, 0, w, h)
            } catch {
              /* ignore */
            }
          }
        }
        const recvTs = pendingFrameTsRef.current.shift() ?? performance.now()
        const latencyMs = performance.now() - recvTs
        recordFrame(frame.codedWidth * frame.codedHeight, true, latencyMs)
        frame.close()
      },
      onError: (err) => {
        if (cancelled) return
        setError(err.message)
      },
    })
    decoderRef.current = factory.instance
    setDecoderKind(factory.kind)

    factory.instance.start().catch((err) => {
      if (!cancelled) setError(err instanceof Error ? err.message : String(err))
    })

    return () => {
      cancelled = true
      const dec = decoderRef.current
      decoderRef.current = null
      ctxRef.current = null
      pendingFrameTsRef.current = []
      reset()
      if (dec) dec.close().catch(() => undefined)
    }
  }, [deviceId, enabled, canvasRef, recordFrame, reset])

  const handleFrame = (frame: Uint8Array, recvTs: number) => {
    const dec = decoderRef.current
    if (!dec) return
    const info = inspect(frame)
    pendingFrameTsRef.current.push(recvTs)
    if (pendingFrameTsRef.current.length > 240) pendingFrameTsRef.current.shift()
    const forwarded = dec.push(frame, Math.floor(recvTs * 1000)) // µs
    if (!forwarded && !info.isParamSet) {
      // dropped while waiting for keyframe / pre-config
      recordDrop()
    }
    // count raw arrival even if not decoded — useful for debugging
    if (!forwarded) recordFrame(frame.byteLength, false, 0)
  }

  const { state } = useStreamSocket({
    deviceId,
    onFrame: handleFrame,
    enabled,
  })

  return { state, stats, resolution, decoderKind, error }
}
