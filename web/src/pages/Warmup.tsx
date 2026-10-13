/**
 * Страница прогрева аккаунтов.
 * Зависит от: accountStore, settingsStore, api/client
 */

import { useEffect, useState } from 'react'
import { useAccountStore, Account } from '../store/accountStore'
import { Flame, Heart, UserPlus, MessageCircle, Scroll, Hash, ToggleLeft, ToggleRight, Save } from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

const WARMUP_ACTIONS = [
  { key: 'likes', label: 'Лайки', icon: Heart, color: 'text-red-500' },
  { key: 'follows', label: 'Подписки', icon: UserPlus, color: 'text-blue-500' },
  { key: 'comments', label: 'Комментарии', icon: MessageCircle, color: 'text-green-500' },
  { key: 'scroll', label: 'Скроллинг', icon: Scroll, color: 'text-purple-500' },
  { key: 'hashtags', label: 'Хештеги', icon: Hash, color: 'text-orange-500' },
]

export default function Warmup() {
  const { accounts, fetchAccounts, updateAccount } = useAccountStore()
  const [warmupCoeff, setWarmupCoeff] = useState(0)
  const [warmupStats, setWarmupStats] = useState<Record<string, any>>({})
  const [configs, setConfigs] = useState<Record<string, any>>({})

  useEffect(() => {
    fetchAccounts()
    loadWarmupData()
    const interval = setInterval(loadWarmupData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadWarmupData = async () => {
    try {
      const { data } = await api.get('/settings?scope=global')
      const wc = data.find((s: any) => s.key === 'warmup_coefficient')
      if (wc) setWarmupCoeff(typeof wc.value === 'number' ? wc.value : 0)

      const stats = data.find((s: any) => s.key === 'warmup_stats')
      if (stats) setWarmupStats(stats.value || {})

      const cfg = data.find((s: any) => s.key === 'warmup_configs')
      if (cfg) setConfigs(cfg.value || {})
    } catch { /* ignore */ }
  }

  const toggleWarmup = async (account: Account) => {
    try {
      await updateAccount(account.id, { warmup_enabled: !account.warmup_enabled })
      toast.success(`Прогрев ${!account.warmup_enabled ? 'включён' : 'выключен'} для ${account.username}`)
    } catch {
      toast.error('Ошибка')
    }
  }

  const saveConfig = async (accountId: string, config: any) => {
    try {
      const updated = { ...configs, [accountId]: config }
      await api.put('/settings?is_global=true', { key: 'warmup_configs', value: updated })
      setConfigs(updated)
      toast.success('Настройки прогрева сохранены')
    } catch {
      toast.error('Ошибка сохранения')
    }
  }

  const activeDevices = accounts.filter((a) => a.warmup_enabled).length
  const totalAccounts = accounts.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Прогрев аккаунтов</h1>
        <div className="flex items-center gap-2">
          <Flame size={20} className="text-orange-500" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Коэффициент: <span className="text-orange-500 font-bold">{warmupCoeff.toFixed(2)}</span>
          </span>
        </div>
      </div>

      {/* Global stats */}
      <div className="card bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/10 dark:to-amber-900/10 border-orange-200 dark:border-orange-800">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-orange-800 dark:text-orange-300">Адаптивный коэффициент</h3>
            <p className="text-sm text-orange-600 dark:text-orange-400">
              min(1, active / 50) = min(1, {activeDevices} / 50) = {warmupCoeff.toFixed(2)}
            </p>
            <p className="text-xs text-orange-500 mt-1">{activeDevices} активных из {totalAccounts} аккаунтов</p>
          </div>
          <div className="text-right">
            <div className="w-48 bg-orange-200 dark:bg-orange-800 rounded-full h-3">
              <div className="bg-orange-500 h-3 rounded-full transition-all duration-500" style={{ width: `${Math.min(warmupCoeff * 100, 100)}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Account warmup cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {accounts.map((account) => {
          const config = configs[account.id] || { likes: true, follows: true, comments: false, scroll: true, hashtags: false, intensity: 5 }
          const stats = warmupStats[account.id] || { actions_today: 0, total_actions: 0 }

          return (
            <div key={account.id} className={`card ${account.warmup_enabled ? 'ring-2 ring-orange-400/50' : ''}`}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{account.username}</h3>
                  <span className="text-xs px-2 py-0.5 rounded text-white" style={{ backgroundColor: platformColor(account.platform) }}>
                    {account.platform}
                  </span>
                </div>
                <button onClick={() => toggleWarmup(account)}>
                  {account.warmup_enabled ? <ToggleRight size={28} className="text-orange-500" /> : <ToggleLeft size={28} className="text-gray-400" />}
                </button>
              </div>

              {account.warmup_enabled && (
                <>
                  <div className="space-y-2 mb-4">
                    {WARMUP_ACTIONS.map((action) => (
                      <label key={action.key} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <action.icon size={16} className={action.color} />
                          <span className="text-sm text-gray-700 dark:text-gray-300">{action.label}</span>
                        </div>
                        <input
                          type="checkbox"
                          checked={config[action.key] ?? false}
                          onChange={(e) => saveConfig(account.id, { ...config, [action.key]: e.target.checked })}
                          className="rounded"
                        />
                      </label>
                    ))}
                  </div>

                  <div className="mb-3">
                    <label className="text-xs text-gray-500 mb-1 block">Интенсивность: {config.intensity || 5}/10</label>
                    <input
                      type="range" min={1} max={10} value={config.intensity || 5}
                      onChange={(e) => saveConfig(account.id, { ...config, intensity: Number(e.target.value) })}
                      className="w-full"
                    />
                  </div>

                  <div className="text-xs text-gray-500 flex justify-between">
                    <span>Сегодня: {stats.actions_today} действий</span>
                    <span>Всего: {stats.total_actions}</span>
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>

      {accounts.length === 0 && (
        <div className="card text-center py-12 text-gray-500">
          <Flame size={48} className="mx-auto mb-3 opacity-50" />
          <p>Нет аккаунтов для прогрева. Добавьте аккаунты на вкладке "Аккаунты".</p>
        </div>
      )}
    </div>
  )
}

function platformColor(platform: string): string {
  const colors: Record<string, string> = {
    instagram: '#E4405F', telegram: '#0088CC', facebook: '#1877F2', tiktok: '#FE2C55',
    twitter: '#000000', linkedin: '#0A66C2', vk: '#4C75A3', youtube: '#FF0000',
    reddit: '#FF4500', threads: '#101010',
  }
  return colors[platform] || '#666'
}
