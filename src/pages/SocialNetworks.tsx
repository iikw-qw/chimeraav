import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart3,
  Bot,
  Facebook,
  Instagram,
  MessageCircle,
  Music2,
  Send,
  Twitter,
  Youtube,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Switch } from '../components/ui'
import { api } from '../api/client'
import { cn } from '../lib/cn'
import {
  ACCOUNTS_QUERY_KEY,
  useAccounts,
  type AccountRow,
} from '../hooks/useAccounts'
import { toast } from '../hooks/useToast'

type PlatformKey =
  | 'instagram'
  | 'tiktok'
  | 'telegram'
  | 'twitter'
  | 'facebook'
  | 'youtube'
  | 'reddit'
  | 'threads'

const PLATFORMS: { key: PlatformKey; label: string; icon: typeof Instagram }[] = [
  { key: 'instagram', label: 'Instagram', icon: Instagram },
  { key: 'tiktok', label: 'TikTok', icon: Music2 },
  { key: 'telegram', label: 'Telegram', icon: Send },
  { key: 'twitter', label: 'Twitter/X', icon: Twitter },
  { key: 'facebook', label: 'Facebook', icon: Facebook },
  { key: 'youtube', label: 'YouTube', icon: Youtube },
  { key: 'reddit', label: 'Reddit', icon: MessageCircle },
  { key: 'threads', label: 'Threads', icon: MessageCircle },
]

const POSTING_STYLES = ['friendly', 'professional', 'playful', 'intriguing'] as const

