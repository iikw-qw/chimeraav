/**
 * Верхняя панель с уведомлениями и информацией о пользователе.
 */

import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useNotificationStore } from '../../store/notificationStore'

export default function Header() {
  const { user } = useAuthStore()
  const { unreadCount, fetchUnreadCount } = useNotificationStore()

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <button onClick={() => window.location.href = '/logs'} className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors">
          <Bell size={20} />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs w-5 h-5 flex items-center justify-center rounded-full">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-chimera-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
            {user?.email?.charAt(0).toUpperCase()}
          </div>
          <span className="text-sm text-gray-700 dark:text-gray-300 hidden sm:block">{user?.email}</span>
        </div>
      </div>
    </header>
  )
}
