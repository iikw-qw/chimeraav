/**
 * Аналитика: графики постов, подписчиков, heatmap активности.
 * Зависит от: api/client, recharts
 */

import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp } from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, Legend
} from 'recharts'
import api from '../api/client'

export default function Analytics() {
  const [overview, setOverview] = useState<any>(null)
  const [postsByDay, setPostsByDay] = useState<any[]>([])
  const [accountsComparison, setAccountsComparison] = useState<any[]>([])
  const [heatmap, setHeatmap] = useState<any[]>([])
  const [period, setPeriod] = useState(30)

  useEffect(() => {
    loadAll()
  }, [period])

  const loadAll = async () => {
    try {
      const [ov, pbd, ac, hm] = await Promise.all([
        api.get('/analytics/overview', { params: { days: period } }),
        api.get('/analytics/posts-by-day', { params: { days: period } }),
        api.get('/analytics/accounts-comparison'),
        api.get('/analytics/activity-heatmap', { params: { days: period } }),
      ])
      setOverview(ov.data)
      setPostsByDay(pbd.data)
      setAccountsComparison(ac.data)
      setHeatmap(hm.data)
    } catch { /* ignore */ }
  }

  const days = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
  const hours = Array.from({ length: 24 }, (_, i) => i)

  const getHeatmapValue = (day: number, hour: number) => {
    const item = heatmap.find((h) => h.day === day && h.hour === hour)
    return item?.count || 0
  }

  const maxHeat = Math.max(...heatmap.map((h) => h.count), 1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Аналитика</h1>
        <div className="flex gap-2">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${period === d ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
            >
              {d}д
            </button>
          ))}
        </div>
      </div>

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="card">
            <p className="text-sm text-gray-500">Постов за {period} дней</p>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">{overview.posts}</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500">Задач выполнено</p>
            <p className="text-3xl font-bold text-green-600">{overview.tasks_completed}</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500">Ошибок</p>
            <p className="text-3xl font-bold text-red-600">{overview.tasks_failed}</p>
          </div>
        </div>
      )}

      {/* Posts by day chart */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Посты по дням</h2>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={postsByDay}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" />
            <Tooltip />
            <Area type="monotone" dataKey="count" stroke="#4c6ef5" fill="#4c6ef5" fillOpacity={0.1} strokeWidth={2} name="Посты" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Accounts comparison */}
      {accountsComparison.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Сравнение аккаунтов</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={accountsComparison}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="username" tick={{ fontSize: 11 }} stroke="#9ca3af" />
              <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" />
              <Tooltip />
              <Legend />
              <Bar dataKey="followers" fill="#4c6ef5" name="Подписчики" radius={[4, 4, 0, 0]} />
              <Bar dataKey="posts" fill="#10b981" name="Посты" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Activity heatmap */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Лучшее время активности</h2>
        <div className="overflow-x-auto">
          <div className="inline-block">
            <div className="flex">
              <div className="w-10" />
              {hours.map((h) => (
                <div key={h} className="w-7 text-center text-xs text-gray-400">{h}</div>
              ))}
            </div>
            {days.map((day, dayIdx) => (
              <div key={day} className="flex items-center">
                <div className="w-10 text-xs text-gray-500 text-right pr-2">{day}</div>
                {hours.map((hour) => {
                  const value = getHeatmapValue(dayIdx, hour)
                  const intensity = value / maxHeat
                  return (
                    <div
                      key={hour}
                      className="w-7 h-7 rounded-sm m-0.5"
                      style={{
                        backgroundColor: value > 0
                          ? `rgba(76, 110, 245, ${0.1 + intensity * 0.9})`
                          : 'rgba(0,0,0,0.05)',
                      }}
                      title={`${day} ${hour}:00 — ${value} действий`}
                    />
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
