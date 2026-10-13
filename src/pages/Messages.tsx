import { useCallback, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, Send, Shuffle, Users } from 'lucide-react'
import { Badge, Button, Input, Switch } from '../components/ui'
import { WelcomeTab } from '../components/bottom-panel/WelcomeTab'
import { cn } from '../lib/cn'
import { useAccounts } from '../hooks/useAccounts'
import { useComments } from '../hooks/useComments'
import {
  useIncomingMessages,
  useUnreadCount,
  type IncomingMessage,
} from '../hooks/useIncomingMessages'
import { useReadyForWelcome, useWelcomeProgress } from '../hooks/useWelcome'
import {
  sendPoolBulkWelcome,
  useUsersPool,
  type PoolUser,
} from '../hooks/useUsersPool'

type TabKey = 'pool' | 'ready' | 'sent' | 'incoming' | 'dialogs' | 'platforms' | 'dm_scanner'

export function Messages() {
  const [tab, setTab] = useState<TabKey>('pool')
  const { data: ready = [] } = useReadyForWelcome()
  const { data: unread = 0 } = useUnreadCount()
  const { data: pool = [] } = useUsersPool()
  const { data: accountsForTabs = [] } = useAccounts()

  const poolPending = useMemo(() => pool.filter((u) => !u.welcome_sent).length, [pool])
  const platformCount = useMemo(
    () => new Set(accountsForTabs.map((a) => a.platform)).size,
    [accountsForTabs],
  )

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'pool', label: 'Мужские контакты', count: poolPending },
    { key: 'ready', label: 'Готовы к приветствию', count: ready.length },
    { key: 'sent', label: 'Отправлено' },
    { key: 'incoming', label: 'Входящие', count: unread },
    { key: 'dialogs', label: 'Диалоги' },
    { key: 'platforms', label: 'Платформы', count: platformCount },
    { key: 'dm_scanner', label: 'DM Scanner' },
  ]

  return (
    <motion.div
      className="flex h-full flex-col bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex h-12 items-center gap-1 border-b border-[--line-1] bg-[--bg-1] px-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              'relative flex h-10 items-center gap-2 rounded-md px-3 text-sm transition-colors',
              tab === t.key
                ? 'bg-[--blue]/10 text-[--blue]'
                : 'text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]',
            )}
          >
            {t.label}
            {typeof t.count === 'number' && t.count > 0 && (
              <Badge variant={tab === t.key ? 'info' : 'neutral'}>{t.count}</Badge>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === 'pool' && <UsersPoolTab />}
        {tab === 'ready' && (
          <div className="h-full p-4">
            <WelcomeTab />
          </div>
        )}
        {tab === 'sent' && <SentTab />}
        {tab === 'incoming' && <IncomingTab />}
        {tab === 'dialogs' && <DialogsTab />}
        {tab === 'platforms' && <PlatformsTab />}
        {tab === 'dm_scanner' && <DMScannerTab />}
      </div>
    </motion.div>
  )
}

const PLATFORM_COLOR: Record<string, string> = {
  instagram: '#E1306C',
  tiktok: '#25F4EE',
  youtube: '#FF0033',
  twitter: '#1DA1F2',
  x: '#1DA1F2',
  facebook: '#1877F2',
  threads: '#9CA3AF',
}

function platformColor(p: string): string {
  return PLATFORM_COLOR[p?.toLowerCase()] ?? '#7C8DA8'
}

