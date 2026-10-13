import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Cable,
  Camera,
  Download,
  Rocket,
  ScanSearch,
  Settings2,
  Smartphone,
  Apple,
  UserPlus,
  KeyRound,
} from 'lucide-react'
import { Badge, Button, Input, ProgressBar } from '../components/ui'
import { cn } from '../lib/cn'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'
import { useSaveSettings, useSettings } from '../hooks/useSettings'
import { useAppStore } from '../stores/appStore'

type StepKey =
  | 'platform'
  | 'connect'
  | 'usb'
  | 'ios_setup'
  | 'ios_jailbreak'
  | 'accounts'
  | 'media'
  | 'done'

type Platform = 'android' | 'ios' | null

function buildSteps(p: Platform): Array<{ key: StepKey; title: string; icon: React.ReactNode }> {
  const base: Array<{ key: StepKey; title: string; icon: React.ReactNode }> = [
    { key: 'platform', title: 'Платформа', icon: <Smartphone className="h-4 w-4" /> },
    { key: 'connect', title: 'Подключите телефоны', icon: <Cable className="h-4 w-4" /> },
  ]
  if (p === 'android') {
    base.push({ key: 'usb', title: 'USB-отладка', icon: <Settings2 className="h-4 w-4" /> })
  } else if (p === 'ios') {
    base.push({ key: 'ios_setup', title: 'Настройка iOS', icon: <Apple className="h-4 w-4" /> })
    base.push({ key: 'ios_jailbreak', title: 'Джейлбрейк (опц.)', icon: <KeyRound className="h-4 w-4" /> })
  }
  base.push({ key: 'accounts', title: 'Добавьте аккаунты', icon: <UserPlus className="h-4 w-4" /> })
  base.push({ key: 'media', title: 'Загрузите фото', icon: <Camera className="h-4 w-4" /> })
  base.push({ key: 'done', title: 'Готово!', icon: <Rocket className="h-4 w-4" /> })
  return base
}

export function OnboardingWizard() {
  const { data: settings } = useSettings()
  const save = useSaveSettings()
  const showOnboarding = useAppStore((s) => s.showOnboarding)
  const setShowOnboarding = useAppStore((s) => s.setShowOnboarding)
  const [open, setOpen] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)
  const [platform, setPlatform] = useState<Platform>(null)

  useEffect(() => {
    if (settings && settings.onboarding_completed !== true) {
      setOpen(true)
    }
  }, [settings])

  useEffect(() => {
    if (showOnboarding) {
      setStepIdx(0)
      setPlatform(null)
      setOpen(true)
    }
  }, [showOnboarding])

  const STEPS = useMemo(() => buildSteps(platform), [platform])

  const close = async () => {
    try {
      await save.mutateAsync({ onboarding_completed: true })
    } catch {
      // ignore
    }
    setShowOnboarding(false)
    setOpen(false)
  }

  const next = () => setStepIdx((i) => Math.min(STEPS.length - 1, i + 1))
  const back = () => setStepIdx((i) => Math.max(0, i - 1))

  const progress = ((stepIdx + 1) / STEPS.length) * 100
  const step = STEPS[stepIdx]

  if (!open) return null

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[90] flex items-center justify-center bg-[--bg-0]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="relative w-full max-w-lg rounded-2xl border border-[--line-1] bg-[--bg-1] shadow-2xl"
        >
          <div className="border-b border-[--line-1] px-6 pt-5 pb-4">
            <div className="mb-3 flex items-center justify-between text-xs text-[--txt-3]">
              <span>
                Шаг {stepIdx + 1} из {STEPS.length}
              </span>
              <span>{step.title}</span>
            </div>
            <ProgressBar value={progress} />
            <div className="mt-4 flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[--blue]/10 text-[--blue]">
                {step.icon}
              </div>
              <h2 className="text-lg font-semibold text-[--txt-1]">{step.title}</h2>
            </div>
          </div>

          <div className="p-6">
            {step.key === 'platform' && (
              <PlatformStep platform={platform} setPlatform={setPlatform} />
            )}
            {step.key === 'connect' && <ConnectStep />}
            {step.key === 'usb' && <UsbStep />}
            {step.key === 'ios_setup' && <IosSetupStep />}
            {step.key === 'ios_jailbreak' && <IosJailbreakStep />}
            {step.key === 'accounts' && <AccountsStep />}
            {step.key === 'media' && <MediaStep />}
            {step.key === 'done' && <DoneStep />}
          </div>

          <div className="flex items-center justify-between border-t border-[--line-1] px-6 py-4">
            <Button
              variant="ghost"
              leftIcon={<ArrowLeft className="h-3.5 w-3.5" />}
              onClick={back}
              disabled={stepIdx === 0}
            >
              Назад
            </Button>
            <div className="flex items-center gap-2">
              {(['media', 'accounts', 'ios_jailbreak'] as StepKey[]).includes(step.key) && (
                <Button variant="ghost" onClick={next}>
                  {step.key === 'media' ? 'Пропустить фото' : 'Пропустить'}
                </Button>
              )}
              {step.key === 'done' ? (
                <Button
                  variant="primary"
                  leftIcon={<Rocket className="h-4 w-4" />}
                  onClick={close}
                  loading={save.isPending}
                >
                  Начать работу
                </Button>
              ) : (
                <Button
                  variant="primary"
                  rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
                  onClick={next}
                  disabled={step.key === 'platform' && platform === null}
                >
                  Далее
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  )
}

