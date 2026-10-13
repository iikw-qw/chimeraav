import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-react'
import { Badge, Button, Switch } from '../components/ui'
import { api } from '../api/client'
import { cn } from '../lib/cn'
import { useAccounts } from '../hooks/useAccounts'
import { useDatasets } from '../hooks/useDatasets'
import { toast } from '../hooks/useToast'

const PLATFORMS = [
  'instagram',
  'tiktok',
  'telegram',
  'twitter',
  'facebook',
  'youtube',
  'reddit',
  'threads',
] as const

type Platform = (typeof PLATFORMS)[number]
type StepState = 'idle' | 'active' | 'done'

const MIX_STRATEGIES = [
  {
    key: 'smart',
    brand: 'SmartMix',
    title: 'Умный микс',
    hint: 'Чередует износ и сдвиг — лучший выбор по умолчанию',
  },
  {
    key: 'cross',
    brand: 'CrossRotate',
    title: 'Кросс-ротация',
    hint: 'Берёт фото из разных корзин по очереди',
  },
  {
    key: 'stride',
    brand: 'ZebraStep',
    title: 'Зебра',
    hint: 'Шаг 1·3·5 → 2·4·6, ровное распределение',
  },
  {
    key: 'interleave',
    brand: 'EvenOdd',
    title: 'Чёт-нечёт',
    hint: 'Простое чередование, минимум совпадений',
  },
  {
    key: 'random_offset',
    brand: 'RandomDrift',
    title: 'Случайный сдвиг',
    hint: 'Стартовая точка случайная, дальше по порядку',
  },
  {
    key: 'wear',
    brand: 'ClassicWear',
    title: 'Классический износ',
    hint: 'Сначала наименее использованные фото',
  },
] as const

const MEDIA_KINDS = [
  { key: 'photo', label: 'Фото' },
  { key: 'video', label: 'Видео' },
] as const

type MixStrategy = (typeof MIX_STRATEGIES)[number]['key']
type MediaKind = (typeof MEDIA_KINDS)[number]['key']

const STEPS = [
  { key: 'photos', label: 'Выбор фото' },
  { key: 'cleaning', label: 'Очистка метаданных' },
  { key: 'caption', label: 'Генерация подписи' },
] as const

type StepKey = (typeof STEPS)[number]['key']

interface GeneratedPost {
  post_id: string
  photos: string[]
  caption: string
  metadata_cleaned: boolean
}

