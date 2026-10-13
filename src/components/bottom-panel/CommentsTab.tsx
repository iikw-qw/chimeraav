import { useMemo, useState } from 'react'
import { FixedSizeList as List } from 'react-window'
import { Download, Hand, MessageSquare, Search, SkipForward } from 'lucide-react'
import { Badge, Button, Input, Modal } from '../ui'
import { cn } from '../../lib/cn'
import {
  commentsExportUrl,
  sendWelcomeForComment,
  useComments,
  type CommentMetrics,
  type CommentRow,
} from '../../hooks/useComments'
import { toast } from '../../hooks/useToast'

const LANG_FLAGS: Record<string, string> = {
  en: '🇺🇸',
  ru: '🇷🇺',
  es: '🇪🇸',
  de: '🇩🇪',
  fr: '🇫🇷',
  pt: '🇵🇹',
  it: '🇮🇹',
}

const ROW_HEIGHT = 52

export function CommentsTab() {
  const [platform, setPlatform] = useState('')
  const [language, setLanguage] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<CommentRow | null>(null)

  const { data = [], isLoading } = useComments({
    platform: platform || undefined,
    language: language || undefined,
    reply_status: status || undefined,
  })

  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return data
    return data.filter((c) => {
      const name = (c.commenter_username ?? '').toLowerCase()
      const text = (c.comment_text ?? '').toLowerCase()
      return name.includes(needle) || text.includes(needle)
    })
  }, [data, search])

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const sendWelcome = async (row: CommentRow) => {
    try {
      await sendWelcomeForComment(row.id)
      toast.success(`Приветствие отправлено @${row.commenter_username ?? row.id}`)
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  return (
    <div className="flex h-full flex-col gap-2 text-xs">
      <div className="flex items-center gap-2">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-7 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
        >
          <option value="">Все платформы</option>
          <option value="instagram">Instagram</option>
          <option value="tiktok">TikTok</option>
          <option value="youtube">YouTube</option>
        </select>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="h-7 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
        >
          <option value="">Все языки</option>
          <option value="en">🇺🇸 EN</option>
          <option value="ru">🇷🇺 RU</option>
          <option value="es">🇪🇸 ES</option>
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-7 rounded-md border border-[--line-2] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none focus:border-[--blue]"
        >
          <option value="">Все статусы</option>
          <option value="pending">Ожидает</option>
          <option value="sent">Отправлено</option>
          <option value="skipped">Пропущено</option>
        </select>
        <div className="w-56">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск..."
            leftIcon={<Search className="h-3 w-3" />}
            className="h-7 text-xs"
          />
        </div>
        <div className="ml-auto">
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<Download className="h-3 w-3" />}
            onClick={() => window.open(commentsExportUrl({ platform, language }), '_blank')}
          >
            Экспорт Excel
          </Button>
        </div>
      </div>

      <div className="flex items-center border-b border-[--line-1] pb-1 text-[10px] uppercase tracking-wider text-[--txt-3]">
        <Header width={28} />
        <Header width={90}>Дата</Header>
        <Header width={140}>Username</Header>
        <Header width={64}>Язык</Header>
        <Header width={170}>Метрики</Header>
        <Header width={90}>Качество</Header>
        <Header flex>Комментарий</Header>
        <Header width={90}>Статус</Header>
        <Header width={110}>Действия</Header>
      </div>

      <div className="flex-1 min-h-0">
        {isLoading && rows.length === 0 ? (
          <div className="py-8 text-center text-[--txt-3]">Загрузка...</div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-[--txt-3]">Нет комментариев</div>
        ) : (
          <List
            height={Math.max(160, rows.length * ROW_HEIGHT > 400 ? 400 : rows.length * ROW_HEIGHT)}
            itemCount={rows.length}
            itemSize={ROW_HEIGHT}
            width="100%"
          >
            {({ index, style }) => {
              const row = rows[index]
              return (
                <div
                  key={row.id}
                  style={style}
                  className={cn(
                    'flex items-center border-b border-[--line-1]/60 px-1 text-xs hover:bg-[--bg-3]/40',
                    selected.has(row.id) && 'bg-[--blue]/5',
                  )}
                >
                  <Cell width={28}>
                    <input
                      type="checkbox"
                      checked={selected.has(row.id)}
                      onChange={() => toggle(row.id)}
                      className="h-3.5 w-3.5 accent-[--blue]"
                    />
                  </Cell>
                  <Cell width={90} className="text-[--txt-2]">
                    {formatDate(row.created_at)}
                  </Cell>
                  <Cell width={140}>
                    <button
                      type="button"
                      onClick={() => setDetail(row)}
                      className="truncate text-[--blue] hover:underline"
                    >
                      @{row.commenter_username ?? row.id.slice(0, 6)}
                    </button>
                  </Cell>
                  <Cell width={64}>
                    <Badge variant="neutral">
                      {LANG_FLAGS[row.commenter_language ?? ''] ?? '🌐'}{' '}
                      {row.commenter_language ?? '—'}
                    </Badge>
                  </Cell>
                  <Cell width={170} className="text-[10px] text-[--txt-2]">
                    {formatMetrics(row.commenter_metrics)}
                  </Cell>
                  <Cell width={90}>
                    <QualityBadge quality={row.commenter_profile_analysis?.quality} />
                  </Cell>
                  <Cell flex className="max-w-48 truncate pr-2">
                    {row.comment_text ?? '—'}
                  </Cell>
                  <Cell width={90}>
                    <StatusBadge row={row} />
                  </Cell>
                  <Cell width={110}>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5"
                        title="Приветствие"
                        onClick={() => sendWelcome(row)}
                      >
                        <Hand className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5"
                        title="Ответить"
                      >
                        <MessageSquare className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5"
                        title="Пропустить"
                      >
                        <SkipForward className="h-3 w-3" />
                      </Button>
                    </div>
                  </Cell>
                </div>
              )
            }}
          </List>
        )}
      </div>

      <CommentDetailModal row={detail} onClose={() => setDetail(null)} onWelcome={sendWelcome} />
    </div>
  )
}

