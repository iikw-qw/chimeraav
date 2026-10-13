import { useCallback, useMemo, useRef, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { LogIn, Mail, Plus, Smartphone, Trash2, UserPlus, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Input, Switch } from '../components/ui'
import {
  startWarmup,
  useDevices,
  type Device,
} from '../hooks/useDevices'
import { useDatasets } from '../hooks/useDatasets'
import { scheduleBatch } from '../hooks/useTasks'
import { toast } from '../hooks/useToast'
import {
  ACCOUNTS_QUERY_KEY,
  autoLoginAccount,
  createAccount,
  deleteAccount,
  getAccountEmail,
  setAccountEmail as saveAccountEmail,
  updateAccount,
  useAccounts,
  type AccountRow,
} from '../hooks/useAccounts'

const PLATFORM_COLOR: Record<string, string> = {
  instagram: '#E1306C',
  tiktok: '#25F4EE',
  youtube: '#FF0033',
  twitter: '#1DA1F2',
  x: '#1DA1F2',
  facebook: '#1877F2',
  threads: '#9CA3AF',
  default: '#7C8DA8',
}

function platformColor(p: string): string {
  return PLATFORM_COLOR[p?.toLowerCase()] ?? PLATFORM_COLOR.default
}

interface PhoneNode {
  device: Device
  x: number
  y: number
}

interface AccountNode {
  account: AccountRow
  device: Device | null
  x: number
  y: number
}

const PHONE_W = 180
const PHONE_H = 160
const ACCOUNT_W = 220
const ACCOUNT_H = 78

const PLATFORM_OPTIONS = [
  'instagram',
  'tiktok',
  'youtube',
  'twitter',
  'facebook',
  'threads',
] as const

export function AccountsMap() {
  const { data: devices = [] } = useDevices()
  const { data: accounts = [] } = useAccounts()
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 1200, h: 800 })
  const [addOpen, setAddOpen] = useState(false)
  const [registerOpen, setRegisterOpen] = useState(false)
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null)
  const activeAccount =
    accounts.find((a) => a.id === activeAccountId) ?? null
  const activeDevice =
    activeAccount && devices.find((d) => d.id === activeAccount.device_id)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const rect = el.getBoundingClientRect()
      setSize({ w: Math.max(800, rect.width), h: Math.max(600, rect.height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const { phoneNodes, accountNodes } = useMemo(() => {
    const cols = Math.max(1, Math.min(devices.length, Math.floor(size.w / 320)))
    const rows = Math.ceil(devices.length / cols)
    const colGap = size.w / (cols + 1)
    const rowGap = size.h / (rows + 1)

    const pNodes: PhoneNode[] = devices.map((d, i) => {
      const r = Math.floor(i / cols)
      const c = i % cols
      return {
        device: d,
        x: colGap * (c + 1) - PHONE_W / 2,
        y: rowGap * (r + 1) - PHONE_H / 2,
      }
    })

    const grouped = new Map<string, AccountRow[]>()
    for (const a of accounts) {
      const key = a.device_id ?? '__unbound__'
      const arr = grouped.get(key) ?? []
      arr.push(a)
      grouped.set(key, arr)
    }

    const aNodes: AccountNode[] = []
    for (const phone of pNodes) {
      const list = grouped.get(phone.device.id) ?? []
      list.forEach((acc, i) => {
        const angle = -Math.PI / 2 + (i - (list.length - 1) / 2) * 0.55
        const r = 200
        aNodes.push({
          account: acc,
          device: phone.device,
          x: phone.x + PHONE_W / 2 + Math.cos(angle) * r - ACCOUNT_W / 2,
          y: phone.y + PHONE_H / 2 + Math.sin(angle) * r - ACCOUNT_H / 2,
        })
      })
    }
    const orphans = grouped.get('__unbound__') ?? []
    orphans.forEach((acc, i) => {
      aNodes.push({
        account: acc,
        device: null,
        x: 30,
        y: 30 + i * (ACCOUNT_H + 14),
      })
    })

    return { phoneNodes: pNodes, accountNodes: aNodes }
  }, [devices, accounts, size])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[--line-1] px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-[--txt-1]">Аккаунты</div>
          <div className="text-xs text-[--txt-3]">
            Визуальная карта привязки аккаунтов к телефонам — нити окрашены по платформе.
          </div>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-[--txt-3]">
          <span>{devices.length} телефонов</span>
          <span>·</span>
          <span>{accounts.length} аккаунтов</span>
          <Button
            size="sm"
            variant="secondary"
            leftIcon={<UserPlus className="h-3.5 w-3.5" />}
            onClick={() => setRegisterOpen(true)}
            disabled={devices.length === 0}
          >
            Создать новый аккаунт
          </Button>
          <Button
            size="sm"
            variant="primary"
            leftIcon={<Plus className="h-3.5 w-3.5" />}
            onClick={() => setAddOpen(true)}
            disabled={devices.length === 0}
          >
            Добавить аккаунт
          </Button>
        </div>
      </div>

      <AnimatePresence>
        {addOpen && (
          <AddAccountModal
            devices={devices}
            existing={accounts}
            onClose={() => setAddOpen(false)}
          />
        )}
        {registerOpen && (
          <RegisterAccountModal
            devices={devices}
            onClose={() => setRegisterOpen(false)}
          />
        )}
        {activeAccount && (
          <AccountDetailsModal
            key={activeAccount.id}
            account={activeAccount}
            device={activeDevice ?? null}
            onClose={() => setActiveAccountId(null)}
          />
        )}
      </AnimatePresence>

      <div
        ref={containerRef}
        className="relative flex-1 overflow-auto bg-[--bg-0]"
      >
        <div
          className="relative"
          style={{ width: size.w, height: Math.max(size.h, 600) }}
        >
          <svg
            className="pointer-events-none absolute inset-0"
            width={size.w}
            height={size.h}
          >
            {accountNodes.map((a, i) => {
              if (!a.device) return null
              const phone = phoneNodes.find((p) => p.device.id === a.device!.id)
              if (!phone) return null
              const sx = phone.x + PHONE_W / 2
              const sy = phone.y + PHONE_H / 2
              const ex = a.x + ACCOUNT_W / 2
              const ey = a.y + ACCOUNT_H / 2
              const mx = (sx + ex) / 2
              const my = (sy + ey) / 2 - 30
              const color = platformColor(a.account.platform)
              return (
                <path
                  key={`thread-${i}`}
                  d={`M ${sx} ${sy} Q ${mx} ${my} ${ex} ${ey}`}
                  stroke={color}
                  strokeWidth={2}
                  fill="none"
                  opacity={0.55}
                />
              )
            })}
          </svg>

          {phoneNodes.map((p) => (
            <motion.div
              key={p.device.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="absolute flex flex-col items-center justify-center rounded-2xl border-2 border-[--line-2] bg-[--bg-2] shadow-[--shadow-card]"
              style={{ left: p.x, top: p.y, width: PHONE_W, height: PHONE_H }}
            >
              <Smartphone className="h-7 w-7 text-[--blue]" />
              <div className="mt-2 truncate px-3 text-sm font-semibold text-[--txt-1]">
                {p.device.name}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-wider text-[--txt-3]">
                {p.device.platform} · {p.device.status}
              </div>
              {p.device.ip_address && (
                <div className="mt-1 font-mono text-[10px] text-[--txt-3]">
                  IP: {p.device.ip_address}
                </div>
              )}
            </motion.div>
          ))}

          {accountNodes.map((a, i) => (
            <AccountChip
              key={`acc-${a.account.id}-${i}`}
              a={a}
              onOpen={() => setActiveAccountId(a.account.id)}
            />
          ))}

          {phoneNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-[--txt-3]">
              Подключите телефоны и привяжите аккаунты — здесь появится карта связей.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function AccountChip({ a, onOpen }: { a: AccountNode; onOpen: () => void }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [loggingIn, setLoggingIn] = useState(false)
  const color = platformColor(a.account.platform)

  const remove = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (busy) return
    if (!window.confirm(`Удалить аккаунт @${a.account.username}?`)) return
    setBusy(true)
    try {
      await deleteAccount(a.account.id)
      qc.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    } finally {
      setBusy(false)
    }
  }

  const autoLogin = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (loggingIn) return
    setLoggingIn(true)
    try {
      const res = await autoLoginAccount(a.account.id)
      if (res.ok) {
        toast.info(res.message, 'Авто-вход')
      } else {
        toast.warning(res.message, 'Авто-вход')
      }
    } catch (err) {
      toast.danger((err as Error).message, 'Авто-вход')
    } finally {
      setLoggingIn(false)
    }
  }

  return (
    <motion.button
      type="button"
      onClick={onOpen}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className="group absolute flex flex-col rounded-xl border-2 bg-[--bg-1] px-3 py-2 text-left transition-shadow hover:shadow-[--shadow-card] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--blue]/40"
      style={{
        left: a.x,
        top: a.y,
        width: ACCOUNT_W,
        height: ACCOUNT_H,
        borderColor: color,
      }}
    >
      <div className="flex items-center justify-between">
        <div
          className="text-[10px] font-bold uppercase tracking-widest"
          style={{ color }}
        >
          {a.account.platform}
        </div>
        <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <span
            role="button"
            tabIndex={0}
            onClick={autoLogin}
            onKeyDown={(e) => {
              if (e.key === 'Enter') autoLogin(e as unknown as React.MouseEvent)
            }}
            aria-disabled={loggingIn}
            className="rounded p-0.5 text-[--txt-3] hover:bg-[--bg-3] hover:text-[--blue]"
            title="Авто-вход в приложение (с обходом капчи через 2Captcha)"
          >
            <LogIn className="h-3 w-3" />
          </span>
          <span
            role="button"
            tabIndex={0}
            onClick={remove}
            onKeyDown={(e) => {
              if (e.key === 'Enter') remove(e as unknown as React.MouseEvent)
            }}
            aria-disabled={busy}
            className="rounded p-0.5 text-[--txt-3] hover:bg-[--bg-3] hover:text-[--red]"
            title="Удалить аккаунт"
          >
            <Trash2 className="h-3 w-3" />
          </span>
        </div>
      </div>
      <div className="mt-0.5 truncate text-sm font-semibold text-[--txt-1]">
        {a.account.username}
      </div>
      <div className="mt-0.5 truncate font-mono text-[10px] text-[--txt-3]">
        ••••••••
      </div>
    </motion.button>
  )
}

interface AccountDetailsModalProps {
  account: AccountRow
  device: Device | null
  onClose: () => void
}

function AccountDetailsModal({ account, device, onClose }: AccountDetailsModalProps) {
  const qc = useQueryClient()
  const { data: datasets = [] } = useDatasets()

  const [tab, setTab] = useState<'profile' | 'warmup' | 'scheduler'>('profile')

  const [username, setUsername] = useState(account.username)
  const [password, setPassword] = useState('')
  const [language, setLanguage] = useState(account.auto_chatter_language)
  const [welcome, setWelcome] = useState(account.welcome_message_enabled)
  const [autoReply, setAutoReply] = useState(account.auto_reply_enabled)

  const [warmupSeconds, setWarmupSeconds] = useState(300)
  const [scrollW, setScrollW] = useState(50)
  const [profileW, setProfileW] = useState(20)
  const [likeW, setLikeW] = useState(20)
  const [followW, setFollowW] = useState(10)

  const [datasetId, setDatasetId] = useState<string>(datasets[0]?.id ?? '')
  const [days, setDays] = useState(7)
  const [postsPerDay, setPostsPerDay] = useState(1)
  const [startHour, setStartHour] = useState(10)
  const [endHour, setEndHour] = useState(20)

  const [accountEmail, setAccountEmail] = useState('')
  const [accountEmailPwd, setAccountEmailPwd] = useState('')
  const [emailLoaded, setEmailLoaded] = useState(false)

  const [busy, setBusy] = useState<'save' | 'warmup' | 'schedule' | 'autologin' | 'email' | null>(null)
  const color = platformColor(account.platform)

  const loadEmail = useCallback(async () => {
    try {
      const info = await getAccountEmail(account.id)
      setAccountEmail(info.email ?? '')
      setEmailLoaded(true)
    } catch {
      setEmailLoaded(true)
    }
  }, [account.id])

  useEffect(() => { loadEmail() }, [loadEmail])

  const saveEmail = async () => {
    if (!accountEmail.trim()) return
    setBusy('email')
    try {
      await saveAccountEmail(account.id, accountEmail.trim(), accountEmailPwd)
      toast.success('Почта привязана')
      setAccountEmailPwd('')
    } catch (err) {
      toast.danger((err as Error).message, 'Email')
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    if (!datasetId && datasets.length > 0) setDatasetId(datasets[0].id)
  }, [datasets, datasetId])

  const save = async () => {
    setBusy('save')
    try {
      await updateAccount(account.id, {
        username: username.trim(),
        password_encrypted: password ? password : undefined,
        auto_chatter_language: language,
        welcome_message_enabled: welcome,
        auto_reply_enabled: autoReply,
      })
      qc.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      toast.success('Изменения сохранены')
    } catch (err) {
      toast.danger((err as Error).message, 'Сохранение')
    } finally {
      setBusy(null)
    }
  }

  const runWarmup = async () => {
    if (!device) return
    setBusy('warmup')
    try {
      await startWarmup(device.id, {
        duration_seconds: warmupSeconds,
        account_id: account.id,
        scroll_weight: scrollW,
        profile_visit_weight: profileW,
        like_weight: likeW,
        follow_weight: followW,
      })
      toast.success(`Прогрев запущен на ${Math.round(warmupSeconds / 60)} мин`)
    } catch (err) {
      toast.danger((err as Error).message, 'Прогрев')
    } finally {
      setBusy(null)
    }
  }

  const runSchedule = async () => {
    if (!device || !datasetId) {
      toast.warning('Выберите датасет', 'Планировщик')
      return
    }
    setBusy('schedule')
    try {
      const res = await scheduleBatch({
        device_ids: [device.id],
        account_id: account.id,
        dataset_id: datasetId,
        platform: account.platform,
        days,
        posts_per_day: postsPerDay,
        start_hour: startHour,
        end_hour: endHour,
      })
      toast.success(`Запланировано постов: ${res.scheduled}`, 'Планировщик')
    } catch (err) {
      toast.danger((err as Error).message, 'Планировщик')
    } finally {
      setBusy(null)
    }
  }

  const runAutoLogin = async () => {
    setBusy('autologin')
    try {
      const res = await autoLoginAccount(account.id, password || undefined)
      if (res.ok) toast.info(res.message, 'Авто-вход')
      else toast.warning(res.message, 'Авто-вход')
    } catch (err) {
      toast.danger((err as Error).message, 'Авто-вход')
    } finally {
      setBusy(null)
    }
  }

  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/55 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.97 }}
        className="flex w-[560px] max-h-[88vh] flex-col overflow-hidden rounded-2xl border border-[--line-2] bg-[--bg-1] shadow-[--shadow-card]"
      >
        <div
          className="flex items-center justify-between border-b border-[--line-1] px-5 py-3"
          style={{ background: `linear-gradient(90deg, ${color}22, transparent)` }}
        >
          <div>
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: color }}
              />
              <span className="text-sm font-semibold text-[--txt-1]">
                @{account.username}
              </span>
              <Badge variant="info">{account.platform}</Badge>
            </div>
            <div className="mt-0.5 text-[11px] text-[--txt-3]">
              {device ? `Телефон: ${device.name}` : 'Без привязки к телефону'}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5 font-mono text-[10px]">
              {account.unique_code && (
                <span className="rounded bg-[--bg-3] px-1.5 py-0.5 text-[--txt-2]">
                  {account.unique_code}
                </span>
              )}
              {device?.unique_code && (
                <span className="rounded bg-[--bg-3] px-1.5 py-0.5 text-[--txt-3]">
                  {device.unique_code}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex border-b border-[--line-1] bg-[--bg-2] px-3">
          {(
            [
              { k: 'profile', l: 'Данные' },
              { k: 'warmup', l: 'Прогрев' },
              { k: 'scheduler', l: 'Планировщик' },
            ] as const
          ).map((t) => (
            <button
              key={t.k}
              type="button"
              onClick={() => setTab(t.k)}
              className={
                'h-9 px-4 text-xs font-medium transition-colors ' +
                (tab === t.k
                  ? 'border-b-2 border-[--blue] text-[--blue]'
                  : 'text-[--txt-2] hover:text-[--txt-1]')
              }
            >
              {t.l}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-5">
          {tab === 'profile' && (
            <div className="space-y-3">
              <label className="block text-xs text-[--txt-2]">
                Логин
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
              <label className="block text-xs text-[--txt-2]">
                Новый пароль <span className="text-[--txt-3]">(оставьте пустым, чтобы не менять)</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </label>
              <label className="block text-xs text-[--txt-2]">
                Язык авто-ответов
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
                >
                  <option value="en">English</option>
                  <option value="ru">Русский</option>
                  <option value="es">Español</option>
                  <option value="de">Deutsch</option>
                  <option value="fr">Français</option>
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center justify-between rounded-md border border-[--line-1] bg-[--bg-2] px-3 py-2 text-xs text-[--txt-2]">
                  Приветствия
                  <Switch checked={welcome} onChange={setWelcome} />
                </label>
                <label className="flex items-center justify-between rounded-md border border-[--line-1] bg-[--bg-2] px-3 py-2 text-xs text-[--txt-2]">
                  Авто-ответ
                  <Switch checked={autoReply} onChange={setAutoReply} />
                </label>
              </div>
              <div className="rounded-md border border-[--line-1] bg-[--bg-2] p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-medium text-[--txt-2]">
                  <Mail className="h-3.5 w-3.5" />
                  Почта аккаунта
                </div>
                {emailLoaded && (
                  <>
                    <Input
                      value={accountEmail}
                      onChange={(e) => setAccountEmail(e.target.value)}
                      placeholder="user@gmail.com"
                    />
                    <Input
                      type="password"
                      value={accountEmailPwd}
                      onChange={(e) => setAccountEmailPwd(e.target.value)}
                      placeholder="Пароль от почты"
                    />
                    <div className="text-[10px] text-[--txt-3]">
                      Платформа: {account.platform} — для Gmail включите IMAP и App Password
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={saveEmail}
                      disabled={busy === 'email' || !accountEmail.trim()}
                    >
                      {busy === 'email' ? 'Сохраняем…' : 'Сохранить почту'}
                    </Button>
                  </>
                )}
              </div>

              <div className="flex items-center justify-between gap-2 pt-1">
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<LogIn className="h-3.5 w-3.5" />}
                  onClick={runAutoLogin}
                  disabled={busy === 'autologin'}
                >
                  {busy === 'autologin' ? 'Запускаю…' : 'Авто-вход (2Captcha)'}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={save}
                  disabled={busy === 'save'}
                >
                  {busy === 'save' ? 'Сохраняем…' : 'Сохранить'}
                </Button>
              </div>
            </div>
          )}

          {tab === 'warmup' && (
            <div className="space-y-3">
              <p className="text-xs text-[--txt-3]">
                Запустите автономный прогрев аккаунта: скролл, заходы в профили, лайки и подписки в указанной пропорции.
              </p>
              <label className="block text-xs text-[--txt-2]">
                Длительность (сек)
                <Input
                  type="number"
                  min={60}
                  max={3600}
                  step={30}
                  value={warmupSeconds}
                  onChange={(e) =>
                    setWarmupSeconds(Math.max(60, Number(e.target.value) || 60))
                  }
                />
              </label>
              {(
                [
                  ['Скролл', scrollW, setScrollW],
                  ['Профили', profileW, setProfileW],
                  ['Лайки', likeW, setLikeW],
                  ['Подписки', followW, setFollowW],
                ] as Array<[string, number, (v: number) => void]>
              ).map(([label, value, setter]) => (
                <label key={label} className="block text-xs text-[--txt-2]">
                  {label} (вес {value})
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={value}
                    onChange={(e) => setter(Number(e.target.value))}
                    className="mt-1 w-full accent-[--blue]"
                  />
                </label>
              ))}
              <Button
                variant="primary"
                onClick={runWarmup}
                disabled={!device || busy === 'warmup'}
              >
                {busy === 'warmup' ? 'Запускаем…' : 'Запустить прогрев'}
              </Button>
            </div>
          )}

          {tab === 'scheduler' && (
            <div className="space-y-3">
              <p className="text-xs text-[--txt-3]">
                Спланируйте автопостинг для этого аккаунта. Посты распределятся случайно
                в окне [start_hour, end_hour] на N дней.
              </p>
              <label className="block text-xs text-[--txt-2]">
                Датасет
                <select
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
                >
                  {datasets.length === 0 && (
                    <option value="">— нет датасетов —</option>
                  )}
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} · {d.photo_count} фото
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-[--txt-2]">
                  Дней
                  <Input
                    type="number"
                    min={1}
                    max={60}
                    value={days}
                    onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
                <label className="block text-xs text-[--txt-2]">
                  Постов в день
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={postsPerDay}
                    onChange={(e) =>
                      setPostsPerDay(Math.max(1, Number(e.target.value) || 1))
                    }
                  />
                </label>
                <label className="block text-xs text-[--txt-2]">
                  Старт (час)
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={startHour}
                    onChange={(e) =>
                      setStartHour(Math.max(0, Math.min(23, Number(e.target.value) || 0)))
                    }
                  />
                </label>
                <label className="block text-xs text-[--txt-2]">
                  Финиш (час)
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={endHour}
                    onChange={(e) =>
                      setEndHour(Math.max(0, Math.min(23, Number(e.target.value) || 0)))
                    }
                  />
                </label>
              </div>
              <Button
                variant="primary"
                onClick={runSchedule}
                disabled={!device || !datasetId || busy === 'schedule'}
              >
                {busy === 'schedule' ? 'Планируем…' : 'Запланировать'}
              </Button>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  )
}

const REGISTER_PLATFORMS = [
  'instagram', 'tiktok', 'facebook', 'twitter', 'linkedin', 'vk', 'reddit',
] as const

const REGISTER_STAGES: Record<string, string> = {
  starting: 'Открываем приложение...',
  navigating: 'Переходим к регистрации...',
  input: 'Вводим данные...',
  verification: 'Проходим верификацию...',
  finalizing: 'Завершаем регистрацию...',
  done: 'Аккаунт создан!',
  error: 'Ошибка регистрации',
}

interface RegisterAccountModalProps {
  devices: Device[]
  onClose: () => void
}

function RegisterAccountModal({ devices, onClose }: RegisterAccountModalProps) {
  const qc = useQueryClient()
  const [deviceId, setDeviceId] = useState<string>(devices[0]?.id ?? '')
  const [platform, setPlatform] = useState<string>(REGISTER_PLATFORMS[0])
  const [email, setEmail] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (busy) return
    setErr(null)
    setStage(null)
    setLogs([])

    if (!deviceId) { setErr('Выберите телефон'); return }
    if (!email.trim()) { setErr('Введите email'); return }
    if (!emailPassword.trim()) { setErr('Введите пароль от email'); return }

    setBusy(true)
    setStage('starting')
    setLogs(['Запуск процесса регистрации...'])

    try {
      const { api } = await import('../api/client')
      const res = await api.post('/api/registration/register-new', {
        email: email.trim(),
        email_password: emailPassword,
        platform,
        device_id: deviceId,
      })

      if (res.data?.ok) {
        setStage('done')
        setLogs(prev => [...prev, 'Регистрация запущена в фоне'])
        qc.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      } else {
        setStage('error')
        setErr(res.data?.error || 'Ошибка при запуске регистрации')
      }
    } catch (e2: unknown) {
      setStage('error')
      const message = e2 instanceof Error ? e2.message : 'Не удалось запустить регистрацию'
      setErr(message)
      setLogs(prev => [...prev, `Ошибка: ${message}`])
    } finally {
      setBusy(false)
    }
  }

  const color = platformColor(platform)

  const stageKeys = Object.keys(REGISTER_STAGES)
  const currentStageIdx = stage ? stageKeys.indexOf(stage) : -1
  const progressPct = stage === 'done' ? 100
    : stage === 'error' ? 0
    : Math.max(0, Math.min(100, ((currentStageIdx + 1) / (stageKeys.length - 1)) * 100))

  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/55 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.97 }}
        className="w-[480px] overflow-hidden rounded-2xl border border-[--line-2] bg-[--bg-1] shadow-[--shadow-card]"
      >
        <div
          className="flex items-center justify-between border-b border-[--line-1] px-5 py-3"
          style={{ background: `linear-gradient(90deg, ${color}22, transparent)` }}
        >
          <div>
            <div className="text-sm font-semibold text-[--txt-1]">
              Создать новый аккаунт
            </div>
            <div className="text-[11px] text-[--txt-3]">
              Автоматическая регистрация на платформе
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 p-5">
          <label className="block text-xs text-[--txt-2]">
            Email
            <Input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="example@gmail.com"
              autoFocus
            />
          </label>

          <label className="block text-xs text-[--txt-2]">
            Пароль от email
            <Input
              type="password"
              value={emailPassword}
              onChange={(e) => setEmailPassword(e.target.value)}
              placeholder="••••••••"
            />
          </label>

          <label className="block text-xs text-[--txt-2]">
            Платформа
            <div className="mt-1 grid grid-cols-4 gap-1.5">
              {REGISTER_PLATFORMS.map((p) => {
                const c = platformColor(p)
                const active = p === platform
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPlatform(p)}
                    className="rounded-md border-2 px-2 py-1.5 text-xs font-semibold capitalize transition-all"
                    style={{
                      borderColor: active ? c : 'var(--line-1)',
                      color: active ? c : 'var(--txt-2)',
                      background: active ? `${c}14` : 'transparent',
                    }}
                  >
                    {p}
                  </button>
                )
              })}
            </div>
          </label>

          <label className="block text-xs text-[--txt-2]">
            Телефон (на каком устройстве регистрировать)
            <select
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
            >
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} · {d.platform}
                </option>
              ))}
            </select>
          </label>

          {stage && (
            <div className="space-y-2 rounded-md border border-[--line-1] bg-[--bg-2] p-3">
              <div className="flex items-center gap-2 text-xs font-medium text-[--txt-1]">
                {stage === 'done' ? '✅' : stage === 'error' ? '❌' : '⏳'}
                {REGISTER_STAGES[stage] || stage}
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[--bg-3]">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: stage === 'error' ? 'var(--red)' : color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${progressPct}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
              {logs.length > 0 && (
                <div className="max-h-24 overflow-auto font-mono text-[10px] text-[--txt-3]">
                  {logs.map((l, i) => (
                    <div key={i}>{l}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {err && (
            <div className="rounded-md border border-[--red]/40 bg-[--red]/10 px-3 py-2 text-xs text-[--red]">
              {err}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[--line-1] bg-[--bg-2] px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? 'Регистрируем...' : 'Начать регистрацию'}
          </Button>
        </div>
      </motion.form>
    </motion.div>,
    document.body,
  )
}

interface AddAccountModalProps {
  devices: Device[]
  existing: AccountRow[]
  onClose: () => void
}

function AddAccountModal({ devices, existing, onClose }: AddAccountModalProps) {
  const qc = useQueryClient()
  const [deviceId, setDeviceId] = useState<string>(devices[0]?.id ?? '')
  const [platform, setPlatform] = useState<string>(PLATFORM_OPTIONS[0])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [language, setLanguage] = useState('en')
  const [welcome, setWelcome] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const duplicate = useMemo(
    () =>
      existing.some(
        (a) =>
          a.platform === platform &&
          a.username.trim().toLowerCase() === username.trim().toLowerCase(),
      ),
    [existing, platform, username],
  )

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (busy) return
    setErr(null)
    if (!deviceId) {
      setErr('Выберите телефон')
      return
    }
    if (!username.trim()) {
      setErr('Введите логин')
      return
    }
    if (duplicate) {
      setErr('Такой аккаунт уже добавлен')
      return
    }
    setBusy(true)
    try {
      await createAccount({
        device_id: deviceId,
        platform,
        username: username.trim(),
        password_encrypted: password || null,
        auto_chatter_language: language,
        welcome_message_enabled: welcome,
      })
      qc.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
      onClose()
    } catch (e2: unknown) {
      const message = e2 instanceof Error ? e2.message : 'Не удалось сохранить аккаунт'
      setErr(message)
    } finally {
      setBusy(false)
    }
  }

  const color = platformColor(platform)

  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/55 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.97 }}
        className="w-[440px] overflow-hidden rounded-2xl border border-[--line-2] bg-[--bg-1] shadow-[--shadow-card]"
      >
        <div
          className="flex items-center justify-between border-b border-[--line-1] px-5 py-3"
          style={{ background: `linear-gradient(90deg, ${color}22, transparent)` }}
        >
          <div>
            <div className="text-sm font-semibold text-[--txt-1]">
              Добавить аккаунт
            </div>
            <div className="text-[11px] text-[--txt-3]">
              Привязка к телефону и платформе
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 p-5">
          <label className="block text-xs text-[--txt-2]">
            Телефон
            <select
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
            >
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} · {d.platform}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-[--txt-2]">
            Платформа
            <div className="mt-1 grid grid-cols-3 gap-1.5">
              {PLATFORM_OPTIONS.map((p) => {
                const c = platformColor(p)
                const active = p === platform
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPlatform(p)}
                    className="rounded-md border-2 px-2 py-1.5 text-xs font-semibold capitalize transition-all"
                    style={{
                      borderColor: active ? c : 'var(--line-1)',
                      color: active ? c : 'var(--txt-2)',
                      background: active ? `${c}14` : 'transparent',
                    }}
                  >
                    {p}
                  </button>
                )
              })}
            </div>
          </label>

          <label className="block text-xs text-[--txt-2]">
            Логин
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="@username"
              autoFocus
            />
          </label>

          <label className="block text-xs text-[--txt-2]">
            Пароль <span className="text-[--txt-3]">(опционально, шифруется)</span>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs text-[--txt-2]">
              Язык авто-ответов
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
              >
                <option value="en">English</option>
                <option value="ru">Русский</option>
                <option value="es">Español</option>
                <option value="de">Deutsch</option>
                <option value="fr">Français</option>
              </select>
            </label>
            <label className="flex cursor-pointer items-center gap-2 self-end pb-1 text-xs text-[--txt-2]">
              <input
                type="checkbox"
                checked={welcome}
                onChange={(e) => setWelcome(e.target.checked)}
              />
              Включить приветствия
            </label>
          </div>

          {err && (
            <div className="rounded-md border border-[--red]/40 bg-[--red]/10 px-3 py-2 text-xs text-[--red]">
              {err}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[--line-1] bg-[--bg-2] px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? 'Сохраняем…' : 'Добавить'}
          </Button>
        </div>
      </motion.form>
    </motion.div>,
    document.body,
  )
}