export function PostGeneratorPage() {
  const { data: accounts = [] } = useAccounts()
  const { data: datasets = [] } = useDatasets()

  const [accountId, setAccountId] = useState('')
  const [platform, setPlatform] = useState<Platform>('instagram')
  const [datasetId, setDatasetId] = useState('')
  const [cleanMetadata, setCleanMetadata] = useState(true)
  const [mixStrategy, setMixStrategy] = useState<MixStrategy>('smart')
  const [mediaKind, setMediaKind] = useState<MediaKind>('photo')
  const [photoCount, setPhotoCount] = useState(3)
  const [loading, setLoading] = useState(false)
  const [stepStates, setStepStates] = useState<Record<StepKey, StepState>>({
    photos: 'idle',
    cleaning: 'idle',
    caption: 'idle',
  })
  const [post, setPost] = useState<GeneratedPost | null>(null)
  const [caption, setCaption] = useState('')
  const [slide, setSlide] = useState(0)
  const [publishMode, setPublishMode] = useState<'instant' | 'scheduled' | 'auto'>('instant')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [autoPostsPerDay, setAutoPostsPerDay] = useState(3)
  const [region, setRegion] = useState<'us' | 'europe' | 'india' | 'uk'>('us')
  const [randomPhotoCount, setRandomPhotoCount] = useState(false)
  const [nextPrimeTime, setNextPrimeTime] = useState<string | null>(null)

  useEffect(() => {
    if (!accountId && accounts[0]) setAccountId(accounts[0].id)
  }, [accounts, accountId])
  useEffect(() => {
    if (!datasetId && datasets[0]) setDatasetId(datasets[0].id)
  }, [datasets, datasetId])

  useEffect(() => {
    api.get(`/api/v1/posts/prime-times?region=${region}`).then(({ data }) => {
      if (data?.prime_slots?.length) setNextPrimeTime(data.prime_slots[0])
    }).catch(() => {})
  }, [region])

  const canGenerate = !!accountId && !!datasetId && !loading

  const publishAtPrime = async () => {
    if (!post || !nextPrimeTime) return
    const today = new Date().toISOString().slice(0, 10)
    const scheduledAt = new Date(`${today}T${nextPrimeTime}:00`).toISOString()
    try {
      await api.post('/api/v1/schedule/assign', {
        post_id: post.post_id,
        scheduled_at: scheduledAt,
        platform,
      })
      toast.success(`Scheduled for prime time: ${nextPrimeTime}`)
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const runSteps = async () => {
    setStepStates({ photos: 'active', cleaning: 'idle', caption: 'idle' })
    await new Promise((r) => setTimeout(r, 250))
    setStepStates({
      photos: 'done',
      cleaning: cleanMetadata ? 'active' : 'done',
      caption: 'idle',
    })
    await new Promise((r) => setTimeout(r, 250))
    setStepStates({ photos: 'done', cleaning: 'done', caption: 'active' })
  }

  const generate = async () => {
    if (!canGenerate) return
    setLoading(true)
    setPost(null)
    try {
      runSteps()
      const { data } = await api.post<GeneratedPost>('/api/posts/generate', {
        account_id: accountId,
        platform,
        dataset_id: datasetId,
        photo_count: mediaKind === 'video' ? 1 : photoCount,
        mix_strategy: mixStrategy,
        media_kind: mediaKind,
        clean_metadata: cleanMetadata,
      })
      setPost(data)
      setCaption(data.caption ?? '')
      setSlide(0)
      setStepStates({ photos: 'done', cleaning: 'done', caption: 'done' })
      toast.success('Пост готов')
    } catch (err) {
      toast.danger((err as Error).message)
      setStepStates({ photos: 'idle', cleaning: 'idle', caption: 'idle' })
    } finally {
      setLoading(false)
    }
  }

  const publish = async () => {
    if (!post) return
    let schedule_at: string | null = null
    if (publishMode === 'scheduled' && scheduleDate && scheduleTime) {
      schedule_at = new Date(`${scheduleDate}T${scheduleTime}`).toISOString()
    }
    try {
      await api.post(`/api/posts/${post.post_id}/publish`, {
        schedule_at,
        auto_mode: publishMode === 'auto' ? { posts_per_day: autoPostsPerDay } : null,
      })
      const msgs: Record<string, string> = {
        instant: 'Поставлено в очередь на публикацию',
        scheduled: `Запланировано на ${scheduleDate} ${scheduleTime}`,
        auto: `Автопубликация: ${autoPostsPerDay} постов/день`,
      }
      toast.success(msgs[publishMode])
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const photos = post?.photos ?? []

  return (
    <motion.div
      className="flex h-full bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <aside className="flex w-80 shrink-0 flex-col gap-4 border-r border-[--line-1] bg-[--bg-1] p-5">
        <div>
          <Label>Аккаунт</Label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                @{a.username} ({a.platform})
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Платформа</Label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Датасет</Label>
          <select
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.photo_count})
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Тип контента</Label>
          <select
            value={mediaKind}
            onChange={(e) => setMediaKind(e.target.value as MediaKind)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            {MEDIA_KINDS.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Смешивание датасета</Label>
          <select
            value={mixStrategy}
            onChange={(e) => setMixStrategy(e.target.value as MixStrategy)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            {MIX_STRATEGIES.map((m) => (
              <option key={m.key} value={m.key}>
                {m.brand} · {m.title}
              </option>
            ))}
          </select>
          <div className="mt-1 rounded-md border border-[--line-1] bg-[--bg-2] p-2 text-[10px] leading-relaxed text-[--txt-3]">
            <div className="font-semibold text-[--txt-2]">
              {MIX_STRATEGIES.find((m) => m.key === mixStrategy)?.brand}
            </div>
            {MIX_STRATEGIES.find((m) => m.key === mixStrategy)?.hint}
          </div>
        </div>

        <div>
          <Label>Регион (prime time)</Label>
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value as typeof region)}
            className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          >
            <option value="us">US (EST)</option>
            <option value="europe">Europe (CET)</option>
            <option value="india">India (IST)</option>
            <option value="uk">UK (GMT)</option>
          </select>
          {nextPrimeTime && (
            <div className="mt-1 text-[10px] text-[--green]">
              Next prime time: {nextPrimeTime}
            </div>
          )}
        </div>

        {mediaKind === 'photo' && (
          <div>
            <Label>Фото в посте</Label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={9}
                value={photoCount}
                disabled={randomPhotoCount}
                onChange={(e) => setPhotoCount(Math.max(1, Math.min(9, Number(e.target.value) || 1)))}
                className="h-10 flex-1 rounded-lg border border-[--line-2] bg-[--bg-3] px-2 text-sm text-[--txt-1] outline-none focus:border-[--blue] disabled:opacity-50"
              />
              <label className="flex items-center gap-1.5 text-xs text-[--txt-2] whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={randomPhotoCount}
                  onChange={(e) => setRandomPhotoCount(e.target.checked)}
                />
                Random
              </label>
            </div>
          </div>
        )}

        {mediaKind === 'photo' && (
          <div className="flex items-center justify-between rounded-lg border border-[--line-1] bg-[--bg-3] px-3 py-2">
            <div className="text-sm text-[--txt-1]">Автоочистка метаданных</div>
            <Switch checked={cleanMetadata} onChange={setCleanMetadata} />
          </div>
        )}

        <Button
          variant="primary"
          size="lg"
          leftIcon={<Sparkles className="h-4 w-4" />}
          disabled={!canGenerate}
          loading={loading}
          onClick={generate}
        >
          Сгенерировать пост
        </Button>

        <Steps states={stepStates} cleanMetadata={cleanMetadata} />
      </aside>

      <section className="flex flex-1 flex-col gap-4 overflow-auto p-6">
        <PreviewCarousel
          photos={photos}
          cleaned={post?.metadata_cleaned ?? false}
          slide={slide}
          onSlideChange={setSlide}
        />

        <div className="flex flex-col gap-2">
          <Label>Подпись</Label>
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Подпись к посту появится здесь после генерации..."
            className="min-h-[140px] w-full rounded-lg border border-[--line-2] bg-[--bg-2] p-3 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
          />
        </div>

        <div className="space-y-3">
          <div className="flex gap-3">
            {(['instant', 'scheduled', 'auto'] as const).map((m) => (
              <label key={m} className="flex items-center gap-1.5 text-sm text-[--txt-1]">
                <input
                  type="radio"
                  name="publishMode"
                  value={m}
                  checked={publishMode === m}
                  onChange={() => setPublishMode(m)}
                />
                {m === 'instant' ? 'Сейчас' : m === 'scheduled' ? 'По расписанию' : 'Автоматически'}
              </label>
            ))}
          </div>

          {publishMode === 'scheduled' && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={scheduleDate}
                onChange={(e) => setScheduleDate(e.target.value)}
                className="rounded-lg border border-[--line-2] bg-[--bg-3] px-2 py-1 text-sm text-[--txt-1] outline-none"
              />
              <input
                type="text"
                placeholder="14:30:00"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value.replace(/[^0-9:]/g, ''))}
                className="w-28 rounded-lg border border-[--line-2] bg-[--bg-3] px-2 py-1 font-mono text-sm text-[--txt-1] outline-none"
              />
            </div>
          )}

          {publishMode === 'auto' && (
            <div className="flex items-center gap-2">
              <Label>Постов в день</Label>
              <input
                type="number"
                min={1}
                max={50}
                value={autoPostsPerDay}
                onChange={(e) => setAutoPostsPerDay(Math.max(1, Number(e.target.value) || 1))}
                className="w-20 rounded-lg border border-[--line-2] bg-[--bg-3] px-2 py-1 text-sm text-[--txt-1] outline-none"
              />
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              disabled={!post}
              onClick={publish}
              leftIcon={<Send className="h-4 w-4" />}
            >
              {publishMode === 'instant' ? 'Опубликовать сейчас' : publishMode === 'scheduled' ? 'Запланировать' : 'Автопубликация'}
            </Button>
            <Button
              variant="secondary"
              disabled={!post || !nextPrimeTime}
              onClick={publishAtPrime}
              leftIcon={<Calendar className="h-4 w-4" />}
            >
              Prime Time
            </Button>
            <Button
              variant="ghost"
              disabled={!post || loading}
              onClick={generate}
              leftIcon={<RefreshCw className="h-4 w-4" />}
            >
              Регенерировать
            </Button>
          </div>
        </div>
      </section>
    </motion.div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 text-xs font-medium uppercase tracking-wider text-[--txt-3]">
      {children}
    </div>
  )
}

function Steps({
  states,
  cleanMetadata,
}: {
  states: Record<StepKey, StepState>
  cleanMetadata: boolean
}) {
  const allDone = Object.values(states).every((s) => s === 'done')
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[--line-1] bg-[--bg-2] p-3 text-xs">
      <div className="text-[10px] uppercase tracking-wider text-[--txt-3]">Процесс</div>
      {STEPS.map((step, idx) => {
        const skipped = step.key === 'cleaning' && !cleanMetadata
        const state = skipped ? 'done' : states[step.key]
        return (
          <div key={step.key} className="flex items-center gap-2">
            <StepDot state={state} index={idx + 1} />
            <span
              className={cn(
                'flex-1',
                state === 'done' && 'text-[--txt-1]',
                state === 'active' && 'text-[--blue]',
                state === 'idle' && 'text-[--txt-3]',
              )}
            >
              {step.label}
              {skipped && <span className="ml-2 text-[--txt-3]">(пропущено)</span>}
            </span>
          </div>
        )
      })}
      {allDone && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-1 flex items-center gap-2 text-[--green]"
        >
          <Check className="h-4 w-4" /> Готово
        </motion.div>
      )}
    </div>
  )
}

