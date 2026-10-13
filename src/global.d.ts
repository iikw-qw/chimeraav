/// <reference types="vite/client" />

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
    onScroll?: (props: { scrollOffset: number; scrollDirection: 'forward' | 'backward' }) => void
    children: React.ComponentType<ListChildComponentProps<T>>
  }

  export class FixedSizeList<T = unknown> extends React.Component<FixedSizeListProps<T>> {
    scrollTo(offset: number): void
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void
  }

  export interface VariableSizeListProps<T = unknown>
    extends Omit<FixedSizeListProps<T>, 'itemSize'> {
    itemSize: (index: number) => number
    estimatedItemSize?: number
  }

  export class VariableSizeList<T = unknown> extends React.Component<VariableSizeListProps<T>> {
    resetAfterIndex(index: number, shouldForceUpdate?: boolean): void
    scrollTo(offset: number): void
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void
  }
}


export interface ChimeraAPI {
  window: {
    minimize: () => Promise<void>
    maximize: () => Promise<void>
    close: () => Promise<void>
    isMaximized: () => Promise<boolean>
  }
  browser: {
    open: (url: string) => Promise<void>
    close: () => Promise<void>
    back: () => Promise<void>
    forward: () => Promise<void>
    reload: () => Promise<void>
    toggle: () => Promise<void>
  }
  dialog: {
    openFolder: () => Promise<string | null>
    openFiles: () => Promise<string[] | null>
    saveFile: (defaultPath?: string) => Promise<string | null>
  }
  app: {
    getVersion: () => Promise<string>
    getDataPath: () => Promise<string>
    openExternal: (url: string) => Promise<void>
  }
  system: {
    info: () => Promise<SystemInfo>
    getAutostart: () => Promise<boolean>
    setAutostart: (enabled: boolean) => Promise<boolean>
    openDataDir: () => Promise<void>
    revealPath: (target: string) => Promise<void>
    ensureTools: () => Promise<void>
    runElevated: (cmd: string, args?: string[]) => Promise<number>
    restartApp: () => Promise<void>
  }
  onNavigate: (cb: (route: string) => void) => () => void
  onUpdate: (cb: (info: unknown) => void) => () => void
}

export interface SystemInfo {
  platform: string
  arch: string
  release: string
  hostname: string
  username: string
  appVersion: string
  electronVersion: string
  nodeVersion: string
  dataPath: string
  toolsPath: string
  autostart: boolean
}

declare global {
  interface Window {
    chimera: ChimeraAPI
  }
}

export {}
