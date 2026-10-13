import { useCallback, useEffect, useRef, useState } from 'react'

interface DeviceStreamProps {
  serial: string
  width: number
  height: number
  active: boolean
}

export function DeviceStream({ serial, width, height, active }: DeviceStreamProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval>>()

  const fetchScreenshot = useCallback(async () => {
    if (!canvasRef.current) return
    try {
      const res = await fetch(
        `http://localhost:17842/api/v1/stream/screenshot/${encodeURIComponent(serial)}?t=${Date.now()}`,
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const bmp = await createImageBitmap(blob)
      const ctx = canvasRef.current.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, width, height)
        ctx.drawImage(bmp, 0, 0, width, height)
      }
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [serial, width, height])

  useEffect(() => {
    if (!active) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }

    fetchScreenshot()
    intervalRef.current = setInterval(fetchScreenshot, 2000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [active, fetchScreenshot])

  if (!active) return null

  return (
    <div className="relative overflow-hidden rounded-lg bg-black">
      <canvas ref={canvasRef} width={width} height={height} className="block w-full" />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 text-[10px] text-[--txt-3]">
          {error}
        </div>
      )}
    </div>
  )
}
