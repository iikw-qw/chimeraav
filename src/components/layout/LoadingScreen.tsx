import { useEffect, useState } from 'react'
import { ProgressBar } from '../ui'

export interface LoadingScreenProps {
  message?: string
}

export function LoadingScreen({ message = 'Starting Chimera...' }: LoadingScreenProps) {
  const [value, setValue] = useState(10)

  useEffect(() => {
    const timer = setInterval(() => {
      setValue((v) => (v < 90 ? v + Math.random() * 6 : v))
    }, 250)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[--bg-0]">
      <img
        src={new URL('../../assets/chimera-logo.png', import.meta.url).href}
        alt="Chimera"
        className="h-16 w-16 rounded-2xl shadow-[--glow-blue] animate-[breathe_3s_infinite] object-cover"
      />
      <div className="mt-4 text-sm text-[--txt-2]">{message}</div>
      <div className="mt-6 w-48">
        <ProgressBar value={value} />
      </div>
    </div>
  )
}
