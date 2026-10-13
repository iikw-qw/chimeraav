/**
 * Главный компонент приложения Chimera v5.0.
 * Маршрутизация, авторизация, Layout.
 */

import { useEffect, lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'
import Sidebar from './components/Layout/Sidebar'
import Header from './components/Layout/Header'
import LoginForm from './components/Auth/LoginForm'
import RegisterForm from './components/Auth/RegisterForm'
import { Toaster } from 'react-hot-toast'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const DeviceMap = lazy(() => import('./pages/DeviceMap'))
const Phones = lazy(() => import('./pages/Phones/PhonesPage'))
const Accounts = lazy(() => import('./pages/Accounts'))
const SocialNetworks = lazy(() => import('./pages/SocialNetworks'))
const Scheduler = lazy(() => import('./pages/Scheduler'))
const Warmup = lazy(() => import('./pages/Warmup'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Logs = lazy(() => import('./pages/Logs'))
const SettingsPage = lazy(() => import('./pages/Settings'))
const Onboarding = lazy(() => import('./components/Onboarding/OnboardingWizard'))

function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-chimera-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center p-4">
      {children}
    </div>
  )
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Sidebar />
      <div className="lg:ml-64">
        <Header />
        <main className="p-6">
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-chimera-600" />
              </div>
            }
          >
            {children}
          </Suspense>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const { isAuthenticated, isLoading, checkAuth, user } = useAuthStore()
  const { isDark } = useThemeStore()

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDark])

  useEffect(() => {
    checkAuth()
  }, [])

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'd': e.preventDefault(); window.location.href = '/'; break
          case 'm': e.preventDefault(); window.location.href = '/device-map'; break
          case 's':
            if (e.shiftKey) { e.preventDefault(); window.location.href = '/settings' }
            break
        }
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-chimera-600" />
      </div>
    )
  }

  return (
    <>
      <Toaster position="top-right" />
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? <Navigate to="/" /> : <AuthLayout><LoginForm /></AuthLayout>
          }
        />
        <Route
          path="/register"
          element={
            isAuthenticated ? <Navigate to="/" /> : <AuthLayout><RegisterForm /></AuthLayout>
          }
        />

        {!isAuthenticated ? (
          <Route path="*" element={<Navigate to="/login" />} />
        ) : user && !user.onboarding_completed ? (
          <Route path="*" element={<Suspense fallback={null}><Onboarding /></Suspense>} />
        ) : (
          <>
            <Route path="/" element={<AppLayout><Dashboard /></AppLayout>} />
            <Route path="/device-map" element={<AppLayout><DeviceMap /></AppLayout>} />
            <Route path="/phones" element={<AppLayout><Phones /></AppLayout>} />
            <Route path="/accounts" element={<AppLayout><Accounts /></AppLayout>} />
            <Route path="/social-networks" element={<AppLayout><SocialNetworks /></AppLayout>} />
            <Route path="/scheduler" element={<AppLayout><Scheduler /></AppLayout>} />
            <Route path="/warmup" element={<AppLayout><Warmup /></AppLayout>} />
            <Route path="/analytics" element={<AppLayout><Analytics /></AppLayout>} />
            <Route path="/logs" element={<AppLayout><Logs /></AppLayout>} />
            <Route path="/settings" element={<AppLayout><SettingsPage /></AppLayout>} />
            <Route path="*" element={<Navigate to="/" />} />
          </>
        )}
      </Routes>
    </>
  )
}
