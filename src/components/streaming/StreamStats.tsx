// StreamStats — sidebar / footer panel with detailed streaming metrics for
// the currently focused device. Includes a 60-sample latency sparkline.

import { useMemo } from 'react'
import type { StreamRuntimeStats } from '../../hooks/useStreamStats'

export interface StreamStatsProps {
  title?: string
  stats: StreamRuntimeStats
  resolution: { width: number; height: number } | null
}

export function StreamStats({ title = 'Метрики стрима', stats, resolution }: StreamStatsProps) {
  const path = useMemo(() => sparklinePath(stats.history, 220, 40), [stats.history])
  const max = stats.history.length ? Math.max(...stats.history) : 0
  const avg =
    stats.history.length > 0
      ? stats.history.reduce((a, b) => a + b, 0) / stats.history.length
      : 0

  return (
    <div className="rounded-xl border border-[--line-1] bg-[--bg-2] p-4 space-y-3">
      <div className="text-sm font-medium text-[--text-1]">{title}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <Stat label="FPS (decoded)" value={stats.decodedFps.toFixed(1)} />
        <Stat label="FPS (raw)" value={stats.fps.toFixed(1)} />
        <Stat label="Битрейт" value={`${(stats.bytesPerSec / 128).toFixed(0)} kbps`} />
        <Stat label="Задержка" value={`${Math.round(stats.latencyMs)} ms`} />
        <Stat label="Дроп фреймы" value={String(stats.droppedFrames)} />
        <Stat
          label="Разрешение"
          value={resolution ? `${resolution.width}×${resolution.height}` : '—'}
        />
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] uppercase tracking-wide text-[--text-3]">
          <span>Latency, ms (60s)</span>
          <span>
            avg {avg.toFixed(0)} · max {max.toFixed(0)}
          </span>
        </div>
        <svg viewBox="0 0 220 40" className="w-full h-10" preserveAspectRatio="none">
          <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} className="text-emerald-400" />
        </svg>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-[--text-3]">{label}</span>
      <span className="font-medium text-[--text-1] tabular-nums">{value}</span>
    </div>
  )
}

function sparklinePath(samples: number[], w: number, h: number): string {
  if (samples.length === 0) return ''
  const max = Math.max(1, ...samples)
  const stepX = w / Math.max(1, samples.length - 1)
  return samples
    .map((s, i) => {
      const x = i * stepX
      const y = h - (s / max) * h
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}
