import { LoadingSpinner } from './LoadingSpinner'

interface Props {
  label?: string
}

export function PageLoader({ label = 'Loading...' }: Props) {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <LoadingSpinner label={label} size="lg" />
    </div>
  )
}
