/**
 * Логи действий: таблица с фильтрами, цветовая маркировка, экспорт CSV.
 * Зависит от: api/client
 */

import { useEffect, useState } from 'react'
import { Download, Filter, RefreshCw, Search } from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

interface ActionLog {
  id: string
  device_id?: string
  account_id?: string
  action_type: string
  details: Record<string, any>
  success: boolean
  duration_ms?: number
  created_at: string
}

const LOG_LEVELS: Record<string, { label: string; class: string }> = {
  success: { label: 'INFO', class: 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400' },
  warning: { label: 'WARN', class: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400' },
  error: { label: 'ERROR', class: 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400' },
}

export default function Logs() {
  const [logs, setLogs] = useState<ActionLog[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [filters, setFilters] = useState({
    action_type: '',
    device_id: '',
    account_id: '',
    success: '' as '' | 'true' | 'false',
    days: 7,
  })

  useEffect(() => {
    loadLogs()
  }, [filters])

  const loadLogs = async () => {
    setIsLoading(true)
    try {
      const params: Record<string, any> = { limit: 200, days: filters.days }
      if (filters.action_type) params.action_type = filters.action_type
      if (filters.device_id) params.device_id = filters.device_id
      if (filters.account_id) params.account_id = filters.account_id
      if (filters.success) params.success = filters.success === 'true'
      const { data } = await api.get('/logs', { params })
      setLogs(data)
    } catch { /* ignore */ }
    setIsLoading(false)
  }

  const exportCSV = async () => {
    try {
      const response = await api.get('/logs/export', {
        params: { days: filters.days },
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = 'chimera_logs.csv'
      link.click()
      window.URL.revokeObjectURL(url)
      toast.success('Экспорт завершён')
    } catch {
      toast.error('Ошибка экспорта')
    }
  }

  const getLevel = (log: ActionLog) => {
    if (!log.success) return 'error'
    if (log.action_type.includes('warning') || log.action_type.includes('captcha')) return 'warning'
    return 'success'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Логи</h1>
        <div className="flex gap-2">
          <button onClick={loadLogs} className="btn-secondary flex items-center gap-2" disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} /> Обновить
          </button>
          <button onClick={exportCSV} className="btn-primary flex items-center gap-2">
            <Download size={16} /> Экспорт CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center gap-3 flex-wrap">
          <Filter size={16} className="text-gray-500" />
          <select
            value={filters.action_type}
            onChange={(e) => setFilters({ ...filters, action_type: e.target.value })}
            className="input-field !w-auto text-sm"
          >
            <option value="">Все типы</option>
            <option value="post">Пост</option>
            <option value="like">Лайк</option>
            <option value="follow">Подписка</option>
            <option value="comment">Комментарий</option>
            <option value="login">Вход</option>
            <option value="warmup">Прогрев</option>
            <option value="screenshot">Скриншот</option>
          </select>
          <select
            value={filters.success}
            onChange={(e) => setFilters({ ...filters, success: e.target.value as any })}
            className="input-field !w-auto text-sm"
          >
            <option value="">Все результаты</option>
            <option value="true">Успех</option>
            <option value="false">Ошибка</option>
          </select>
          <select
            value={filters.days}
            onChange={(e) => setFilters({ ...filters, days: Number(e.target.value) })}
            className="input-field !w-auto text-sm"
          >
            <option value={1}>1 день</option>
            <option value={3}>3 дня</option>
            <option value={7}>7 дней</option>
            <option value={14}>14 дней</option>
            <option value={30}>30 дней</option>
          </select>
          <span className="text-sm text-gray-500 ml-auto">{logs.length} записей</span>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Уровень</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Тип</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Устройство</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Длительность</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Детали</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Время</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => {
                const level = getLevel(log)
                const levelInfo = LOG_LEVELS[level]
                return (
                  <tr key={`${log.id}-${log.created_at}`} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td className="py-2.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${levelInfo.class}`}>
                        {levelInfo.label}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-medium text-gray-900 dark:text-white">{log.action_type}</td>
                    <td className="py-2.5 px-4 text-gray-500 text-xs font-mono">
                      {log.device_id ? log.device_id.slice(0, 8) : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-gray-500">
                      {log.duration_ms != null ? `${log.duration_ms}ms` : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-gray-500 text-xs max-w-xs truncate">
                      {JSON.stringify(log.details).slice(0, 100)}
                    </td>
                    <td className="py-2.5 px-4 text-gray-400 text-xs">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                  </tr>
                )
              })}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-500">Нет логов за выбранный период</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
