// useStreamStats — rolling 1-second window of frames-per-second, decoded
// bytes, and end-to-end latency derived from `recordFrame()` calls. Plus a
// 60-sample latency history for charting (one sample/sec).
//
// Latency is "frames received minus first paint" — without a wall-clock
// timestamp embedded in the bitstream we approximate with the receive→draw
// gap in the browser, which is a reasonable proxy on LAN.

import { useCallback, useEffect, useRef, useState } from 'react'

export interface StreamRuntimeStats {
  fps: number
  decodedFps: number
  bytesPerSec: number
  latencyMs: number
  droppedFrames: number
  history: number[] // last 60 latency samples (ms)
}

interface FrameSample {
  ts: number
  bytes: number
  decoded: boolean
  latencyMs: number
}

const EMPTY: StreamRuntimeStats = {
  fps: 0,
  decodedFps: 0,
  bytesPerSec: 0,
  latencyMs: 0,
  droppedFrames: 0,
  history: [],
}

export function useStreamStats(): {
  stats: StreamRuntimeStats
  recordFrame: (bytes: number, decoded: boolean, latencyMs: number) => void
  recordDrop: () => void
  reset: () => void
} {
  const [stats, setStats] = useState<StreamRuntimeStats>(EMPTY)
  const samplesRef = useRef<FrameSample[]>([])
  const droppedRef = useRef(0)
  const historyRef = useRef<number[]>([])

  const recordFrame = useCallback((bytes: number, decoded: boolean, latencyMs: number) => {
    samplesRef.current.push({ ts: performance.now(), bytes, decoded, latencyMs })
  }, [])

  const recordDrop = useCallback(() => {
    droppedRef.current += 1
  }, [])

  const reset = useCallback(() => {
    samplesRef.current = []
    droppedRef.current = 0
    historyRef.current = []
    setStats(EMPTY)
  }, [])

  useEffect(() => {
    const tick = setInterval(() => {
      const now = performance.now()
      const cutoff = now - 1000
      const samples = samplesRef.current
      while (samples.length && samples[0].ts < cutoff) samples.shift()

      const decoded = samples.filter((s) => s.decoded)
      const fps = samples.length
      const decodedFps = decoded.length
      const bytesPerSec = samples.reduce((a, s) => a + s.bytes, 0)
      const latencyMs =
        decoded.length > 0
          ? decoded.reduce((a, s) => a + s.latencyMs, 0) / decoded.length
          : 0

      historyRef.current.push(latencyMs)
      if (historyRef.current.length > 60) historyRef.current.shift()

      setStats({
        fps,
        decodedFps,
        bytesPerSec,
        latencyMs,
        droppedFrames: droppedRef.current,
        history: historyRef.current.slice(),
      })
    }, 1000)
    return () => clearInterval(tick)
  }, [])

  return { stats, recordFrame, recordDrop, reset }
}
