// DeviceStream — single-device live H.264 viewer. Owns the canvas, the
// decoder hook, and the on-canvas overlay. Used standalone or inside
// DeviceGrid.

import { useRef, useState } from 'react'
import { Camera, Maximize2, Pause, Play } from 'lucide-react'
import { useH264Decoder } from '../../hooks/useH264Decoder'
import { StreamOverlay } from './StreamOverlay'

export interface DeviceStreamProps {
  deviceId: string
  title: string
  active?: boolean
  onFullscreen?: () => void
  onScreenshot?: () => void
  className?: string
}

export function DeviceStream({
  deviceId,
  title,
  active = true,
  onFullscreen,
  onScreenshot,
  className,
}: DeviceStreamProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [paused, setPaused] = useState(false)
  const [hovering, setHovering] = useState(false)

  const enabled = active && !paused
  const { state, stats, resolution, decoderKind, error } = useH264Decoder(
    deviceId,
    canvasRef,
    enabled,
  )

  const handleScreenshot = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title.replace(/\s+/g, '_')}_${Date.now()}.png`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }, 'image/png')
    onScreenshot?.()
  }

  return (
    <div
      className={
        'relative overflow-hidden rounded-xl border border-[--line-1] bg-black ' +
        (className ?? '')
      }
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <canvas
        ref={canvasRef}
        className="block w-full h-full object-contain"
        style={{ aspectRatio: '9 / 16' }}
      />
      <StreamOverlay
        title={title}
        state={state}
        stats={stats}
        resolution={resolution}
        decoderKind={decoderKind}
        error={error}
        visible={hovering || state !== 'open'}
      />
      {state === 'closed' && (
        <div className="absolute inset-0 grid place-items-center text-white/80 bg-black/60 text-xs">
          Reconnecting…
        </div>
      )}
      {state === 'connecting' && resolution === null && (
        <div className="absolute inset-0 grid place-items-center text-white/80 bg-black/30 text-xs">
          Подключение…
        </div>
      )}
      <div
        className="absolute right-2 top-2 flex gap-1 transition-opacity"
        style={{ opacity: hovering ? 1 : 0 }}
      >
        <IconButton title={paused ? 'Возобновить' : 'Пауза'} onClick={() => setPaused((p) => !p)}>
          {paused ? <Play size={14} /> : <Pause size={14} />}
        </IconButton>
        <IconButton title="Скриншот" onClick={handleScreenshot}>
          <Camera size={14} />
        </IconButton>
        {onFullscreen && (
          <IconButton title="Полный экран" onClick={onFullscreen}>
            <Maximize2 size={14} />
          </IconButton>
        )}
      </div>
    </div>
  )
}

function IconButton({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode
  onClick: () => void
  title: string
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="grid place-items-center w-7 h-7 rounded-md bg-black/60 text-white/90 hover:bg-black/80 transition-colors"
    >
      {children}
    </button>
  )
}