function Header({
  width,
  flex,
  children,
}: {
  width?: number
  flex?: boolean
  children?: React.ReactNode
}) {
  return (
    <div
      className={cn('px-2 font-medium', flex && 'flex-1')}
      style={width ? { width } : undefined}
    >
      {children}
    </div>
  )
}

function Cell({
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

function QualityBadge({ quality }: { quality?: string }) {
  if (!quality) return <span className="text-[--txt-3]">—</span>
  if (quality === 'quality') return <Badge variant="success">quality</Badge>
  if (quality === 'suspicious') return <Badge variant="warning">suspicious</Badge>
  return <Badge variant="danger">{quality}</Badge>
}

function StatusBadge({ row }: { row: CommentRow }) {
  if (row.welcome_sent) return <Badge variant="success">welcome</Badge>
  if (row.reply_status === 'sent') return <Badge variant="info">replied</Badge>
  if (row.reply_status === 'skipped') return <Badge variant="neutral">skipped</Badge>
  return <Badge variant="neutral">pending</Badge>
}

function formatDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}.${dd} ${hh}:${mi}`
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
  const ageYears =
    typeof m.account_age_days === 'number'
      ? `${(m.account_age_days / 365).toFixed(1)}y`
      : '?'
  return `${followers}👥 ${posts}📷 ${ageYears}📅`
}

function CommentDetailModal({
  row,
  onClose,
  onWelcome,
}: {
  row: CommentRow | null
  onClose: () => void
  onWelcome: (row: CommentRow) => void
}) {
  if (!row) return null
  const metrics = row.commenter_metrics ?? {}
  return (
    <Modal
      open={!!row}
      onClose={onClose}
      title={`@${row.commenter_username ?? 'user'}`}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Закрыть
          </Button>
          <Button variant="primary" size="sm" onClick={() => onWelcome(row)}>
            Отправить приветствие
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[--bg-3] text-lg text-[--txt-2]">
            {(row.commenter_username ?? '?').slice(0, 2).toUpperCase()}
          </div>
          <div className="flex flex-col gap-1">
            <div className="font-medium">@{row.commenter_username ?? '—'}</div>
            <div className="flex flex-wrap gap-1">
              <Badge variant="info">{row.platform}</Badge>
              <Badge variant="neutral">{row.commenter_gender}</Badge>
              <QualityBadge quality={row.commenter_profile_analysis?.quality} />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <Stat label="Подписчики" value={metrics.followers} />
          <Stat label="Подписки" value={metrics.following} />
          <Stat label="Постов" value={metrics.posts} />
          <Stat label="Возраст, дн." value={metrics.account_age_days} />
          <Stat label="Ratio" value={metrics.ratio?.toFixed(2)} />
          <Stat label="Verified" value={metrics.verified ? 'да' : 'нет'} />
        </div>
        <div className="rounded-lg bg-[--bg-3] p-3 text-xs text-[--txt-2]">
          <div className="mb-1 text-[--txt-3]">Комментарий</div>
          <div className="text-[--txt-1]">{row.comment_text ?? '—'}</div>
        </div>
      </div>
    </Modal>
  )
}

function Stat({ label, value }: { label: string; value: unknown }) {
  const text =
    value === null || value === undefined || value === ''
      ? '—'
      : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
        ? String(value)
        : JSON.stringify(value)
  return (
    <div className="rounded-md bg-[--bg-3] p-2">
      <div className="text-[10px] text-[--txt-3]">{label}</div>
      <div className="text-sm text-[--txt-1]">{text}</div>
    </div>
  )
}
