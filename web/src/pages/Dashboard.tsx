/**
 * Дашборд: статистика, графики, быстрые действия.
 */

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Smartphone, Users, CheckSquare, AlertTriangle, Play, Pause, Flame } from 'lucide-react'
import toast from 'react-hot-toast'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import api from '../api/client'

interface Stats {
  devices: { total: number; online: number }
  accounts: { total: number }
  tasks: Record<string, number>
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [chartData, setChartData] = useState<any[]>([])
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('week')

  useEffect(() => {
    loadStats()
    loadChart()
  }, [period])

  const loadStats = async () => {
    try {
      const [devices, accounts, tasks] = await Promise.all([
        api.get('/devices/count'),
        api.get('/accounts/count'),
        api.get('/tasks/stats'),
      ])
      setStats({ devices: devices.data, accounts: accounts.data, tasks: tasks.data })
    } catch { /* loading state */ }
  }

  const loadChart = async () => {
    const days = period === 'day' ? 1 : period === 'week' ? 7 : 30
    try {
      const { data } = await api.get('/analytics/posts-by-day', { params: { days } })
      setChartData(data)
    } catch { /* ignore */ }
  }

  const startPosting = async () => {
    try {
      await api.post('/tasks/batch-action', { action: 'start_posting' })
      toast.success('Постинг запущен')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка запуска постинга')
    }
  }

  const stopPosting = async () => {
    try {
      await api.post('/tasks/batch-action', { action: 'stop_posting' })
      toast.success('Постинг остановлен')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка остановки постинга')
    }
  }

  const startWarmup = async () => {
    try {
      await api.post('/tasks/batch-action', { action: 'start_warmup' })
      toast.success('Прогрев запущен')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка запуска прогрева')
    }
  }

  const stopWarmup = async () => {
    try {
      await api.post('/tasks/batch-action', { action: 'stop_warmup' })
      toast.success('Прогрев остановлен')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка остановки прогрева')
    }
  }

  const cards = [
    { label: 'Устройства', value: stats?.devices.total ?? 0, sub: `${stats?.devices.online ?? 0} онлайн`, icon: Smartphone, color: 'bg-blue-500' },
    { label: 'Аккаунты', value: stats?.accounts.total ?? 0, sub: 'всего', icon: Users, color: 'bg-green-500' },
    { label: 'Задачи выполнены', value: stats?.tasks.completed ?? 0, sub: `${stats?.tasks.running ?? 0} в работе`, icon: CheckSquare, color: 'bg-purple-500' },
    { label: 'Ошибки', value: stats?.tasks.failed ?? 0, sub: `${stats?.tasks.dead ?? 0} мёртвых`, icon: AlertTriangle, color: 'bg-red-500' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Дашборд</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="card flex items-center gap-4"
          >
            <div className={`${card.color} p-3 rounded-xl text-white`}>
              <card.icon size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{card.value}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">{card.label}</p>
              <p className="text-xs text-gray-400">{card.sub}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Быстрые действия</h2>
        <div className="flex flex-wrap gap-3">
          <button onClick={startPosting} className="btn-primary flex items-center gap-2"><Play size={16} /> Старт постинг</button>
          <button onClick={stopPosting} className="btn-secondary flex items-center gap-2"><Pause size={16} /> Стоп постинг</button>
          <button onClick={startWarmup} className="btn-primary flex items-center gap-2 !bg-orange-500 hover:!bg-orange-600"><Flame size={16} /> Старт прогрев</button>
          <button onClick={stopWarmup} className="btn-secondary flex items-center gap-2"><Pause size={16} /> Стоп прогрев</button>
        </div>
      </div>

      {/* Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Активность</h2>
          <div className="flex gap-2">
            {(['day', 'week', 'month'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded-lg text-sm ${period === p ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
              >
                {p === 'day' ? 'День' : p === 'week' ? 'Неделя' : 'Месяц'}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
            <Tooltip />
            <Area type="monotone" dataKey="count" stroke="#4c6ef5" fill="#4c6ef5" fillOpacity={0.1} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