function StepDot({ state, index }: { state: StepState; index: number }) {
  if (state === 'done')
    return (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[--green] text-white">
        <Check className="h-3 w-3" />
      </div>
    )
  if (state === 'active')
    return (
      <motion.div
        className="flex h-5 w-5 items-center justify-center rounded-full bg-[--blue] text-white text-[10px]"
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ repeat: Infinity, duration: 1.2 }}
      >
        {index}
      </motion.div>
    )
  return (
    <div className="flex h-5 w-5 items-center justify-center rounded-full border border-[--line-2] text-[10px] text-[--txt-3]">
      {index}
    </div>
  )
}

function PreviewCarousel({
  photos,
  cleaned,
  slide,
  onSlideChange,
}: {
  photos: string[]
  cleaned: boolean
  slide: number
  onSlideChange: (n: number) => void
}) {
  const safeIndex = useMemo(
    () => (photos.length === 0 ? 0 : Math.min(slide, photos.length - 1)),
    [slide, photos.length],
  )

  if (photos.length === 0) {
    return (
      <div className="flex h-80 items-center justify-center rounded-xl border border-dashed border-[--line-2] bg-[--bg-2] text-sm text-[--txt-3]">
        Здесь появится превью карусели
      </div>
    )
  }

  const prev = () => onSlideChange((safeIndex - 1 + photos.length) % photos.length)
  const next = () => onSlideChange((safeIndex + 1) % photos.length)

  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-80 overflow-hidden rounded-xl border border-[--line-1] bg-black">
        <AnimatePresence mode="wait">
          <motion.div
            key={photos[safeIndex]}
            className="flex h-full w-full items-center justify-center text-xs text-white/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <img
              src={`/api/v1/media/${encodeURIComponent(photos[safeIndex])}/thumb`}
              alt={photos[safeIndex]}
              className="h-full w-full object-contain"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
                (e.target as HTMLImageElement).parentElement!.querySelector('span')!.style.display = '';
              }}
            />
            <span className="break-all px-4 text-center" style={{ display: 'none' }}>{photos[safeIndex]}</span>
          </motion.div>
        </AnimatePresence>

        {cleaned && (
          <div className="absolute left-3 top-3">
            <Badge variant="success">Очищено ✓</Badge>
          </div>
        )}

        <button
          type="button"
          onClick={prev}
          className="absolute left-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={next}
          className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {photos.map((p, i) => (
          <button
            key={p}
            type="button"
            onClick={() => onSlideChange(i)}
            className={cn(
              'relative flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border bg-[--bg-2] text-[9px] text-[--txt-3]',
              i === safeIndex ? 'border-[--blue]' : 'border-[--line-1]',
            )}
            title={p}
          >
            <img
              src={`/api/v1/media/${encodeURIComponent(p)}/thumb`}
              alt={p.split(/[\\/]/).pop() ?? ''}
              className="h-full w-full object-cover rounded-lg"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
            <span className="absolute inset-0 flex items-center justify-center truncate px-1">{p.split(/[\\/]/).pop()}</span>
            {cleaned && (
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[--green] text-[9px] text-white">
                ✓
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

export { PostGeneratorPage as PostGenerator }
