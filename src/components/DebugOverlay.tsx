import { useEffect, useRef, useState } from 'react'
import { cn } from '../lib/cn'

interface DebugEvent {
  type: string
  x?: number
  y?: number
  screen_w?: number
  screen_h?: number
  direction?: string
  points?: { x: number; y: number }[]
  timestamp?: number
  duration_ms?: number
}

interface Props {
  active: boolean
  debugData: DebugEvent[]
  streamWidth: number
  streamHeight: number
  screenWidth: number
  screenHeight: number
  latencyMs?: number
  actionCount?: number
}

export function DebugOverlay({
  active,
  debugData,
  streamWidth,
  streamHeight,
  screenWidth,
  screenHeight,
  latencyMs = 0,
  actionCount = 0,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [fps, setFps] = useState(0)
  const frameCountRef = useRef(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(frameCountRef.current)
      frameCountRef.current = 0
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!active || !canvasRef.current) return
    const ctx = canvasRef.current.getContext('2d')
    if (!ctx) return

    frameCountRef.current++

    const scaleX = streamWidth / (screenWidth || 1080)
    const scaleY = streamHeight / (screenHeight || 2400)

    ctx.clearRect(0, 0, streamWidth, streamHeight)

    const now = Date.now() / 1000

    for (const event of debugData) {
      const age = now - (event.timestamp || now)
      const alpha = Math.max(0, 1 - age)

      if (event.type === 'tap' && event.x != null && event.y != null) {
        const sx = event.x * scaleX
        const sy = event.y * scaleY
        const radius = 12 * (1 + age * 0.5)

        ctx.beginPath()
        ctx.arc(sx, sy, radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(239, 68, 68, ${alpha * 0.6})`
        ctx.fill()

        ctx.beginPath()
        ctx.arc(sx, sy, 4, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
        ctx.fill()
      }

      if (event.type === 'swipe' && event.points && event.points.length >= 2) {
        ctx.beginPath()
        ctx.strokeStyle = `rgba(59, 130, 246, ${alpha * 0.8})`
        ctx.lineWidth = 3
        ctx.lineCap = 'round'

        const pts = event.points
        ctx.moveTo(pts[0].x * scaleX, pts[0].y * scaleY)
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i].x * scaleX, pts[i].y * scaleY)
        }
        ctx.stroke()

        const last = pts[pts.length - 1]
        const prev = pts[pts.length - 2]
        const angle = Math.atan2(
          (last.y - prev.y) * scaleY,
          (last.x - prev.x) * scaleX,
        )
        const arrowLen = 10
        ctx.beginPath()
        ctx.moveTo(last.x * scaleX, last.y * scaleY)
        ctx.lineTo(
          last.x * scaleX - arrowLen * Math.cos(angle - 0.4),
          last.y * scaleY - arrowLen * Math.sin(angle - 0.4),
        )
        ctx.moveTo(last.x * scaleX, last.y * scaleY)
        ctx.lineTo(
          last.x * scaleX - arrowLen * Math.cos(angle + 0.4),
          last.y * scaleY - arrowLen * Math.sin(angle + 0.4),
        )
        ctx.strokeStyle = `rgba(59, 130, 246, ${alpha})`
        ctx.stroke()
      }

      if (event.type === 'chaotic_swipe' && event.points) {
        ctx.beginPath()
        ctx.strokeStyle = `rgba(249, 115, 22, ${alpha * 0.8})`
        ctx.lineWidth = 2
        ctx.setLineDash([4, 3])
        const pts = event.points
        if (pts.length > 0) {
          ctx.moveTo(pts[0].x * scaleX, pts[0].y * scaleY)
          for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(pts[i].x * scaleX, pts[i].y * scaleY)
          }
        }
        ctx.stroke()
        ctx.setLineDash([])
      }
    }
  }, [active, debugData, streamWidth, streamHeight, screenWidth, screenHeight])

  if (!active) return null

  return (
    <div className="pointer-events-none absolute inset-0">
      <canvas
        ref={canvasRef}
        width={streamWidth}
        height={streamHeight}
        className="absolute inset-0 h-full w-full"
      />
      <div className="absolute bottom-2 left-2 rounded-md bg-black/70 px-2 py-1 font-mono text-[10px] text-white/80">
        FPS: {fps} | Latency: {latencyMs}ms | Actions: {actionCount}
      </div>
    </div>
  )
}
