import { useEffect, useMemo, useState } from 'react'
import { Send, Users } from 'lucide-react'
import { Badge, Button, Modal, ProgressBar, Slider } from '../ui'
import { cn } from '../../lib/cn'
import { useAccounts } from '../../hooks/useAccounts'
import type { CommentMetrics, CommentRow } from '../../hooks/useComments'
import {
  sendBulkWelcome,
  useReadyForWelcome,
  useWelcomeProgress,
} from '../../hooks/useWelcome'
import { toast } from '../../hooks/useToast'

const LANG_FLAGS: Record<string, string> = {
  en: '🇺🇸',
  ru: '🇷🇺',
  es: '🇪🇸',
  de: '🇩🇪',
  fr: '🇫🇷',
}

type Selection = 'selected' | 'first' | 'random' | 'newest'

export function WelcomeTab() {
  const { data: accounts = [] } = useAccounts()
  const { data: ready = [] } = useReadyForWelcome()
  const progress = useWelcomeProgress()

  const [accountId, setAccountId] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkOpen, setBulkOpen] = useState(false)

  useEffect(() => {
    if (!accountId && accounts[0]) setAccountId(accounts[0].id)
  }, [accounts, accountId])

  const rows = useMemo(
    () => (accountId ? ready.filter((r) => r.account_id === accountId) : ready),
    [ready, accountId],
  )

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const sendOne = async (row: CommentRow) => {
    try {
      await sendBulkWelcome({ comment_ids: [row.id] })
      toast.success(`Отправка @${row.commenter_username ?? ''} запланирована`)
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const sendSelected = async () => {
    const ids = Array.from(selected)
    if (ids.length === 0) return
    try {
      const res = await sendBulkWelcome({ comment_ids: ids })
      toast.success(`Поставлено в очередь: ${res.queued}`)
      setSelected(new Set())
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  return (
    <div className="flex h-full flex-col gap-2 text-xs">
      <div className="flex items-center gap-2">
        <select
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          className="h-7 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
        >
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              @{a.username} ({a.platform})
            </option>
          ))}
        </select>
        <Button
          variant="primary"
          size="sm"
          leftIcon={<Users className="h-3 w-3" />}
          onClick={() => setBulkOpen(true)}
        >
          Массовая отправка
        </Button>
        <div className="text-[--txt-2]">
          Доступно: <span className="text-[--txt-1] font-medium">{rows.length}</span>
        </div>
      </div>

      <div className="flex items-center border-b border-[--line-1] pb-1 text-[10px] uppercase tracking-wider text-[--txt-3]">
        <Col width={28} />
        <Col width={180}>Username</Col>
        <Col width={64}>Язык</Col>
        <Col flex>Метрики</Col>
        <Col width={110}>Дата</Col>
        <Col width={110}>Действие</Col>
      </div>

      <div className="flex-1 overflow-auto">
        {rows.length === 0 ? (
          <div className="py-8 text-center text-[--txt-3]">Некого приветствовать</div>
        ) : (
          rows.map((row) => (
            <div
              key={row.id}
              className={cn(
                'flex items-center border-b border-[--line-1]/60 py-1.5 hover:bg-[--bg-3]/40',
                selected.has(row.id) && 'bg-[--blue]/5',
              )}
            >
              <Col width={28}>
                <input
                  type="checkbox"
                  checked={selected.has(row.id)}
                  onChange={() => toggle(row.id)}
                  className="h-3.5 w-3.5 accent-[--blue]"
                />
              </Col>
              <Col width={180} className="truncate">
                @{row.commenter_username ?? row.id.slice(0, 6)}
              </Col>
              <Col width={64}>
                <Badge variant="neutral">
                  {LANG_FLAGS[row.commenter_language ?? ''] ?? '🌐'}{' '}
                  {row.commenter_language ?? '—'}
                </Badge>
              </Col>
              <Col flex className="text-[10px] text-[--txt-2]">
                {formatMetrics(row.commenter_metrics)}
              </Col>
              <Col width={110} className="text-[--txt-2]">
                {formatDate(row.created_at)}
              </Col>
              <Col width={110}>
                <Button variant="primary" size="sm" className="h-6 px-2" onClick={() => sendOne(row)}>
                  Отправить
                </Button>
              </Col>
            </div>
          ))
        )}
      </div>

      <div className="sticky bottom-0 flex items-center gap-2 border-t border-[--line-1] bg-[--bg-1] px-2 py-1.5">
        <div className="text-[--txt-2]">
          Выбрано: <span className="font-medium text-[--txt-1]">{selected.size}</span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          disabled={selected.size === 0}
          onClick={sendSelected}
          leftIcon={<Send className="h-3 w-3" />}
        >
          Отправить выбранным
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => setBulkOpen(true)}
          leftIcon={<Users className="h-3 w-3" />}
        >
          Массовая отправка
        </Button>
        {progress && progress.account_id === accountId && progress.total > 0 && (
          <div className="ml-auto flex items-center gap-2 text-[--txt-2]">
            <span>
              Отправлено {progress.sent}/{progress.total}
            </span>
            <div className="w-32">
              <ProgressBar value={progress.sent} max={progress.total} />
            </div>
          </div>
        )}
      </div>

      <BulkModal
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        accountId={accountId}
        selectedIds={Array.from(selected)}
        available={rows}
      />
    </div>
  )
}

