interface Particle {
  top: string
  left: string
  duration: string
  delay: string
}

const PARTICLES: Particle[] = [
  { top: '8%', left: '12%', duration: '20s', delay: '0s' },
  { top: '62%', left: '8%', duration: '28s', delay: '-7s' },
  { top: '18%', left: '72%', duration: '35s', delay: '-3s' },
  { top: '78%', left: '64%', duration: '24s', delay: '-12s' },
  { top: '44%', left: '40%', duration: '32s', delay: '-18s' },
]

export function FloatingParticles() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="absolute h-[300px] w-[300px] rounded-full bg-[--blue] opacity-[0.03] blur-[100px]"
          style={{
            top: p.top,
            left: p.left,
            animation: `float ${p.duration} ease-in-out infinite`,
            animationDelay: p.delay,
          }}
        />
      ))}
    </div>
  )
}
