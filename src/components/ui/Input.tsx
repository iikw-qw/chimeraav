import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, leftIcon, rightIcon, ...rest },
  ref,
) {
  if (!leftIcon && !rightIcon) {
    return (
      <input
        ref={ref}
        className={cn(
          'h-10 w-full bg-[--bg-3] border border-[--line-2] rounded-lg px-3 text-sm text-[--txt-1] placeholder:text-[--txt-3] outline-none transition-colors focus:border-[--blue] focus:ring-2 focus:ring-[--blue]/20',
          className,
        )}
        {...rest}
      />
    )
  }
  return (
    <div className={cn('relative w-full', className)}>
      {leftIcon && (
        <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[--txt-3]">
          {leftIcon}
        </span>
      )}
      <input
        ref={ref}
        className={cn(
          'h-10 w-full bg-[--bg-3] border border-[--line-2] rounded-lg text-sm text-[--txt-1] placeholder:text-[--txt-3] outline-none transition-colors focus:border-[--blue] focus:ring-2 focus:ring-[--blue]/20',
          leftIcon ? 'pl-9' : 'pl-3',
          rightIcon ? 'pr-9' : 'pr-3',
        )}
        {...rest}
      />
      {rightIcon && (
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[--txt-3]">
          {rightIcon}
        </span>
      )}
    </div>
  )
})