function Col({
  width,
  flex,
  className,
  children,
}: {
  width?: number
  flex?: boolean
  className?: string
  children?: React.ReactNode
}) {
  return (
    <div
      className={cn('flex items-center px-2 text-[--txt-1]', flex && 'flex-1 min-w-0', className)}
      style={width ? { width, flexShrink: 0 } : undefined}
    >
      {children}
    </div>
  )
}

function BulkModal({
  open,
  onClose,
  accountId,
  selectedIds,
  available,
}: {
  open: boolean
  onClose: () => void
  accountId: string
  selectedIds: string[]
  available: CommentRow[]
}) {
  const [selection, setSelection] = useState<Selection>('selected')
  const [count, setCount] = useState(10)
  const [delay, setDelay] = useState(60)
  const [running, setRunning] = useState(false)
  const progress = useWelcomeProgress()

  const finalCount =
    selection === 'selected' ? selectedIds.length : Math.min(count, available.length)
  const etaMinutes = Math.max(1, Math.ceil((finalCount * delay) / 60))

  const pick = (): string[] => {
    if (selection === 'selected') return selectedIds
    const pool = [...available]
    if (selection === 'random') pool.sort(() => Math.random() - 0.5)
    else if (selection === 'newest')
      pool.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
    return pool.slice(0, finalCount).map((r) => r.id)
  }

  const run = async () => {
    const ids = pick()
    if (ids.length === 0) return
    setRunning(true)
    try {
      await sendBulkWelcome({ comment_ids: ids })
      toast.success(`Запущена рассылка (${ids.length} шт.)`)
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Массовая отправка"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={running}>
            Отмена
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={run}
            loading={running}
            disabled={finalCount === 0}
          >
            Запустить
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 text-sm">
        <div className="flex flex-col gap-2">
          <RadioRow
            checked={selection === 'selected'}
            onSelect={() => setSelection('selected')}
            label={`Выбранным (${selectedIds.length})`}
          />
          <RadioRow
            checked={selection === 'first'}
            onSelect={() => setSelection('first')}
            label="Первым N"
          />
          <RadioRow
            checked={selection === 'random'}
            onSelect={() => setSelection('random')}
            label="Случайным N"
          />
          <RadioRow
            checked={selection === 'newest'}
            onSelect={() => setSelection('newest')}
            label="Новейшим N"
          />
        </div>

        {selection !== 'selected' && (
          <div className="flex items-center gap-2">
            <span className="text-[--txt-2]">Количество</span>
            <input
              type="number"
              min={1}
              max={available.length}
              value={count}
              onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
              className="h-8 w-24 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1]"
            />
            <span className="text-xs text-[--txt-3]">из {available.length}</span>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs text-[--txt-2]">
            <span>Задержка между отправками</span>
            <span>{delay} сек</span>
          </div>
          <Slider min={30} max={120} step={5} value={delay} onChange={setDelay} />
        </div>

        <div className="rounded-lg bg-[--bg-3] p-3 text-xs text-[--txt-2]">
          Будет отправлено <span className="text-[--txt-1]">{finalCount}</span>{' '}
          приветствий за <span className="text-[--txt-1]">~{etaMinutes}</span> мин
          {accountId && (
            <span className="text-[--txt-3]"> (аккаунт {accountId.slice(0, 6)}…)</span>
          )}
        </div>

        {running && progress && progress.account_id === accountId && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs text-[--txt-2]">
              <span>
                Отправлено {progress.sent}/{progress.total}
              </span>
              <span>{progress.failed > 0 ? `Ошибок: ${progress.failed}` : ''}</span>
            </div>
            <ProgressBar value={progress.sent} max={Math.max(1, progress.total)} />
          </div>
        )}
      </div>
    </Modal>
  )
}

function RadioRow({
  checked,
  onSelect,
  label,
}: {
  checked: boolean
  onSelect: () => void
  label: string
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-[--txt-1]">
      <input
        type="radio"
        checked={checked}
        onChange={onSelect}
        className="h-3.5 w-3.5 accent-[--blue]"
      />
      {label}
    </label>
  )
}

function formatDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function compactNumber(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatMetrics(m?: CommentMetrics | null) {
  if (!m) return '—'
  const followers = typeof m.followers === 'number' ? compactNumber(m.followers) : '?'
  const posts = typeof m.posts === 'number' ? String(m.posts) : '?'
  const age =
    typeof m.account_age_days === 'number'
      ? `${(m.account_age_days / 365).toFixed(1)}y`
      : '?'
  return `${followers}👥 ${posts}📷 ${age}📅`
}
