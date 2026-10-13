import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type BackendStatus = 'starting' | 'ready' | 'error' | 'down'
export type CellSize = 'sm' | 'md' | 'lg'
export type ActivePage =
  | 'phones'
  | 'accounts'
  | 'tasks'
  | 'comments'
  | 'messages'
  | 'datasets'
  | 'templates'
  | 'proxies'
  | 'settings'
  | 'dashboard'

export const CELL_SIZE_PX: Record<CellSize, number> = {
  sm: 140,
  md: 175,
  lg: 220,
}

export const BOTTOM_PANEL_MIN = 48
export const BOTTOM_PANEL_DEFAULT = 280
export const BOTTOM_PANEL_COLLAPSED = 48

interface AppState {
  sidebarCollapsed: boolean
  bottomPanelHeight: number
  bottomPanelCollapsed: boolean
  bottomPanelPrevHeight: number
  backendStatus: BackendStatus
  cellSize: CellSize
  activePage: ActivePage
  syncMouse: boolean
  syncKeys: boolean
  selectedGroup: string | 'all'
  datasetPanelOpen: boolean
  masterDeviceId: string | null
  selectedDeviceIds: Set<string>
  showOnboarding: boolean

  setSidebarCollapsed: (v: boolean) => void
  toggleSidebar: () => void
  setBottomPanelHeight: (h: number) => void
  toggleBottomPanel: () => void
  setBackendStatus: (s: BackendStatus) => void
  setCellSize: (s: CellSize) => void
  setActivePage: (p: ActivePage) => void
  setSyncMouse: (v: boolean) => void
  setSyncKeys: (v: boolean) => void
  setSelectedGroup: (g: string | 'all') => void
  setDatasetPanelOpen: (v: boolean) => void
  toggleDatasetPanel: () => void
  setMasterDeviceId: (id: string | null) => void
  toggleDeviceSelected: (id: string) => void
  clearSelectedDevices: () => void
  setShowOnboarding: (v: boolean) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      sidebarCollapsed: false,
      bottomPanelHeight: BOTTOM_PANEL_DEFAULT,
      bottomPanelCollapsed: false,
      bottomPanelPrevHeight: BOTTOM_PANEL_DEFAULT,
      backendStatus: 'starting',
      cellSize: 'md',
      activePage: 'phones',
      syncMouse: false,
      syncKeys: false,
      selectedGroup: 'all',
      datasetPanelOpen: false,
      masterDeviceId: null,
      selectedDeviceIds: new Set<string>(),
      showOnboarding: false,

      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setBottomPanelHeight: (h) => {
        const maxH = Math.floor(window.innerHeight * 0.5)
        const clamped = Math.max(BOTTOM_PANEL_MIN, Math.min(h, maxH))
        set({
          bottomPanelHeight: clamped,
          bottomPanelCollapsed: clamped <= BOTTOM_PANEL_COLLAPSED,
        })
      },
      toggleBottomPanel: () => {
        const s = get()
        if (s.bottomPanelCollapsed) {
          set({
            bottomPanelHeight: s.bottomPanelPrevHeight || BOTTOM_PANEL_DEFAULT,
            bottomPanelCollapsed: false,
          })
        } else {
          set({
            bottomPanelPrevHeight: s.bottomPanelHeight,
            bottomPanelHeight: BOTTOM_PANEL_COLLAPSED,
            bottomPanelCollapsed: true,
          })
        }
      },
      setBackendStatus: (s) => set({ backendStatus: s }),
      setCellSize: (s) => set({ cellSize: s }),
      setActivePage: (p) => set({ activePage: p }),
      setSyncMouse: (v) => set({ syncMouse: v }),
      setSyncKeys: (v) => set({ syncKeys: v }),
      setSelectedGroup: (g) => set({ selectedGroup: g }),
      setDatasetPanelOpen: (v) => set({ datasetPanelOpen: v }),
      toggleDatasetPanel: () =>
        set({ datasetPanelOpen: !get().datasetPanelOpen }),
      setMasterDeviceId: (id) => set({ masterDeviceId: id }),
      toggleDeviceSelected: (id) => {
        const next = new Set(get().selectedDeviceIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        set({ selectedDeviceIds: next })
      },
      clearSelectedDevices: () => set({ selectedDeviceIds: new Set<string>() }),
      setShowOnboarding: (v) => set({ showOnboarding: v }),
    }),
    {
      name: 'chimera-app-store',
      partialize: (s) => ({
        sidebarCollapsed: s.sidebarCollapsed,
        bottomPanelHeight: s.bottomPanelHeight,
        bottomPanelCollapsed: s.bottomPanelCollapsed,
        bottomPanelPrevHeight: s.bottomPanelPrevHeight,
        cellSize: s.cellSize,
        activePage: s.activePage,
        syncMouse: s.syncMouse,
        syncKeys: s.syncKeys,
        selectedGroup: s.selectedGroup,
      }),
    },
  ),
)