interface ToolsStatus {
  adb: { available: boolean; path: string | null }
  ios: { available: boolean; path: string | null }
  tools_root: string
}

function ConnectStep() {
  const [scanning, setScanning] = useState(false)
  const [devices, setDevices] = useState<
    Array<{ id: string; name: string; platform: string; status?: string }>
  >([])
  const [status, setStatus] = useState<ToolsStatus | null>(null)
  const [installing, setInstalling] = useState<'all' | 'adb' | 'ios' | null>(null)

  const refreshStatus = async () => {
    try {
      const { data } = await api.get<ToolsStatus>('/api/tools/status')
      setStatus(data)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    refreshStatus()
  }, [])

  const installTool = async (target: 'all' | 'adb' | 'ios') => {
    setInstalling(target)
    try {
      const { data } = await api.post<{
        ok: boolean
        error?: string
        status: ToolsStatus
      }>('/api/tools/install', { target })
      if (data.ok) {
        toast.success(
          target === 'all'
            ? 'Инструменты установлены'
            : target === 'adb'
            ? 'ADB установлен'
            : 'libimobiledevice установлен',
        )
        setStatus(data.status)
      } else {
        toast.danger(`Установка не удалась: ${data.error ?? 'unknown'}`)
      }
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setInstalling(null)
    }
  }

  const scan = async () => {
    setScanning(true)
    try {
      const { data } = await api.post<{
        devices: Array<{ id: string; name: string; platform: string; status?: string }>
        android_available: boolean
        ios_available: boolean
      }>('/api/devices/scan')
      setDevices(data.devices)
      setStatus((s) =>
        s
          ? {
              ...s,
              adb: { ...s.adb, available: data.android_available },
              ios: { ...s.ios, available: data.ios_available },
            }
          : s,
      )
      const unauthorized = data.devices.filter(
        (d) => (d as unknown as { status?: string }).status === 'unauthorized',
      )
      if (data.devices.length === 0) {
        const hints: string[] = []
        if (!data.android_available) hints.push('ADB не установлен')
        if (!data.ios_available) hints.push('libimobiledevice не установлен')
        const tail = hints.length ? ` (${hints.join(', ')})` : ''
        toast.warning(`Устройства не найдены${tail}. Проверьте USB и отладку.`)
      } else if (unauthorized.length > 0) {
        toast.warning(
          `Найдено ${data.devices.length} устройств, но ${unauthorized.length} ждут подтверждения отладки. На телефоне нажмите «Разрешить отладку по USB».`,
        )
      } else {
        toast.success(`Найдено устройств: ${data.devices.length}`)
      }
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setScanning(false)
    }
  }

  const adbMissing = status?.adb.available === false
  const iosMissing = status?.ios.available === false

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center rounded-xl border border-dashed border-[--line-2] bg-[--bg-3]/30 py-8">
        <Cable className="h-12 w-12 text-[--blue]/60" />
      </div>
      <p className="text-sm text-[--txt-2]">
        Подключите ваши Android- или iOS-телефоны к компьютеру через USB. Для Android включите
        отладку, для iOS — доверьте компьютеру.
      </p>

      {(adbMissing || iosMissing) && (
        <div className="rounded-lg border border-[--yellow]/40 bg-[--yellow]/10 p-3 text-xs text-[--txt-1]">
          <div className="mb-2 font-medium">
            Необходимые инструменты не установлены
          </div>
          <div className="mb-2 flex items-center gap-2 text-[--txt-2]">
            <span>ADB (Android):</span>
            {status?.adb.available ? (
              <Badge variant="success">ok</Badge>
            ) : (
              <Badge variant="warning">не установлен</Badge>
            )}
          </div>
          <div className="mb-3 flex items-center gap-2 text-[--txt-2]">
            <span>libimobiledevice (iOS):</span>
            {status?.ios.available ? (
              <Badge variant="success">ok</Badge>
            ) : (
              <Badge variant="warning">не установлен</Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<Download className="h-3.5 w-3.5" />}
              loading={installing === 'all'}
              disabled={installing !== null}
              onClick={() => installTool('all')}
            >
              Установить всё
            </Button>
            {adbMissing && (
              <Button
                variant="ghost"
                size="sm"
                loading={installing === 'adb'}
                disabled={installing !== null}
                onClick={() => installTool('adb')}
              >
                Только ADB
              </Button>
            )}
            {iosMissing && (
              <Button
                variant="ghost"
                size="sm"
                loading={installing === 'ios'}
                disabled={installing !== null}
                onClick={() => installTool('ios')}
              >
                Только iOS
              </Button>
            )}
          </div>
        </div>
      )}

      <Button
        variant="primary"
        leftIcon={<ScanSearch className="h-4 w-4" />}
        onClick={scan}
        loading={scanning}
      >
        Сканировать
      </Button>
      {devices.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium text-[--txt-2]">Найдено ({devices.length})</div>
          {devices.map((d) => {
            const unauthorized = d.status === 'unauthorized'
            return (
              <div
                key={d.id}
                className={cn(
                  'flex items-center gap-2 rounded-md border px-3 py-2 text-sm',
                  unauthorized
                    ? 'border-[--amber]/40 bg-[--amber]/10'
                    : 'border-[--line-1] bg-[--bg-2]',
                )}
              >
                <Check
                  className={cn(
                    'h-3.5 w-3.5',
                    unauthorized ? 'text-[--amber]' : 'text-[--green]',
                  )}
                />
                <Badge variant="info">{d.platform}</Badge>
                <span className="text-[--txt-1]">{d.name}</span>
                {unauthorized && (
                  <Badge variant="warning">подтвердите отладку</Badge>
                )}
                <span className="ml-auto font-mono text-[10px] text-[--txt-3]">
                  {d.id.slice(0, 8)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function UsbStep() {
  const instructions = [
    'Откройте Настройки → О телефоне',
    'Нажмите «Номер сборки» 7 раз, чтобы активировать режим разработчика',
    'Вернитесь в Настройки → Система → Для разработчиков',
    'Включите переключатель «Отладка по USB»',
    'Разрешите отладку при подключении (нажмите OK на телефоне)',
    'Агент Chimera установится автоматически при подключении по USB (APK Deployer)',
  ]
  return (
    <div className="space-y-3">
      <p className="text-sm text-[--txt-2]">
        На каждом подключённом телефоне выполните следующие шаги:
      </p>
      <ol className="space-y-2">
        {instructions.map((text, i) => (
          <li
            key={i}
            className="flex items-start gap-3 rounded-md border border-[--line-1] bg-[--bg-2] p-3 text-sm"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[--blue]/15 text-xs font-medium text-[--blue]">
              {i + 1}
            </span>
            <span className="text-[--txt-1]">{text}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

const PLATFORMS = [
  'instagram',
  'tiktok',
  'telegram',
  'twitter',
  'facebook',
  'youtube',
  'reddit',
  'threads',
]

function AccountsStep() {
  const [platform, setPlatform] = useState('instagram')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [added, setAdded] = useState<Array<{ platform: string; username: string }>>([])
  const [busy, setBusy] = useState(false)

  const add = async () => {
    if (!username.trim()) return
    setBusy(true)
    try {
      await api.post('/api/accounts', {
        platform,
        username: username.trim(),
        password: password || null,
      })
      setAdded((prev) => [...prev, { platform, username: username.trim() }])
      setUsername('')
      setPassword('')
      toast.success('Аккаунт добавлен')
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[--txt-2]">
        Добавьте хотя бы один аккаунт. Это можно сделать и позже в разделе «Соцсети».
      </p>
      <div className="grid grid-cols-3 gap-2">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-10 rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] focus:border-[--blue] focus:outline-none"
        >
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <Input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="username"
        />
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
        />
      </div>
      <Button variant="secondary" size="sm" onClick={add} disabled={!username.trim() || busy}>
        Добавить аккаунт
      </Button>
      {added.length > 0 && (
        <div className="space-y-1.5">
          {added.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-md border border-[--line-1] bg-[--bg-2] px-3 py-2 text-sm"
            >
              <Check className="h-3.5 w-3.5 text-[--green]" />
              <Badge variant="info">{a.platform}</Badge>
              <span className="text-[--txt-1]">{a.username}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MediaStep() {
  const [name, setName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = async () => {
    if (!name.trim() || files.length === 0) return
    setBusy(true)
    try {
      const form = new FormData()
      form.append('name', name.trim())
      for (const f of files) form.append('files', f)
      await api.post('/api/datasets/upload', form)
      toast.success(`Загружено ${files.length} файл(ов)`)
      setName('')
      setFiles([])
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[--txt-2]">
        Загрузите первый набор фото — он станет датасетом для генерации постов.
      </p>
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Название датасета"
      />
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          setFiles(Array.from(e.dataTransfer.files))
        }}
        className="flex h-32 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-[--line-2] text-xs hover:border-[--blue] hover:bg-[--blue]/5"
      >
        <Camera className="mb-1 h-5 w-5 text-[--txt-2]" />
        {files.length > 0 ? (
          <span className="text-[--txt-1]">Выбрано {files.length} файл(ов)</span>
        ) : (
          <span className="text-[--txt-3]">Перетащите или выберите файлы</span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
      />
      <Button
        variant="secondary"
        size="sm"
        onClick={upload}
        disabled={!name.trim() || files.length === 0 || busy}
      >
        Загрузить
      </Button>
    </div>
  )
}

function PlatformStep({
  platform,
  setPlatform,
}: {
  platform: Platform
  setPlatform: (p: Platform) => void
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-[--txt-2]">
        Выберите платформу телефонов, которые будут подключены к Chimera. Шаги
        настройки и инструкции зависят от выбранной операционной системы.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => setPlatform('android')}
          className={cn(
            'flex flex-col items-center gap-2 rounded-xl border-2 p-5 transition-colors',
            platform === 'android'
              ? 'border-[--blue] bg-[--blue]/10'
              : 'border-[--line-2] hover:border-[--line-3]',
          )}
        >
          <Smartphone className="h-10 w-10 text-[--green]" />
          <span className="text-base font-semibold text-[--txt-1]">Android</span>
          <span className="text-center text-[11px] text-[--txt-3]">
            Любой смартфон с USB-отладкой. Самый простой путь.
          </span>
        </button>
        <button
          type="button"
          onClick={() => setPlatform('ios')}
          className={cn(
            'flex flex-col items-center gap-2 rounded-xl border-2 p-5 transition-colors',
            platform === 'ios'
              ? 'border-[--blue] bg-[--blue]/10'
              : 'border-[--line-2] hover:border-[--line-3]',
          )}
        >
          <Apple className="h-10 w-10 text-[--txt-1]" />
          <span className="text-base font-semibold text-[--txt-1]">iOS / iPhone</span>
          <span className="text-center text-[11px] text-[--txt-3]">
            iPhone через WebDriverAgent или джейлбрейк (полная инструкция далее).
          </span>
        </button>
      </div>
    </div>
  )
}

function IosSetupStep() {
  const steps = [
    'Подключите iPhone к компьютеру кабелем Lightning/USB-C.',
    'На iPhone нажмите «Доверять этому компьютеру» и введите код-пароль.',
    'В Chimera на следующем шаге будет установлен libimobiledevice — это разрешает считывать UDID и снимать скриншоты без джейлбрейка.',
    'Для управления нажатиями нужен WebDriverAgent — Chimera установит его автоматически (требуется бесплатный Apple ID).',
    'Откройте «Настройки → Основные → VPN и управление устройством», доверяйте сертификату разработчика.',
  ]
  return (
    <div className="space-y-3">
      <p className="text-sm text-[--txt-2]">
        Базовая настройка iPhone <b>без джейлбрейка</b>. Подходит большинству пользователей.
      </p>
      <ol className="space-y-2">
        {steps.map((t, i) => (
          <li
            key={i}
            className="flex items-start gap-3 rounded-md border border-[--line-1] bg-[--bg-2] p-3 text-sm"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[--blue]/15 text-xs font-medium text-[--blue]">
              {i + 1}
            </span>
            <span className="text-[--txt-1]">{t}</span>
          </li>
        ))}
      </ol>
      <div className="rounded-md border border-[--blue]/30 bg-[--blue]/5 p-3 text-xs text-[--txt-2]">
        Без джейлбрейка доступны: стрим экрана, скриншоты, запуск приложений по
        bundle id, наблюдение за сетевой активностью. Для эмуляции нажатий и
        полного антидетекта рекомендуется джейлбрейк (следующий шаг).
      </div>
    </div>
  )
}

function IosJailbreakStep() {
  const items: Array<{ title: string; body: string }> = [
    {
      title: '1. Что даёт джейлбрейк',
      body:
        'Полный контроль: эмуляция касаний на низком уровне, изменение device fingerprint (IMEI, UUID, MAC), установка Frida, обход Jailbreak Detection в Instagram/TikTok, доступ к файловой системе.',
    },
    {
      title: '2. Какой инструмент выбрать',
      body:
        'iOS 15.0–16.6.1 → palera1n (semi-tethered). iOS 16.7+ → Dopamine (требует A12+). iOS 14 — checkra1n. Скачивайте только с официальных сайтов: palera.in, dopamine.iso.cool, checkra.in.',
    },
    {
      title: '3. Подготовка',
      body:
        '— Создайте полный backup в Finder/iTunes.\n— Отключите «Найти iPhone» (Apple ID → iCloud → Найти iPhone → Off).\n— Полный заряд батареи и оригинальный кабель.',
    },
    {
      title: '4. Установка',
      body:
        'Подключите iPhone, запустите palera1n/Dopamine, переведите устройство в DFU (палец на Power+Home/Volume Down 8 секунд). Утилита перезапустит iPhone в jailbroken-режим. Через несколько минут в системе появится приложение Sileo (или Cydia).',
    },
    {
      title: '5. Установите твики для Chimera',
      body:
        '— OpenSSH (доступ Chimera к телефону по сети).\n— Filza (файловый менеджер).\n— AppSync Unified (запуск unsigned IPA).\n— Liberty Lite (обход Jailbreak Detection).\n— Frida server (для рантайм-инспекции).',
    },
    {
      title: '6. Настройка SSH',
      body:
        'В Sileo установите OpenSSH → дефолтный пароль "alpine" — ОБЯЗАТЕЛЬНО смените (passwd root → passwd mobile). Подключитесь с компьютера: ssh root@<IP-iPhone>. В Chimera пропишите этот SSH-доступ в Настройки → iOS → Удалённый доступ.',
    },
    {
      title: '7. Привязка к Chimera',
      body:
        'В разделе «Телефоны» нажмите «Сканировать» — джейлбрейкнутый iPhone появится с пометкой "jailbroken". Нажмите ПКМ → «Открыть профиль» → «Применить антидетект-профиль». Chimera поменяет IDFV/IDFA, MAC, локаль и время по выбранному прокси.',
    },
    {
      title: '8. Безопасность',
      body:
        'Не подключайте джейлбрейкнутый телефон к публичному Wi-Fi. Используйте только Chimera-туннели. Не устанавливайте твики из непроверенных репозиториев. Подавление телеметрии Apple → твик "Choicy".',
    },
  ]
  return (
    <div className="max-h-[420px] space-y-3 overflow-auto pr-1">
      <div className="rounded-md border border-[--amber]/40 bg-[--amber]/10 p-3 text-xs text-[--txt-1]">
        ⚠️ Джейлбрейк — необратимая операция в правовом смысле и нарушает гарантию Apple.
        Используйте только на устройствах, которыми вы владеете и которые предназначены
        исключительно для автоматизации.
      </div>
      {items.map((it, i) => (
        <div key={i} className="rounded-md border border-[--line-1] bg-[--bg-2] p-3">
          <div className="text-sm font-semibold text-[--txt-1]">{it.title}</div>
          <div className="mt-1 whitespace-pre-line text-xs text-[--txt-2]">{it.body}</div>
        </div>
      ))}
      <div className="rounded-md border border-[--green]/30 bg-[--green]/5 p-3 text-xs text-[--txt-2]">
        После установки твиков перезагрузите телефон и вернитесь в Chimera —
        статус устройства автоматически сменится на <b>jailbroken</b>.
      </div>
    </div>
  )
}

function DoneStep() {
  const checklist = useMemo(
    () => [
      'Устройства подключены',
      'USB-отладка включена',
      'Аккаунты добавлены',
      'Фото загружены',
      'Всё готово к запуску',
    ],
    [],
  )
  return (
    <div className="space-y-3">
      <div className="flex justify-center py-3">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[--green]/15 text-[--green]">
          <Rocket className="h-8 w-8" />
        </div>
      </div>
      <p className="text-center text-sm text-[--txt-2]">
        Вы настроили Chimera. Можно приступать к работе!
      </p>
      <ul className="space-y-1.5">
        {checklist.map((item, i) => (
          <li
            key={i}
            className={cn(
              'flex items-center gap-2 rounded-md border border-[--line-1] bg-[--bg-2] px-3 py-2 text-sm',
            )}
          >
            <Check className="h-3.5 w-3.5 text-[--green]" />
            <span className="text-[--txt-1]">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
