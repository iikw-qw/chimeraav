interface LogoWatermarkProps {
  src?: string
}

export function LogoWatermark({ src }: LogoWatermarkProps) {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed z-0"
      style={{
        right: '-60px',
        top: '-40px',
        width: '450px',
        height: '450px',
        opacity: 0.025,
        filter: 'grayscale(100%) brightness(3)',
        animation: 'pulse-glow 8s ease-in-out infinite, spin-slow 120s linear infinite',
      }}
    >
      {src ? (
        <img src={src} alt="" className="h-full w-full select-none" draggable={false} />
      ) : (
        <div
          className="h-full w-full rounded-full"
          style={{
            background:
              'radial-gradient(circle at center, var(--blue) 0%, transparent 60%)',
          }}
        />
      )}
    </div>
  )
}
