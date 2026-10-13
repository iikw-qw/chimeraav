import { useCallback, useRef, type PointerEvent } from 'react'
import { cn } from '../../lib/cn'

export interface SliderProps {
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (value: number) => void
  disabled?: boolean
  className?: string
}

export function Slider({
  value,
  min = 0,
  max = 100,
  step = 1,
  onChange,
  disabled,
  className,
}: SliderProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  const setFromClientX = useCallback(
    (clientX: number) => {
      const el = trackRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
      const raw = min + ratio * (max - min)
      const stepped = Math.round(raw / step) * step
      onChange(Math.min(max, Math.max(min, stepped)))
    },
    [min, max, step, onChange],
  )

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (disabled) return
    draggingRef.current = true
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    setFromClientX(e.clientX)
  }

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    setFromClientX(e.clientX)
  }

  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    draggingRef.current = false
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  }

  const pct = ((value - min) / (max - min)) * 100

  return (
    <div
      ref={trackRef}
      className={cn(
        'relative h-1.5 w-full rounded-full bg-[--bg-3] cursor-pointer',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
      role="slider"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <div
        className="absolute left-0 top-0 h-full rounded-full bg-[--blue]"
        style={{ width: `${pct}%` }}
      />
      <div
        className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[--blue] bg-white shadow"
        style={{ left: `${pct}%` }}
      />
    </div>
  )
}
