// Top-overlay for a live device stream — shows device name, FPS, latency,
// resolution, and connection status. Designed to fade out when the user
// hovers away from the cell so it does not obscure the picture.

import { motion } from 'framer-motion'
import type { StreamConnState } from '../../hooks/useStreamSocket'
import type { StreamRuntimeStats } from '../../hooks/useStreamStats'

export interface StreamOverlayProps {
  title: string
  state: StreamConnState
  stats: StreamRuntimeStats
  resolution: { width: number; height: number } | null
  decoderKind: 'webcodecs' | 'fallback' | null
  error: string | null
  visible: boolean
}

const STATE_COLOR: Record<StreamConnState, string> = {
  idle: 'bg-zinc-500',
  connecting: 'bg-amber-500',
  open: 'bg-emerald-500',
  closed: 'bg-rose-500',
  error: 'bg-rose-500',
}

const STATE_LABEL: Record<StreamConnState, string> = {
  idle: 'idle',
  connecting: 'подключение',
  open: 'live',
  closed: 'оффлайн',
  error: 'ошибка',
}

export function StreamOverlay({
  title,
  state,
  stats,
  resolution,
  decoderKind,
  error,
  visible,
}: StreamOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: visible ? 1 : 0 }}
      transition={{ duration: 0.18 }}
      className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3 text-white"
      style={{
        background:
          'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 28%, rgba(0,0,0,0) 72%, rgba(0,0,0,0.55) 100%)',
      }}
    >
      <div className="flex items-start justify-between text-xs font-medium">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${STATE_COLOR[state]} animate-pulse`} />
          <span className="truncate max-w-[180px]">{title}</span>
          <span className="opacity-70">{STATE_LABEL[state]}</span>
        </div>
        {decoderKind === 'fallback' && (
          <span className="rounded bg-amber-500/80 px-1.5 py-0.5 text-[10px]">no WebCodecs</span>
        )}
      </div>
      <div className="flex items-end justify-between text-[11px] tabular-nums opacity-90">
        <div className="flex gap-3">
          <span>{stats.decodedFps.toFixed(0)} fps</span>
          <span>{(stats.bytesPerSec / 1024).toFixed(0)} KB/s</span>
          <span>{Math.round(stats.latencyMs)} ms</span>
        </div>
        <div className="flex gap-2">
          {resolution && (
            <span>
              {resolution.width}×{resolution.height}
            </span>
          )}
          {stats.droppedFrames > 0 && (
            <span className="text-amber-300">drop {stats.droppedFrames}</span>
          )}
        </div>
      </div>
      {error && (
        <div className="absolute bottom-2 left-3 right-3 rounded bg-rose-900/70 px-2 py-1 text-[10px] text-rose-100">
          {error}
        </div>
      )}
    </motion.div>
  )
}