function PlatformsTab() {
  const { data: accounts = [] } = useAccounts()
  const { data: comments = [] } = useComments()
  const { data: incoming = [] } = useIncomingMessages()

  const platforms = useMemo(() => {
    const set = new Set<string>()
    for (const a of accounts) set.add(a.platform)
    return Array.from(set).sort()
  }, [accounts])

  const [selected, setSelected] = useState<string | null>(null)
  const active = selected ?? platforms[0] ?? null

  const platformStats = useMemo(() => {
    const map = new Map<string, { accounts: number; comments: number; dms: number }>()
    for (const p of platforms) map.set(p, { accounts: 0, comments: 0, dms: 0 })
    for (const a of accounts) {
      const s = map.get(a.platform)
      if (s) s.accounts++
    }
    for (const c of comments) {
      const s = map.get(c.platform)
      if (s) s.comments++
    }
    for (const m of incoming) {
      const s = map.get(m.platform)
      if (s) s.dms++
    }
    return map
  }, [platforms, accounts, comments, incoming])

  const perAccount = useMemo(() => {
    if (!active) return []
    const platformAccounts = accounts.filter((a) => a.platform === active)
    return platformAccounts.map((a) => {
      const accountComments = comments.filter(
        (c) => c.account_id === a.id && c.platform === active,
      )
      const accountDms = incoming.filter(
        (m) => m.account_id === a.id && m.platform === active,
      )
      const lastComment = accountComments[0]?.created_at
      const lastDm = accountDms[0]?.received_at
      const lastActivity =
        lastComment && lastDm
          ? new Date(lastComment) > new Date(lastDm)
            ? lastComment
            : lastDm
          : (lastComment ?? lastDm ?? null)
      const replied = accountComments.filter((c) => c.reply_status === 'sent').length
      return {
        account: a,
        comments: accountComments.length,
        replied,
        dms: accountDms.length,
        lastActivity,
      }
    })
  }, [active, accounts, comments, incoming])

  if (platforms.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-[--txt-3]">
        Нет подключённых аккаунтов. Добавьте аккаунт во вкладке «Аккаунты», чтобы
        увидеть метрики по платформе.
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <aside className="w-[220px] shrink-0 overflow-auto border-r border-[--line-1] bg-[--bg-1]">
        <div className="px-4 pb-2 pt-3 text-[10px] font-semibold uppercase tracking-widest text-[--txt-3]">
          Платформы
        </div>
        {platforms.map((p) => {
          const stat = platformStats.get(p)!
          const c = platformColor(p)
          const isActive = active === p
          return (
            <button
              key={p}
              type="button"
              onClick={() => setSelected(p)}
              className={cn(
                'flex w-full items-center gap-3 border-l-2 px-4 py-3 text-left transition-colors',
                isActive ? 'bg-[--blue]/10' : 'border-transparent hover:bg-[--bg-3]',
              )}
              style={isActive ? { borderColor: c } : undefined}
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: c }}
              />
              <span className="flex-1">
                <span className="block text-sm font-semibold capitalize text-[--txt-1]">
                  {p}
                </span>
                <span className="block text-[10px] text-[--txt-3]">
                  {stat.accounts} акк · {stat.comments} комм · {stat.dms} лс
                </span>
              </span>
            </button>
          )
        })}
      </aside>

      <section className="flex-1 overflow-auto">
        {active ? (
          <div className="p-5">
            <div className="mb-4 flex items-center gap-3">
              <span
                className="h-3 w-3 rounded-full"
                style={{ background: platformColor(active) }}
              />
              <h2 className="text-base font-semibold capitalize text-[--txt-1]">
                {active}
              </h2>
              <span className="text-xs text-[--txt-3]">
                метрики по аккаунтам — комментарии и личные сообщения
              </span>
            </div>

            {perAccount.length === 0 ? (
              <div className="p-8 text-center text-sm text-[--txt-3]">
                Нет аккаунтов с активностью на этой платформе.
              </div>
            ) : (
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
                  <tr>
                    <th className="px-3 py-2 text-left">Аккаунт</th>
                    <th className="px-3 py-2 text-right">Комментарии</th>
                    <th className="px-3 py-2 text-right">Отвечено</th>
                    <th className="px-3 py-2 text-right">Личные</th>
                    <th className="px-3 py-2 text-left">Последняя активность</th>
                  </tr>
                </thead>
                <tbody>
                  {perAccount.map((row) => (
                    <tr
                      key={row.account.id}
                      className="border-t border-[--line-1] hover:bg-[--bg-3]/40"
                    >
                      <td className="px-3 py-2 font-medium text-[--txt-1]">
                        @{row.account.username}
                      </td>
                      <td className="px-3 py-2 text-right">{row.comments}</td>
                      <td className="px-3 py-2 text-right text-[--txt-2]">
                        {row.replied}
                      </td>
                      <td className="px-3 py-2 text-right">{row.dms}</td>
                      <td className="px-3 py-2 text-[--txt-2]">
                        {row.lastActivity
                          ? new Date(row.lastActivity).toLocaleString()
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </section>
    </div>
  )
}

function SentTab() {
  const { data: comments = [] } = useComments({ welcome_sent: true })
  const { data: incoming = [] } = useIncomingMessages()

  const replyBySender = useMemo(() => {
    const map = new Map<string, IncomingMessage>()
    for (const m of incoming) {
      const key = (m.sender_username ?? m.sender_user_id ?? '').toLowerCase()
      if (key) map.set(key, m)
    }
    return map
  }, [incoming])

  return (
    <div className="h-full overflow-auto p-4">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
          <tr>
            <th className="px-3 py-2 text-left">Username</th>
            <th className="px-3 py-2 text-left">Платформа</th>
            <th className="px-3 py-2 text-left">Дата</th>
            <th className="px-3 py-2 text-left">Статус</th>
          </tr>
        </thead>
        <tbody>
          {comments.length === 0 ? (
            <tr>
              <td colSpan={4} className="px-3 py-10 text-center text-[--txt-3]">
                Пока не отправлено
              </td>
            </tr>
          ) : (
            comments.map((c) => {
              const key = (c.commenter_username ?? '').toLowerCase()
              const reply = replyBySender.get(key)
              return (
                <tr key={c.id} className="border-t border-[--line-1] hover:bg-[--bg-3]/40">
                  <td className="px-3 py-2">@{c.commenter_username ?? '—'}</td>
                  <td className="px-3 py-2 text-[--txt-2]">{c.platform}</td>
                  <td className="px-3 py-2 text-[--txt-2]">
                    {new Date(c.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    {reply ? (
                      <Badge variant="success">Ответил 💬</Badge>
                    ) : (
                      <Badge variant="neutral">Ожидание</Badge>
                    )}
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}

function IncomingTab() {
  const { data = [] } = useIncomingMessages()
  if (data.length === 0)
    return <div className="p-8 text-center text-sm text-[--txt-3]">Нет новых сообщений</div>
  return (
    <div className="h-full overflow-auto p-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.map((m) => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-2 rounded-xl border border-[--line-1] bg-[--bg-2] p-3 shadow-[var(--shadow-card)]"
          >
            <div className="flex items-center justify-between text-xs text-[--txt-2]">
              <span>Аккаунт {m.account_id.slice(0, 8)}…</span>
              <span>{new Date(m.received_at).toLocaleTimeString()}</span>
            </div>
            <div className="text-sm font-medium text-[--txt-1]">
              @{m.sender_username ?? m.sender_user_id ?? '—'}
            </div>
            <div className="text-sm text-[--txt-1]">{m.message_text ?? '—'}</div>
            <div className="flex items-center justify-between">
              <Badge variant="info">{m.platform}</Badge>
              <Button variant="primary" size="sm" leftIcon={<Send className="h-3 w-3" />}>
                Ответить
              </Button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

type SourceFilter = 'all' | 'comment' | 'dm'
type SelectionMode = 'selected' | 'first' | 'random' | 'newest'

function UsersPoolTab() {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [accountId, setAccountId] = useState<string>('')
  const { data: accounts = [] } = useAccounts()

  const { data: pool = [], isLoading } = useUsersPool({
    source: sourceFilter === 'all' ? undefined : sourceFilter,
    account_id: accountId || undefined,
    limit: 500,
  })

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [mode, setMode] = useState<SelectionMode>('selected')
  const [count, setCount] = useState<number>(20)
  const [messageText, setMessageText] = useState<string>('Hi! Nice to meet you!')
  const [delay, setDelay] = useState<number>(30)
  const [busy, setBusy] = useState(false)
  const progress = useWelcomeProgress()

  const pending = useMemo(() => pool.filter((u) => !u.welcome_sent), [pool])

  const toggle = (k: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })
  }
  const toggleAll = () => {
    if (selected.size === pending.length && pending.length > 0) setSelected(new Set())
    else setSelected(new Set(pending.map((u) => u.key)))
  }

  const previewKeys = useMemo(() => {
    if (mode === 'selected') return Array.from(selected)
    const pool = [...pending]
    if (mode === 'random') pool.sort(() => Math.random() - 0.5)
    else if (mode === 'newest')
      pool.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
    return pool.slice(0, count).map((u) => u.key)
  }, [mode, selected, pending, count])

  const sendNow = async () => {
    if (busy) return
    setBusy(true)
    try {
      if (mode === 'selected') {
        if (previewKeys.length === 0) return
        await sendPoolBulkWelcome({
          keys: previewKeys,
          account_id: accountId || undefined,
          message_text: messageText,
          delay_seconds: delay,
        })
      } else {
        await sendPoolBulkWelcome({
          count,
          selection: mode,
          account_id: accountId || undefined,
          message_text: messageText,
          delay_seconds: delay,
        })
      }
      setSelected(new Set())
    } finally {
      setBusy(false)
    }
  }

  const canSend =
    !busy &&
    (mode === 'selected' ? previewKeys.length > 0 : count > 0 && pending.length > 0)

  return (
    <div className="flex h-full">
      <aside className="flex w-[320px] shrink-0 flex-col gap-3 overflow-auto border-r border-[--line-1] bg-[--bg-1] p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-[--txt-1]">
          <Users className="h-4 w-4" />
          Рассылка приветствий
        </div>
        <div className="rounded-md border border-[--line-1] bg-[--bg-2] px-2 py-1.5 text-[11px] text-[--txt-3]">
          В списке только мужчины: комментаторы и авторы личных сообщений,
          чей пол определён как мужской по имени и анкете.
        </div>

        <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
          <span>Источник</span>
          <div className="flex gap-1">
            {(
              [
                { k: 'all', l: 'Все' },
                { k: 'comment', l: 'Комментарии' },
                { k: 'dm', l: 'Личные' },
              ] as { k: SourceFilter; l: string }[]
            ).map((opt) => (
              <button
                key={opt.k}
                type="button"
                onClick={() => setSourceFilter(opt.k)}
                className={cn(
                  'flex-1 rounded-md border px-2 py-1.5 text-xs transition-colors',
                  sourceFilter === opt.k
                    ? 'border-[--blue] bg-[--blue]/10 text-[--blue]'
                    : 'border-[--line-1] text-[--txt-2] hover:bg-[--bg-3]',
                )}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
          <span>Аккаунт</span>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="h-9 rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            <option value="">Все аккаунты</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                @{a.username ?? a.id.slice(0, 8)} · {a.platform}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
          <span>Кого отправить</span>
          <div className="grid grid-cols-2 gap-1">
            {(
              [
                { k: 'selected', l: 'Отмеченных' },
                { k: 'first', l: 'По порядку' },
                { k: 'random', l: 'Наугад' },
                { k: 'newest', l: 'Самых свежих' },
              ] as { k: SelectionMode; l: string }[]
            ).map((opt) => (
              <button
                key={opt.k}
                type="button"
                onClick={() => setMode(opt.k)}
                className={cn(
                  'rounded-md border px-2 py-1.5 text-xs transition-colors',
                  mode === opt.k
                    ? 'border-[--blue] bg-[--blue]/10 text-[--blue]'
                    : 'border-[--line-1] text-[--txt-2] hover:bg-[--bg-3]',
                )}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        {mode !== 'selected' && (
          <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
            <span>Сколько отправить</span>
            <Input
              type="number"
              min={1}
              max={500}
              value={count}
              onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
            />
          </div>
        )}

        <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
          <span>Текст приветствия</span>
          <textarea
            rows={3}
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            className="rounded-md border border-[--line-1] bg-[--bg-3] p-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          />
        </div>

        <div className="flex flex-col gap-1 text-xs text-[--txt-2]">
          <span>Задержка между отправками (сек)</span>
          <Input
            type="number"
            min={0}
            max={600}
            step={5}
            value={delay}
            onChange={(e) => setDelay(Math.max(0, Number(e.target.value) || 0))}
          />
        </div>

        <div className="mt-auto flex flex-col gap-2 text-xs text-[--txt-2]">
          <div className="flex items-center justify-between">
            <span>Доступно: {pending.length}</span>
            {mode === 'selected' && <span>Выбрано: {selected.size}</span>}
            {mode !== 'selected' && <span>Отправим: {Math.min(count, pending.length)}</span>}
          </div>
          {progress && progress.total > 0 && (
            <div className="flex items-center justify-between rounded-md border border-[--line-1] bg-[--bg-2] px-2 py-1">
              <span>
                {progress.sent}/{progress.total} отправлено
              </span>
              {progress.failed > 0 && (
                <Badge variant="danger">ошибок: {progress.failed}</Badge>
              )}
            </div>
          )}
          <Button
            variant="primary"
            disabled={!canSend}
            onClick={sendNow}
            leftIcon={
              mode === 'random' ? (
                <Shuffle className="h-4 w-4" />
              ) : (
                <Send className="h-4 w-4" />
              )
            }
          >
            {busy ? 'Отправляем…' : 'Отправить приветствие'}
          </Button>
        </div>
      </aside>

      <section className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-[--txt-3]">Загрузка…</div>
        ) : pool.length === 0 ? (
          <div className="p-8 text-center text-sm text-[--txt-3]">
            Нет мужских пользователей в пуле — подождите новые комментарии и сообщения.
          </div>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
              <tr>
                <th className="w-10 px-3 py-2 text-left">
                  <input
                    type="checkbox"
                    checked={selected.size > 0 && selected.size === pending.length}
                    onChange={toggleAll}
                    disabled={mode !== 'selected'}
                  />
                </th>
                <th className="px-3 py-2 text-left">Пользователь</th>
                <th className="px-3 py-2 text-left">Источник</th>
                <th className="px-3 py-2 text-left">Платформа</th>
                <th className="px-3 py-2 text-left">Превью</th>
                <th className="px-3 py-2 text-left">Когда</th>
                <th className="px-3 py-2 text-left">Статус</th>
              </tr>
            </thead>
            <tbody>
              {pool.map((u) => (
                <PoolRow
                  key={u.key}
                  u={u}
                  checked={selected.has(u.key)}
                  disabled={mode !== 'selected' || u.welcome_sent}
                  onToggle={() => toggle(u.key)}
                />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

function PoolRow({
  u,
  checked,
  disabled,
  onToggle,
}: {
  u: PoolUser
  checked: boolean
  disabled: boolean
  onToggle: () => void
}) {
  return (
    <tr className="border-t border-[--line-1] hover:bg-[--bg-3]/40">
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          disabled={disabled}
        />
      </td>
      <td className="px-3 py-2 font-medium text-[--txt-1]">
        @{u.username ?? u.user_id ?? '—'}
      </td>
      <td className="px-3 py-2">
        <Badge variant={u.source === 'comment' ? 'info' : 'neutral'}>
          {u.source === 'comment' ? 'Комментарий' : 'Личное'}
        </Badge>
      </td>
      <td className="px-3 py-2 text-[--txt-2]">{u.platform}</td>
      <td className="max-w-[360px] truncate px-3 py-2 text-[--txt-2]">
        {u.preview ?? '—'}
      </td>
      <td className="px-3 py-2 text-[--txt-2]">
        {new Date(u.created_at).toLocaleString()}
      </td>
      <td className="px-3 py-2">
        {u.welcome_sent ? (
          <Badge variant="success">Отправлено</Badge>
        ) : (
          <Badge variant="neutral">Ожидание</Badge>
        )}
      </td>
    </tr>
  )
}

function DialogsTab() {
  const { data: accounts = [] } = useAccounts()
  const { data: incoming = [] } = useIncomingMessages()

  const bySender = useMemo(() => {
    const map = new Map<string, IncomingMessage[]>()
    for (const m of incoming) {
      const key = `${m.account_id}::${m.sender_username ?? m.sender_user_id ?? ''}`
      const arr = map.get(key) ?? []
      arr.push(m)
      map.set(key, arr)
    }
    return map
  }, [incoming])

  const conversations = useMemo(
    () =>
      Array.from(bySender.entries()).map(([key, messages]) => {
        const [accountId, sender] = key.split('::')
        return {
          key,
          accountId,
          sender,
          messages: messages.sort(
            (a, b) => new Date(a.received_at).getTime() - new Date(b.received_at).getTime(),
          ),
        }
      }),
    [bySender],
  )

  const [activeKey, setActiveKey] = useState<string | null>(null)
  const active = conversations.find((c) => c.key === activeKey) ?? conversations[0] ?? null
  const activeAccount = accounts.find((a) => a.id === active?.accountId)
  const [manualMode, setManualMode] = useState(false)

  return (
    <div className="flex h-full">
      <aside className="w-[280px] shrink-0 overflow-auto border-r border-[--line-1] bg-[--bg-1]">
        {conversations.length === 0 ? (
          <div className="p-6 text-center text-xs text-[--txt-3]">Нет диалогов</div>
        ) : (
          conversations.map((c) => {
            const last = c.messages[c.messages.length - 1]
            const isActive = (active?.key ?? null) === c.key
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => setActiveKey(c.key)}
                className={cn(
                  'flex w-full flex-col gap-1 border-b border-[--line-1] px-4 py-3 text-left transition-colors',
                  isActive ? 'bg-[--blue]/10' : 'hover:bg-[--bg-3]',
                )}
              >
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-[--txt-1]">@{c.sender || 'user'}</span>
                  <span className="text-[10px] text-[--txt-3]">
                    {new Date(last.received_at).toLocaleTimeString()}
                  </span>
                </div>
                <div className="truncate text-xs text-[--txt-2]">{last.message_text}</div>
              </button>
            )
          })
        )}
      </aside>

      <section className="flex flex-1 flex-col">
        {active ? (
          <>
            <div className="flex h-12 items-center justify-between border-b border-[--line-1] bg-[--bg-1] px-4">
              <div className="flex flex-col">
                <div className="text-sm font-medium">@{active.sender || 'user'}</div>
                <div className="text-[10px] text-[--txt-3]">
                  @{activeAccount?.username ?? active.accountId.slice(0, 8)}
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-[--txt-2]">
                <span>{manualMode ? 'Ручной' : 'Авто'}</span>
                <Switch checked={!manualMode} onChange={(v) => setManualMode(!v)} />
              </div>
            </div>

            <div className="flex-1 space-y-2 overflow-auto p-4">
              {active.messages.map((m) => (
                <div key={m.id} className="flex justify-start">
                  <div className="max-w-[70%] rounded-2xl rounded-bl-sm bg-[--bg-2] px-3 py-2 text-sm">
                    {m.message_text}
                    <div className="mt-1 text-[10px] text-[--txt-3]">
                      {new Date(m.received_at).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {manualMode && (
              <div className="flex items-center gap-2 border-t border-[--line-1] bg-[--bg-1] p-3">
                <input
                  type="text"
                  placeholder="Написать сообщение..."
                  className="h-10 flex-1 rounded-lg border border-[--line-2] bg-[--bg-3] px-3 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
                />
                <Button variant="primary" leftIcon={<Send className="h-4 w-4" />}>
                  Отправить
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-[--txt-3]">
            Выберите диалог
          </div>
        )}
      </section>
    </div>
  )
}

interface DMScanResult {
  username: string
  platform: string
  gender: string
}

function DMScannerTab() {
  const [results, setResults] = useState<DMScanResult[]>([])
  const [scanning, setScanning] = useState(false)
  const [filter, setFilter] = useState<'all' | 'male' | 'female' | 'unknown'>('all')

  const onScanAll = useCallback(async () => {
    setScanning(true)
    try {
      const { api } = await import('../api/client')
      const { data } = await api.post('/api/v1/dm/scan', { serial: '', platform: 'instagram' })
      const all: DMScanResult[] = []
      for (const item of data?.male ?? []) all.push({ ...item, gender: 'male' })
      for (const item of data?.female ?? []) all.push({ ...item, gender: 'female' })
      for (const item of data?.unknown ?? []) all.push({ ...item, gender: 'unknown' })
      setResults(all)
    } catch {
      // silently fail
    } finally {
      setScanning(false)
    }
  }, [])

  const onSave = useCallback(async (username: string) => {
    try {
      const { api } = await import('../api/client')
      await api.post('/api/v1/dm/save', { username })
    } catch {
      // silently fail
    }
  }, [])

  const filtered = useMemo(() => {
    if (filter === 'all') return results
    return results.filter((r) => r.gender === filter)
  }, [results, filter])

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center gap-3">
        <Button
          variant="primary"
          size="sm"
          onClick={onScanAll}
          disabled={scanning}
          leftIcon={scanning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Users className="h-3.5 w-3.5" />}
        >
          {scanning ? 'Scanning...' : 'Scan All Devices'}
        </Button>

        <div className="flex gap-1">
          {(['all', 'male', 'female', 'unknown'] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                'rounded-md px-3 py-1 text-xs transition-colors',
                filter === f
                  ? 'bg-[--blue]/15 text-[--blue]'
                  : 'text-[--txt-2] hover:text-[--txt-1]',
              )}
            >
              {f === 'all' ? 'All' : f === 'male' ? 'Male' : f === 'female' ? 'Female' : 'Unknown'}
            </button>
          ))}
        </div>

        <span className="text-xs text-[--txt-3]">{filtered.length} results</span>
      </div>

      {filtered.length === 0 ? (
        <div className="flex-1 text-center text-sm text-[--txt-3] pt-12">
          {results.length === 0 ? 'Click "Scan All Devices" to start' : 'No results for this filter'}
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-[--bg-1] text-xs uppercase tracking-wider text-[--txt-2]">
              <tr>
                <th className="px-3 py-2 text-left">Username</th>
                <th className="px-3 py-2 text-left">Platform</th>
                <th className="px-3 py-2 text-left">Gender</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={`${r.username}-${i}`} className="border-t border-[--line-1] hover:bg-[--bg-3]/40">
                  <td className="px-3 py-2 font-medium text-[--txt-1]">@{r.username}</td>
                  <td className="px-3 py-2 text-[--txt-2]">{r.platform}</td>
                  <td className="px-3 py-2">
                    {r.gender === 'female' ? (
                      <Badge variant="neutral">Muted</Badge>
                    ) : r.gender === 'male' ? (
                      <Badge variant="info">Male</Badge>
                    ) : (
                      <Badge variant="warning">Unknown</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.gender === 'male' && (
                      <Button variant="ghost" size="sm" onClick={() => onSave(r.username)}>
                        Add to DB
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
