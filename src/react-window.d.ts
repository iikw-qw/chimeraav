declare module 'react-window' {
  import * as React from 'react'

  export interface ListChildComponentProps<T = unknown> {
    index: number
    style: React.CSSProperties
    data: T
    isScrolling?: boolean
  }

  export interface FixedSizeListProps<T = unknown> {
    height: number | string
    width: number | string
    itemCount: number
    itemSize: number
    itemData?: T
    overscanCount?: number
    className?: string
    style?: React.CSSProperties
    innerRef?: React.Ref<HTMLElement>
    outerRef?: React.Ref<HTMLElement>
    onScroll?: (props: {
      scrollOffset: number
      scrollDirection: 'forward' | 'backward'
    }) => void
    children: React.ComponentType<ListChildComponentProps<T>>
  }

  export class FixedSizeList<T = unknown> extends React.Component<FixedSizeListProps<T>> {
    scrollTo(offset: number): void
    scrollToItem(
      index: number,
      align?: 'auto' | 'smart' | 'center' | 'end' | 'start',
    ): void
  }

  export interface VariableSizeListProps<T = unknown>
    extends Omit<FixedSizeListProps<T>, 'itemSize'> {
    itemSize: (index: number) => number
    estimatedItemSize?: number
  }

  export class VariableSizeList<T = unknown> extends React.Component<
    VariableSizeListProps<T>
  > {
    resetAfterIndex(index: number, shouldForceUpdate?: boolean): void
    scrollTo(offset: number): void
    scrollToItem(
      index: number,
      align?: 'auto' | 'smart' | 'center' | 'end' | 'start',
    ): void
  }
}
