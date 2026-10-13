import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'

export interface CountUpProps {
  value: number
  duration?: number
  className?: string
  format?: (n: number) => string
}

export function CountUp({ value, duration = 0.6, className, format }: CountUpProps) {
  const [display, setDisplay] = useState(value)
  const prev = useRef(value)

  useEffect(() => {
    const controls = animate(prev.current, value, {
      duration,
      ease: 'easeOut',
      onUpdate: (v) => setDisplay(v),
    })
    prev.current = value
    return () => controls.stop()
  }, [value, duration])

  const rendered = format ? format(display) : Math.round(display).toString()
  return <span className={className}>{rendered}</span>
}
