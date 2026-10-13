/**
 * Настройки: глобальные, демонстрация экрана, 2Captcha, onboarding.
 * Зависит от: settingsStore, authStore, api/client
 */

import { useEffect, useState } from 'react'
import { useSettingsStore } from '../store/settingsStore'
import { useAuthStore } from '../store/authStore'
import {
  Shield, Monitor, Key, RotateCcw, Save, Globe, Eye, EyeOff,
  ToggleLeft, ToggleRight, Wifi, BookOpen
} from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { settings, fetchSettings, updateSetting } = useSettingsStore()
  const { user } = useAuthStore()
  const [captchaKey, setCaptchaKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  useEffect(() => {
    if (settings.twocaptcha_api_key) {
      setCaptchaKey(settings.twocaptcha_api_key)
    }
  }, [settings])

  const streamSettings = settings.stream_settings || {
    quality: '720p', fps: 30, grid_mode: '3x3', show_overlay: true, show_ip: true,
  }

  const antidetectSettings = settings.antidetect || {
    exif_cleanup: true, fingerprint_rotation: true, rotation_hours: 24,
  }

  const proxySettings = settings.proxy || {
    type: 'http', check_dns_leak: true, check_webrtc: false,
  }

  const updateStream = async (key: string, value: any) => {
    const updated = { ...streamSettings, [key]: value }
    await updateSetting('stream_settings', updated, true)
    toast.success('Настройки демонстрации обновлены')
  }

  const updateAntidetect = async (key: string, value: any) => {
    const updated = { ...antidetectSettings, [key]: value }
    await updateSetting('antidetect', updated, true)
    toast.success('Настройки антидетекта обновлены')
  }

  const updateProxy = async (key: string, value: any) => {
    const updated = { ...proxySettings, [key]: value }
    await updateSetting('proxy', updated, true)
    toast.success('Настройки прокси обновлены')
  }

  const saveCaptchaKey = async () => {
    try {
      await updateSetting('twocaptcha_api_key', captchaKey, true)
      toast.success('API ключ 2Captcha сохранён')
    } catch {
      toast.error('Ошибка сохранения')
    }
  }

  const resetOnboarding = async () => {
    try {
      await api.put('/settings?is_global=false', { key: 'onboarding_completed', value: false })
      toast.success('Онбординг сброшен. Обновите страницу.')
    } catch {
      toast.error('Ошибка')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Настройки</h1>

      {/* Global settings sync info */}
      <div className="card bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800">
        <div className="flex items-center gap-3">
          <Globe size={20} className="text-blue-500" />
          <div>
            <p className="font-medium text-blue-800 dark:text-blue-300">Глобальные настройки</p>
            <p className="text-sm text-blue-600 dark:text-blue-400">Синхронизируются между всеми пользователями через WebSocket</p>
          </div>
        </div>
      </div>

      {/* Stream settings */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center">
            <Monitor size={20} className="text-purple-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Демонстрация экрана</h3>
            <p className="text-sm text-gray-500">Качество, FPS, режим отображения</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Качество</label>
            <select value={streamSettings.quality} onChange={(e) => updateStream('quality', e.target.value)} className="input-field">
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">FPS</label>
            <select value={streamSettings.fps} onChange={(e) => updateStream('fps', Number(e.target.value))} className="input-field">
              <option value={15}>15 FPS</option>
              <option value={30}>30 FPS</option>
              <option value={60}>60 FPS</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Режим сетки</label>
            <select value={streamSettings.grid_mode} onChange={(e) => updateStream('grid_mode', e.target.value)} className="input-field">
              <option value="2x2">2x2</option>
              <option value="3x3">3x3</option>
              <option value="4x4">4x4</option>
            </select>
          </div>
        </div>
        <div className="flex gap-6 mt-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={streamSettings.show_overlay} onChange={(e) => updateStream('show_overlay', e.target.checked)} className="rounded" />
            <span className="text-sm text-gray-700 dark:text-gray-300">Показать оверлей</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={streamSettings.show_ip} onChange={(e) => updateStream('show_ip', e.target.checked)} className="rounded" />
            <span className="text-sm text-gray-700 dark:text-gray-300">Показать IP</span>
          </label>
        </div>
      </div>

      {/* Anti-detect */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-red-100 dark:bg-red-900/20 rounded-lg flex items-center justify-center">
            <Shield size={20} className="text-red-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Антидетект</h3>
            <p className="text-sm text-gray-500">Очистка метаданных, ротация fingerprint</p>
          </div>
        </div>
        <div className="space-y-3">
          <label className="flex items-center justify-between">
            <span className="text-sm text-gray-700 dark:text-gray-300">Очистка EXIF метаданных</span>
            <button onClick={() => updateAntidetect('exif_cleanup', !antidetectSettings.exif_cleanup)}>
              {antidetectSettings.exif_cleanup ? <ToggleRight size={28} className="text-green-500" /> : <ToggleLeft size={28} className="text-gray-400" />}
            </button>
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm text-gray-700 dark:text-gray-300">Ротация fingerprint</span>
            <button onClick={() => updateAntidetect('fingerprint_rotation', !antidetectSettings.fingerprint_rotation)}>
              {antidetectSettings.fingerprint_rotation ? <ToggleRight size={28} className="text-green-500" /> : <ToggleLeft size={28} className="text-gray-400" />}
            </button>
          </label>
          <div>
            <label className="block text-sm text-gray-700 dark:text-gray-300 mb-1">Период ротации (часы)</label>
            <input
              type="number" value={antidetectSettings.rotation_hours} min={1} max={168}
              onChange={(e) => updateAntidetect('rotation_hours', Number(e.target.value))}
              className="input-field !w-32"
            />
          </div>
        </div>
      </div>

      {/* Proxy */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center">
            <Wifi size={20} className="text-green-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Прокси</h3>
            <p className="text-sm text-gray-500">Настройки прокси и проверки</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Тип прокси</label>
            <select value={proxySettings.type} onChange={(e) => updateProxy('type', e.target.value)} className="input-field">
              <option value="http">HTTP</option>
              <option value="socks5">SOCKS5</option>
              <option value="residential">Residential</option>
            </select>
          </div>
        </div>
        <div className="flex gap-6 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={proxySettings.check_dns_leak} onChange={(e) => updateProxy('check_dns_leak', e.target.checked)} className="rounded" />
            <span className="text-sm text-gray-700 dark:text-gray-300">Проверка DNS утечек</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={proxySettings.check_webrtc} onChange={(e) => updateProxy('check_webrtc', e.target.checked)} className="rounded" />
            <span className="text-sm text-gray-700 dark:text-gray-300">Проверка WebRTC</span>
          </label>
        </div>
      </div>

      {/* 2Captcha */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-yellow-100 dark:bg-yellow-900/20 rounded-lg flex items-center justify-center">
            <Key size={20} className="text-yellow-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">2Captcha</h3>
            <p className="text-sm text-gray-500">API ключ для решения капчи</p>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              type={showKey ? 'text' : 'password'}
              value={captchaKey}
              onChange={(e) => setCaptchaKey(e.target.value)}
              className="input-field pr-10"
              placeholder="Введите API ключ 2Captcha"
            />
            <button onClick={() => setShowKey(!showKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <button onClick={saveCaptchaKey} className="btn-primary flex items-center gap-2">
            <Save size={16} /> Сохранить
          </button>
        </div>
      </div>

      {/* Onboarding reset + Manual */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center">
            <RotateCcw size={20} className="text-gray-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Дополнительно</h3>
          </div>
        </div>
        <div className="space-y-3">
          <button onClick={resetOnboarding} className="btn-secondary flex items-center gap-2">
            <RotateCcw size={16} /> Пройти настройку заново
          </button>
          <button onClick={() => window.open('/docs/SETUP_GUIDE.md', '_blank')} className="btn-secondary flex items-center gap-2">
            <BookOpen size={16} /> Методичка по использованию
          </button>
        </div>
      </div>
    </div>
  )
}
