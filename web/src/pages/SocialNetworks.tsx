/**
 * Настройки автопостинга по платформам, автоответ на комментарии.
 * Зависит от: settingsStore, accountStore, api/client
 */

import { useEffect, useState } from 'react'
import { useSettingsStore } from '../store/settingsStore'
import { useAccountStore } from '../store/accountStore'
import { Globe, MessageCircle, Save, ToggleLeft, ToggleRight } from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

const PLATFORMS = ['instagram', 'threads', 'telegram', 'facebook', 'tiktok', 'twitter', 'linkedin', 'vk', 'youtube', 'reddit']

const PLATFORM_COLORS: Record<string, string> = {
  instagram: '#E4405F', telegram: '#0088CC', facebook: '#1877F2', tiktok: '#FE2C55',
  twitter: '#000000', linkedin: '#0A66C2', vk: '#4C75A3', youtube: '#FF0000',
  reddit: '#FF4500', threads: '#101010',
}

export default function SocialNetworks() {
  const { settings, fetchSettings, updateSetting } = useSettingsStore()
  const { accounts, fetchAccounts } = useAccountStore()
  const [datasets, setDatasets] = useState<any[]>([])
  const [commentSettings, setCommentSettings] = useState({
    enabled: false,
    delay_min: 40,
    delay_max: 70,
    gender_filter: 'male',
    style: 'intriguing' as 'intriguing' | 'vulgar',
  })

  useEffect(() => {
    fetchSettings()
    fetchAccounts()
    loadDatasets()
    loadCommentSettings()
  }, [])

  const loadDatasets = async () => {
    try {
      const { data } = await api.get('/posts/datasets/list')
      setDatasets(data)
    } catch { /* ignore */ }
  }

  const loadCommentSettings = async () => {
    try {
      const { data } = await api.get('/settings?scope=user')
      const cs = data.find((s: any) => s.key === 'comment_autoresponse')
      if (cs) setCommentSettings(cs.value)
    } catch { /* ignore */ }
  }

  const savePlatformSettings = async (platform: string, config: any) => {
    try {
      await updateSetting(`autopost_${platform}`, config, false)
      toast.success(`Настройки ${platform} сохранены`)
    } catch {
      toast.error('Ошибка сохранения')
    }
  }

  const saveCommentSettings = async () => {
    try {
      await updateSetting('comment_autoresponse', commentSettings, false)
      toast.success('Настройки автоответа сохранены')
    } catch {
      toast.error('Ошибка сохранения')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Социальные сети</h1>

      {/* Platform settings */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PLATFORMS.map((platform) => {
          const config = settings[`autopost_${platform}`] || { enabled: false, dataset_id: '', caption_style: 'casual', schedule: 'daily' }
          const platAccounts = accounts.filter((a) => a.platform === platform)

          return (
            <div key={platform} className="card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold" style={{ backgroundColor: PLATFORM_COLORS[platform] }}>
                    {platform.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white capitalize">{platform}</h3>
                    <p className="text-xs text-gray-500">{platAccounts.length} аккаунтов</p>
                  </div>
                </div>
                <button
                  onClick={() => savePlatformSettings(platform, { ...config, enabled: !config.enabled })}
                  className="text-gray-500"
                >
                  {config.enabled ? <ToggleRight size={28} className="text-green-500" /> : <ToggleLeft size={28} />}
                </button>
              </div>

              {config.enabled && (
                <div className="space-y-3">
                  <select
                    value={config.dataset_id || ''}
                    onChange={(e) => savePlatformSettings(platform, { ...config, dataset_id: e.target.value })}
                    className="input-field text-sm"
                  >
                    <option value="">Выберите датасет</option>
                    {datasets.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.total_photos} фото)</option>)}
                  </select>
                  <select
                    value={config.caption_style || 'casual'}
                    onChange={(e) => savePlatformSettings(platform, { ...config, caption_style: e.target.value })}
                    className="input-field text-sm"
                  >
                    <option value="casual">Casual</option>
                    <option value="professional">Professional</option>
                    <option value="funny">Funny</option>
                    <option value="minimal">Minimal</option>
                    <option value="storytelling">Storytelling</option>
                  </select>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Comment auto-response */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center">
              <MessageCircle size={20} className="text-purple-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">Автоответ на комментарии</h3>
              <p className="text-sm text-gray-500">Автоматический ответ на комментарии подписчиков</p>
            </div>
          </div>
          <button onClick={() => setCommentSettings({ ...commentSettings, enabled: !commentSettings.enabled })}>
            {commentSettings.enabled ? <ToggleRight size={28} className="text-green-500" /> : <ToggleLeft size={28} className="text-gray-400" />}
          </button>
        </div>

        {commentSettings.enabled && (
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Задержка (мин)</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number" value={commentSettings.delay_min}
                    onChange={(e) => setCommentSettings({ ...commentSettings, delay_min: Number(e.target.value) })}
                    className="input-field" min={10} max={120}
                  />
                  <span className="text-gray-500">—</span>
                  <input
                    type="number" value={commentSettings.delay_max}
                    onChange={(e) => setCommentSettings({ ...commentSettings, delay_max: Number(e.target.value) })}
                    className="input-field" min={10} max={120}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Фильтр по полу</label>
                <select value={commentSettings.gender_filter} onChange={(e) => setCommentSettings({ ...commentSettings, gender_filter: e.target.value })} className="input-field">
                  <option value="male">Мужской</option>
                  <option value="female">Женский</option>
                  <option value="all">Все</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Стиль ответа</label>
              <div className="flex gap-3">
                <button
                  onClick={() => setCommentSettings({ ...commentSettings, style: 'intriguing' })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${commentSettings.style === 'intriguing' ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
                >
                  Интригующий
                </button>
                <button
                  onClick={() => setCommentSettings({ ...commentSettings, style: 'vulgar' })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${commentSettings.style === 'vulgar' ? 'bg-pink-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
                >
                  Вульгарный
                </button>
              </div>
            </div>
            <button onClick={saveCommentSettings} className="btn-primary flex items-center gap-2">
              <Save size={16} /> Сохранить
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
