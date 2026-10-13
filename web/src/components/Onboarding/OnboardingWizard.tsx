/**
 * Мастер первого запуска: 6 шагов с анимацией.
 * Зависит от: authStore, deviceStore, accountStore, api/client
 */

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '../../store/authStore'
import { useDeviceStore } from '../../store/deviceStore'
import { useAccountStore } from '../../store/accountStore'
import api from '../../api/client'
import {
  Smartphone, Apple, ChevronRight, ChevronLeft, Check, Upload,
  Wifi, WifiOff, Plus, X, SkipForward, Loader2, Monitor
} from 'lucide-react'
import toast from 'react-hot-toast'

const STEPS = [
  'Выбор платформы',
  'Настройка телефона',
  'Подключение устройств',
  'Загрузка фотографий',
  'Добавление аккаунтов',
  'Готово',
]

const PLATFORMS = ['instagram', 'threads', 'telegram', 'facebook', 'reddit', 'tiktok', 'twitter', 'linkedin', 'vk', 'youtube'] as const

export default function OnboardingWizard() {
  const [step, setStep] = useState(0)
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
  const [devices, setDevices] = useState<any[]>([])
  const [photos, setPhotos] = useState<File[]>([])
  const [accounts, setAccounts] = useState<Array<{ platform: string; username: string; password: string; device_id?: string }>>([])
  const [scanning, setScanning] = useState(false)
  const { setOnboardingCompleted } = useAuthStore()
  const { addDevice, fetchDevices, devices: storeDevices } = useDeviceStore()
  const { addAccount } = useAccountStore()

  const finishOnboarding = async () => {
    try {
      await api.put('/settings?is_global=false', { key: 'onboarding_completed', value: true })
      const { data } = await api.get('/auth/me')
      setOnboardingCompleted()
      toast.success('Настройка завершена!')
    } catch {
      toast.error('Ошибка сохранения')
    }
  }

  const scanDevices = async () => {
    setScanning(true)
    try {
      const { data } = await api.get('/devices/discover')
      setDevices(data.devices || [])
    } catch { /* ignore */ }
    setScanning(false)
  }

  const addManualDevice = async (name: string, ip: string, type: 'android' | 'ios') => {
    try {
      const device = await addDevice({ name, ip_address: ip, device_type: type })
      setDevices((prev) => [...prev, device])
      toast.success('Устройство добавлено')
    } catch {
      toast.error('Ошибка добавления устройства')
    }
  }

  const next = () => setStep((s) => Math.min(s + 1, 5))
  const prev = () => setStep((s) => Math.max(s - 1, 0))

  return (
    <div className="min-h-screen bg-gradient-to-br from-chimera-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-3xl"
      >
        {/* Stepper */}
        <div className="flex items-center justify-between mb-8 px-4">
          {STEPS.map((label, i) => (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center">
                <motion.div
                  animate={{
                    scale: i === step ? 1.1 : 1,
                    backgroundColor: i <= step ? '#4c6ef5' : '#d1d5db',
                  }}
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                >
                  {i < step ? <Check size={18} /> : i + 1}
                </motion.div>
                <span className="text-xs mt-1 text-gray-500 dark:text-gray-400 text-center max-w-[80px]">
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`w-8 sm:w-16 h-0.5 mx-1 ${i < step ? 'bg-chimera-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
              )}
            </div>
          ))}
        </div>

        <div className="card min-h-[400px] flex flex-col">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -50 }}
              transition={{ duration: 0.3 }}
              className="flex-1"
            >
              {step === 0 && <StepPlatform selected={selectedPlatforms} setSelected={setSelectedPlatforms} />}
              {step === 1 && <StepInstructions platforms={selectedPlatforms} />}
              {step === 2 && <StepDevices devices={devices} scanning={scanning} onScan={scanDevices} onAdd={addManualDevice} />}
              {step === 3 && <StepPhotos photos={photos} setPhotos={setPhotos} />}
              {step === 4 && <StepAccounts accounts={accounts} setAccounts={setAccounts} devices={storeDevices} />}
              {step === 5 && <StepFinish devicesCount={storeDevices.length} accountsCount={accounts.length} photosCount={photos.length} />}
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={prev}
              disabled={step === 0}
              className="btn-secondary flex items-center gap-2 disabled:opacity-30"
            >
              <ChevronLeft size={16} /> Назад
            </button>
            <div className="flex gap-3">
              {(step === 3 || step === 4) && (
                <button onClick={next} className="btn-secondary flex items-center gap-2">
                  <SkipForward size={16} /> Пропустить
                </button>
              )}
              {step < 5 ? (
                <button onClick={next} className="btn-primary flex items-center gap-2">
                  Далее <ChevronRight size={16} />
                </button>
              ) : (
                <button onClick={finishOnboarding} className="btn-primary flex items-center gap-2">
                  <Check size={16} /> Начать работу
                </button>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

function StepPlatform({ selected, setSelected }: { selected: string[]; setSelected: (v: string[]) => void }) {
  const toggle = (t: string) => {
    setSelected(selected.includes(t) ? selected.filter((s) => s !== t) : [...selected, t])
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Выберите платформы</h2>
      <p className="text-gray-500 dark:text-gray-400 mb-6">На каких устройствах вы планируете работать?</p>
      <div className="grid grid-cols-2 gap-4">
        {(['android', 'ios'] as const).map((type) => (
          <motion.button
            key={type}
            onClick={() => toggle(type)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={`p-8 rounded-xl border-2 flex flex-col items-center gap-3 transition-colors ${
              selected.includes(type)
                ? 'border-chimera-500 bg-chimera-50 dark:bg-chimera-900/20'
                : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'
            }`}
          >
            {type === 'android' ? <Smartphone size={48} className="text-green-500" /> : <Apple size={48} className="text-gray-700 dark:text-gray-300" />}
            <span className="text-lg font-semibold text-gray-900 dark:text-white">
              {type === 'android' ? 'Android' : 'iOS'}
            </span>
            {selected.includes(type) && <Check className="text-chimera-500" size={24} />}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

function StepInstructions({ platforms }: { platforms: string[] }) {
  const [tab, setTab] = useState<'android' | 'ios'>(platforms.includes('android') ? 'android' : 'ios')

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Настройка телефона</h2>
      <div className="flex gap-2 mb-4">
        {platforms.includes('android') && (
          <button onClick={() => setTab('android')} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === 'android' ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}>Android</button>
        )}
        {platforms.includes('ios') && (
          <button onClick={() => setTab('ios')} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === 'ios' ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}>iOS</button>
        )}
      </div>

      <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
        {tab === 'android' ? (
          <>
            <InstructionItem num={1} text="Откройте Настройки → О телефоне → 7 раз нажмите на 'Номер сборки' для режима разработчика" />
            <InstructionItem num={2} text="Настройки → Для разработчиков → Включите 'Отладка по USB'" />
            <InstructionItem num={3} text="Настройки → Экран → 'Не выключать при зарядке'" />
            <InstructionItem num={4} text="Установите Chimera Agent APK на телефон" />
            <InstructionItem num={5} text="Подключите телефон к той же Wi-Fi сети, что и сервер" />
            <InstructionItem num={6} text="Настройте прокси при необходимости (Настройки → Wi-Fi → Прокси)" />
          </>
        ) : (
          <>
            <InstructionItem num={1} text="Определите версию iOS и чип: Настройки → Основные → Об устройстве" />
            <h4 className="font-semibold text-gray-800 dark:text-gray-200 mt-4">Jailbreak инструменты:</h4>
            <InstructionItem num={2} text="checkra1n: для A7-A11 (iPhone 5s – X), iOS 12-14. Скачайте с checkra.in, подключите USB, введите DFU режим" />
            <InstructionItem num={3} text="unc0ver: для A12-A15, iOS 14.0-14.8. Скачайте через AltStore, установите, нажмите Jailbreak" />
            <InstructionItem num={4} text="Dopamine: для A12+, iOS 15.0-16.6.1. Скачайте через TrollStore, установите" />
            <InstructionItem num={5} text="Установите Cydia/Sileo → OpenSSH → WebDriverAgent" />
            <InstructionItem num={6} text="Скрытие JB: Liberty Lite, Shadow (repo.packix.com), A-Bypass" />
            <InstructionItem num={7} text="На Mac: brew install node → npm install -g appium → appium driver install xcuitest" />
            <InstructionItem num={8} text="Настройте прокси: через mobileconfig профиль или на роутере (iptables/VLAN)" />
          </>
        )}
      </div>
    </div>
  )
}

function InstructionItem({ num, text }: { num: number; text: string }) {
  return (
    <div className="flex gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
      <div className="w-7 h-7 bg-chimera-500 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
        {num}
      </div>
      <p className="text-sm text-gray-700 dark:text-gray-300">{text}</p>
    </div>
  )
}

function StepDevices({ devices, scanning, onScan, onAdd }: {
  devices: any[]; scanning: boolean; onScan: () => void; onAdd: (name: string, ip: string, type: 'android' | 'ios') => void
}) {
  const [showManual, setShowManual] = useState(false)
  const [name, setName] = useState('')
  const [ip, setIp] = useState('')
  const [type, setType] = useState<'android' | 'ios'>('android')

  const handleAdd = () => {
    if (name && ip) {
      onAdd(name, ip, type)
      setName('')
      setIp('')
      setShowManual(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Подключение устройств</h2>
      <p className="text-gray-500 dark:text-gray-400 mb-4">Найденные устройства в вашей сети</p>

      <div className="flex gap-3 mb-4">
        <button onClick={onScan} className="btn-primary flex items-center gap-2" disabled={scanning}>
          {scanning ? <Loader2 size={16} className="animate-spin" /> : <Wifi size={16} />}
          {scanning ? 'Поиск...' : 'Сканировать сеть'}
        </button>
        <button onClick={() => setShowManual(true)} className="btn-secondary flex items-center gap-2">
          <Plus size={16} /> Добавить вручную
        </button>
      </div>

      {showManual && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mb-4 p-4 border border-gray-200 dark:border-gray-600 rounded-lg space-y-3">
          <input value={name} onChange={(e) => setName(e.target.value)} className="input-field" placeholder="Имя устройства" />
          <input value={ip} onChange={(e) => setIp(e.target.value)} className="input-field" placeholder="IP адрес" />
          <select value={type} onChange={(e) => setType(e.target.value as any)} className="input-field">
            <option value="android">Android</option>
            <option value="ios">iOS</option>
          </select>
          <div className="flex gap-2">
            <button onClick={handleAdd} className="btn-primary">Добавить</button>
            <button onClick={() => setShowManual(false)} className="btn-secondary">Отмена</button>
          </div>
        </motion.div>
      )}

      <div className="space-y-2 max-h-[200px] overflow-y-auto">
        {devices.length > 0 ? devices.map((d: any, i: number) => (
          <div key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <div className="flex items-center gap-3">
              <Smartphone size={20} className="text-chimera-500" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white text-sm">{d.name || d.model}</p>
                <p className="text-xs text-gray-500">{d.ip_address} • {d.device_type}</p>
              </div>
            </div>
            <Check size={18} className="text-green-500" />
          </div>
        )) : (
          <div className="text-center py-8 text-gray-500">
            <Monitor size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">Устройства не найдены. Нажмите 'Сканировать' или добавьте вручную.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function StepPhotos({ photos, setPhotos }: { photos: File[]; setPhotos: (f: File[]) => void }) {
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'))
    setPhotos([...photos, ...files])
  }, [photos, setPhotos])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files).filter((f) => f.type.startsWith('image/'))
      setPhotos([...photos, ...files])
    }
  }

  const removePhoto = (i: number) => {
    setPhotos(photos.filter((_, idx) => idx !== i))
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Загрузка фотографий</h2>
      <p className="text-gray-500 dark:text-gray-400 mb-4">Загрузите фото для автопостинга. EXIF-данные будут автоматически очищены.</p>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center hover:border-chimera-500 transition-colors cursor-pointer"
        onClick={() => document.getElementById('photo-input')?.click()}
      >
        <Upload size={32} className="mx-auto mb-3 text-gray-400" />
        <p className="text-gray-600 dark:text-gray-400">Перетащите фотографии сюда</p>
        <p className="text-sm text-gray-400 mt-1">или нажмите для выбора</p>
        <input id="photo-input" type="file" multiple accept="image/*" className="hidden" onChange={handleFileInput} />
      </div>

      {photos.length > 0 && (
        <div className="mt-4 grid grid-cols-6 gap-2 max-h-[150px] overflow-y-auto">
          {photos.map((file, i) => (
            <div key={i} className="relative aspect-square rounded-lg overflow-hidden group">
              <img src={URL.createObjectURL(file)} alt="" className="w-full h-full object-cover" />
              <button
                onClick={(e) => { e.stopPropagation(); removePhoto(i) }}
                className="absolute top-1 right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={12} className="text-white" />
              </button>
            </div>
          ))}
        </div>
      )}
      <p className="text-sm text-gray-400 mt-2">{photos.length} фото загружено</p>
    </div>
  )
}

function StepAccounts({ accounts, setAccounts, devices }: {
  accounts: Array<{ platform: string; username: string; password: string; device_id?: string }>
  setAccounts: (a: any[]) => void
  devices: any[]
}) {
  const [platform, setPlatform] = useState('instagram')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [deviceId, setDeviceId] = useState('')

  const addAcc = () => {
    if (username && password) {
      setAccounts([...accounts, { platform, username, password, device_id: deviceId || undefined }])
      setUsername('')
      setPassword('')
    }
  }

  const removeAcc = (i: number) => setAccounts(accounts.filter((_, idx) => idx !== i))

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Добавление аккаунтов</h2>
      <p className="text-gray-500 dark:text-gray-400 mb-4">Привяжите аккаунты соцсетей к устройствам</p>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="input-field">
          {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)} className="input-field">
          <option value="">Без привязки</option>
          {devices.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input value={username} onChange={(e) => setUsername(e.target.value)} className="input-field" placeholder="Логин" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" placeholder="Пароль" />
      </div>
      <button onClick={addAcc} className="btn-primary flex items-center gap-2 mb-4"><Plus size={16} /> Добавить аккаунт</button>

      <div className="space-y-2 max-h-[150px] overflow-y-auto">
        {accounts.map((a, i) => (
          <div key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <div>
              <span className="text-sm font-medium text-gray-900 dark:text-white">{a.username}</span>
              <span className="text-xs text-gray-500 ml-2">{a.platform}</span>
            </div>
            <button onClick={() => removeAcc(i)} className="text-red-400 hover:text-red-600"><X size={16} /></button>
          </div>
        ))}
      </div>
    </div>
  )
}

function StepFinish({ devicesCount, accountsCount, photosCount }: { devicesCount: number; accountsCount: number; photosCount: number }) {
  return (
    <div className="text-center py-8">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 200 }}
        className="w-20 h-20 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-6"
      >
        <Check size={40} className="text-green-600" />
      </motion.div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Всё готово!</h2>
      <div className="flex justify-center gap-8 mb-6">
        <div className="text-center">
          <p className="text-3xl font-bold text-chimera-600">{devicesCount}</p>
          <p className="text-sm text-gray-500">устройств</p>
        </div>
        <div className="text-center">
          <p className="text-3xl font-bold text-chimera-600">{accountsCount}</p>
          <p className="text-sm text-gray-500">аккаунтов</p>
        </div>
        <div className="text-center">
          <p className="text-3xl font-bold text-chimera-600">{photosCount}</p>
          <p className="text-sm text-gray-500">фото</p>
        </div>
      </div>
      <p className="text-gray-500 dark:text-gray-400">Нажмите «Начать работу» для перехода к дашборду</p>
    </div>
  )
}
