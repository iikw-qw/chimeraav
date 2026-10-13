import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { NAV_ITEMS } from '../components/layout/Sidebar'
import { useAppStore } from '../stores/appStore'

export function useHotkeys() {
  const navigate = useNavigate()
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const toggleBottomPanel = useAppStore((s) => s.toggleBottomPanel)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return

      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (
          tag === 'INPUT' ||
          tag === 'TEXTAREA' ||
          tag === 'SELECT' ||
          target.isContentEditable
        ) {
          return
        }
      }

      const key = e.key.toLowerCase()

      if (key === 'b') {
        e.preventDefault()
        toggleSidebar()
        return
      }
      if (key === 'j') {
        e.preventDefault()
        toggleBottomPanel()
        return
      }
      if (/^[1-9]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1
        const target = NAV_ITEMS[idx]
        if (target) {
          e.preventDefault()
          navigate(target.path)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, toggleBottomPanel, toggleSidebar])
}
