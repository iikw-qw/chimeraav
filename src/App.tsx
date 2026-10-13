import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  HashRouter,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { TitleBar } from './components/layout/TitleBar'
import { FloatingParticles } from './components/layout/FloatingParticles'
import { LogoWatermark } from './components/layout/LogoWatermark'
import { Sidebar } from './components/layout/Sidebar'
import { BottomPanel } from './components/layout/BottomPanel'
import { LoadingScreen } from './components/layout/LoadingScreen'
import { ToastViewport } from './components/ui'
import { Dashboard } from './pages/Dashboard'
import { PhoneGrid } from './pages/PhoneGrid'
import { Messages } from './pages/Messages'
import { SocialNetworks } from './pages/SocialNetworks'
import { PostGenerator } from './pages/PostGenerator'
import { Warmup } from './pages/Warmup'
import { Datasets } from './pages/Datasets'
import { AccountsMap } from './pages/AccountsMap'
import { Scheduler } from './pages/Scheduler'
import { Monitoring } from './pages/Monitoring'
import { Logs } from './pages/Logs'
import { Settings } from './pages/Settings'
import { Captions } from './pages/Captions'
import { Uniqueizer } from './pages/Uniqueizer'
import { AutoClicker } from './pages/AutoClicker'

import { OnboardingWizard } from './pages/OnboardingWizard'
import { AuthGate } from './pages/AuthGate'
import { ErrorBoundary } from './components/ErrorBoundary'
import DeviceMap from './pages/DeviceMap'
import { ws } from './api/ws'
import { waitForBackend } from './api/client'
import { useAppStore } from './stores/appStore'
import { useHotkeys } from './hooks/useHotkeys'
import { useNotificationsBridge } from './hooks/useNotificationsBridge'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      staleTime: 1000,
      // Drop unused query data after 5 min so long-running sessions don't
      // accumulate gigabytes of cached responses.
      gcTime: 5 * 60_000,
    },
  },
})

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/phones" element={<PhoneGrid />} />
        <Route path="/warmup" element={<Warmup />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/social" element={<SocialNetworks />} />
        <Route path="/posts" element={<PostGenerator />} />
        <Route path="/datasets" element={<Datasets />} />
        <Route path="/accounts" element={<AccountsMap />} />
        <Route path="/device-map" element={<DeviceMap />} />
        <Route path="/scheduler" element={<Scheduler />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/captions" element={<Captions />} />
        <Route path="/uniqueizer" element={<Uniqueizer />} />
        <Route path="/autoclicker" element={<AutoClicker />} />
<Route path="/settings" element={<Settings />} />
      </Routes>
    </AnimatePresence>
  )
}

function AppShell() {
  useHotkeys()
  useNotificationsBridge()
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[--bg-0] text-[--txt-1]">
      <TitleBar />
      <FloatingParticles />
      <LogoWatermark src={new URL('./assets/chimera-logo.png', import.meta.url).href} />
      <div className="relative z-10 flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <main className="flex-1 overflow-hidden">
            <AnimatedRoutes />
          </main>
          <BottomPanel />
        </div>
      </div>
      <ToastViewport />
      <OnboardingWizard />
    </div>
  )
}

export default function App() {
  const [ready, setReady] = useState(false)
  const [authorised, setAuthorised] = useState(false)
  const setBackendStatus = useAppStore((s) => s.setBackendStatus)

  useEffect(() => {
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null

    const probe = (): void => {
      setBackendStatus('starting')
      waitForBackend().then((ok) => {
        if (cancelled) return
        setBackendStatus(ok ? 'ready' : 'down')
        if (ok) {
          ws.connect()
        } else {
          // Backend isn't up yet — render the shell anyway with the down
          // banner, and keep polling in the background so the UI recovers
          // automatically once the sidecar comes back.
          retryTimer = setTimeout(probe, 5000)
        }
        setReady(true)
      })
    }

    probe()

    return () => {
      cancelled = true
      if (retryTimer) clearTimeout(retryTimer)
      ws.close()
    }
  }, [setBackendStatus])

  if (!ready) return <LoadingScreen />
  if (!authorised) return <AuthGate onAuthorised={() => setAuthorised(true)} />

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <HashRouter
          future={{
            v7_startTransition: true,
            v7_relativeSplatPath: true,
          }}
        >
          <AppShell />
        </HashRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