export function SocialNetworks() {
  const [platform, setPlatform] = useState<PlatformKey>('instagram')
  const { data: accounts = [] } = useAccounts()
  const qc = useQueryClient()

  const accountsForPlatform = useMemo(
    () => accounts.filter((a) => a.platform === platform),
    [accounts, platform],
  )

  const patchAccount = async (id: string, patch: Record<string, unknown>) => {
    try {
      await api.put(`/api/accounts/${id}`, patch)
      qc.invalidateQueries({ queryKey: ACCOUNTS_QUERY_KEY })
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  return (
    <motion.div
      className="flex h-full flex-col bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex h-12 shrink-0 items-center gap-1 overflow-x-auto border-b border-[--line-1] bg-[--bg-1] px-4">
        {PLATFORMS.map(({ key, label, icon: Icon }) => {
          const active = platform === key
          return (
            <button
              key={key}
              type="button"
              onClick={() => setPlatform(key)}
              className={cn(
                'flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-sm transition-colors',
                active
                  ? 'bg-[--blue]/10 text-[--blue]'
                  : 'text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]',
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          )
        })}
      </div>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-6 xl:grid-cols-2">
        <AutoPostingSection
          platform={platform}
          accounts={accountsForPlatform}
          onPatch={patchAccount}
        />
        <AutoReplySection
          platform={platform}
          accounts={accountsForPlatform}
          onPatch={patchAccount}
        />
      </div>
    </motion.div>
  )
}

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-[--line-1] bg-[--bg-2] p-4">
      <header className="flex items-center gap-2 text-sm font-semibold text-[--txt-1]">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[--blue]/10 text-[--blue]">
          {icon}
        </div>
        {title}
      </header>
      <div className="flex flex-1 flex-col gap-3">{children}</div>
    </section>
  )
}

function AutoPostingSection({
  platform,
  accounts,
  onPatch,
}: {
  platform: PlatformKey
  accounts: AccountRow[]
  onPatch: (id: string, patch: Record<string, unknown>) => void
}) {
  return (
    <SectionCard title={`Автопостинг — ${platform}`} icon={<BarChart3 className="h-4 w-4" />}>
      {accounts.length === 0 ? (
        <div className="py-6 text-center text-sm text-[--txt-3]">Нет аккаунтов</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[--line-1]">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
              <tr>
                <th className="px-3 py-2 text-left">Аккаунт</th>
                <th className="px-3 py-2 text-left">Статус</th>
                <th className="px-3 py-2 text-left">Активные часы</th>
                <th className="px-3 py-2 text-left">Стиль</th>
                <th className="px-3 py-2 text-left">Автопостинг</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => {
                const row = a as AccountRow & {
                  posting_style?: string
                  welcome_message_enabled?: boolean
                  activity_hours_min?: number
                  activity_hours_max?: number
                }
                return (
                  <tr key={a.id} className="border-t border-[--line-1]">
                    <td className="px-3 py-2 text-[--txt-1]">@{a.username}</td>
                    <td className="px-3 py-2">
                      <Badge variant={a.status === 'active' ? 'success' : 'neutral'}>
                        {a.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-[--txt-2]">
                      {row.activity_hours_min ?? 1}–{row.activity_hours_max ?? 6} ч/день
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={row.posting_style ?? 'friendly'}
                        onChange={(e) => onPatch(a.id, { posting_style: e.target.value })}
                        className="h-7 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1]"
                      >
                        {POSTING_STYLES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <Switch
                        checked={Boolean(row.welcome_message_enabled)}
                        onChange={(v) => onPatch(a.id, { welcome_message_enabled: v })}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-xl border border-dashed border-[--line-2] bg-[--bg-3] p-4">
        <div className="mb-2 text-xs uppercase tracking-wider text-[--txt-3]">
          График публикаций (7 дней)
        </div>
        <SimpleBars data={syntheticSchedule(platform)} />
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-[--txt-2]">Стиль подписи по умолчанию</span>
        <select className="h-8 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1]">
          {POSTING_STYLES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
    </SectionCard>
  )
}

function AutoReplySection({
  platform,
  accounts,
  onPatch,
}: {
  platform: PlatformKey
  accounts: AccountRow[]
  onPatch: (id: string, patch: Record<string, unknown>) => void
}) {
  return (
    <SectionCard title={`Автоответ — ${platform}`} icon={<Bot className="h-4 w-4" />}>
      <div className="rounded-xl border border-[--line-1] bg-[--bg-3] p-3 text-xs text-[--txt-2]">
        <div className="mb-2 text-[10px] uppercase tracking-wider text-[--txt-3]">
          Настройки анализа
        </div>
        <ul className="list-disc pl-4 space-y-1">
          <li>Пол: только male (gender-guesser)</li>
          <li>Качество: quality (отсев bot/inactive/suspicious)</li>
          <li>
            Язык ответа:{' '}
            <span className="font-semibold text-[--blue]">EN</span> (зафиксировано)
          </li>
        </ul>
      </div>

      {accounts.length === 0 ? (
        <div className="py-6 text-center text-sm text-[--txt-3]">Нет аккаунтов</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[--line-1]">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
              <tr>
                <th className="px-3 py-2 text-left">Аккаунт</th>
                <th className="px-3 py-2 text-left">Автоответ</th>
                <th className="px-3 py-2 text-left">Язык</th>
                <th className="px-3 py-2 text-left">Уведомления</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => {
                const row = a as AccountRow & { notify_new_messages?: boolean }
                return (
                  <tr key={a.id} className="border-t border-[--line-1]">
                    <td className="px-3 py-2 text-[--txt-1]">@{a.username}</td>
                    <td className="px-3 py-2">
                      <Switch
                        checked={a.auto_reply_enabled}
                        onChange={(v) => onPatch(a.id, { auto_reply_enabled: v })}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="info">EN (fixed)</Badge>
                    </td>
                    <td className="px-3 py-2">
                      <Switch
                        checked={Boolean(row.notify_new_messages)}
                        onChange={(v) => onPatch(a.id, { notify_new_messages: v })}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center gap-2 pt-2">
        <Button variant="secondary" size="sm">
          Тест автоответа
        </Button>
        <Button variant="ghost" size="sm">
          Очистить очередь
        </Button>
      </div>
    </SectionCard>
  )
}

function syntheticSchedule(seed: string): number[] {
  let x = 0
  for (let i = 0; i < seed.length; i++) x = (x * 31 + seed.charCodeAt(i)) >>> 0
  return Array.from({ length: 7 }, () => {
    x = (1103515245 * x + 12345) >>> 0
    return (x % 9) + 1
  })
}

function SimpleBars({ data }: { data: number[] }) {
  const max = Math.max(1, ...data)
  const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  return (
    <div className="flex h-24 items-end gap-2">
      {data.map((v, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div
            className="w-full rounded-md bg-[--blue]/70 transition-all"
            style={{ height: `${(v / max) * 100}%` }}
          />
          <span className="text-[10px] text-[--txt-3]">{days[i]}</span>
        </div>
      ))}
    </div>
  )
}
