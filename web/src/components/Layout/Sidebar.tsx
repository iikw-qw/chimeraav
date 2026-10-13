/**
 * Боковая навигация приложения.
 */

import { NavLink } from 'react-router-dom'
import { useThemeStore } from '../../store/themeStore'
import {
  LayoutDashboard, Map, Smartphone, Users, Globe, Calendar,
  Flame, BarChart3, ScrollText, Settings, Sun, Moon, LogOut, Menu, X
} from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '../../store/authStore'
import { clsx } from 'clsx'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Дашборд' },
  { to: '/device-map', icon: Map, label: 'Карта устройств' },
  { to: '/phones', icon: Smartphone, label: 'Телефоны' },
  { to: '/accounts', icon: Users, label: 'Аккаунты' },
  { to: '/social-networks', icon: Globe, label: 'Соцсети' },
  { to: '/scheduler', icon: Calendar, label: 'Планировщик' },
  { to: '/warmup', icon: Flame, label: 'Прогрев' },
  { to: '/analytics', icon: BarChart3, label: 'Аналитика' },
  { to: '/logs', icon: ScrollText, label: 'Логи' },
  { to: '/settings', icon: Settings, label: 'Настройки' },
]

export default function Sidebar() {
  const { isDark, toggle } = useThemeStore()
  const { logout } = useAuthStore()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {/* Mobile hamburger */}
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-md"
        onClick={() => setCollapsed(!collapsed)}
      >
        {collapsed ? <X size={20} /> : <Menu size={20} />}
      </button>

      <aside
        className={clsx(
          'fixed left-0 top-0 h-full bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 z-40 transition-all duration-300 flex flex-col',
          collapsed ? 'w-64 translate-x-0' : '-translate-x-full lg:translate-x-0 lg:w-64'
        )}
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-chimera-500 to-chimera-700 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">Chimera</span>
            <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">v5.0</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setCollapsed(false)}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors text-sm font-medium',
                  isActive
                    ? 'bg-chimera-50 dark:bg-chimera-900/20 text-chimera-700 dark:text-chimera-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                )
              }
            >
              <item.icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom actions */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={toggle}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
            <span>{isDark ? 'Светлая тема' : 'Тёмная тема'}</span>
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            <LogOut size={20} />
            <span>Выйти</span>
          </button>
        </div>
      </aside>
    </>
  )
}
