import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, hoverable, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        'bg-[--bg-2] border border-[--line-1] rounded-xl',
        hoverable &&
          'hover:border-[--line-3] hover:shadow-[var(--shadow-card)] hover:scale-[1.01] transition-all duration-200',
        className,
      )}
      {...rest}
    />
  )
})

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardHeader({ className, ...rest }, ref) {
    return (
      <div ref={ref} className={cn('px-5 py-4 border-b border-[--line-1]', className)} {...rest} />
    )
  },
)

export const CardBody = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardBody({ className, ...rest }, ref) {
    return <div ref={ref} className={cn('p-5', className)} {...rest} />
  },
)

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardFooter({ className, ...rest }, ref) {
    return (
      <div ref={ref} className={cn('px-5 py-4 border-t border-[--line-1]', className)} {...rest} />
    )
  },
)
