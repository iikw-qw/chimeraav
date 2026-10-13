import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { EmptyState } from '../components/ui'

export const slideUpVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
}

export interface PageStubProps {
  title: string
  icon: ReactNode
  description?: string
}

export function PageStub({ title, icon, description }: PageStubProps) {
  return (
    <motion.div
      variants={slideUpVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="flex h-full w-full flex-col overflow-hidden bg-[--bg-0]"
    >
      <div className="flex h-12 items-center border-b border-[--line-1] bg-[--bg-1] px-4">
        <h2 className="font-display text-sm font-semibold tracking-wide text-[--txt-1]">
          {title}
        </h2>
      </div>
      <div className="flex flex-1 items-center justify-center overflow-auto">
        <EmptyState
          icon={icon}
          title={title}
          description={description ?? 'Этот раздел будет подключён в следующих блоках.'}
        />
      </div>
    </motion.div>
  )
}
