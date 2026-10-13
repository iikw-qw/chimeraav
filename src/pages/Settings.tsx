import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  Bell,
  Bot,
  Database,
  EyeOff,
  FileStack,
  HelpCircle,
  Image as ImageIcon,
  Info,
  MessageCircle,
  Monitor,
  Network,
  Plus,
  Save,
  Send,
  Settings as SettingsIcon,
  Shield,
  Sparkles,
  Trash2,
  UserSearch,
  Zap,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Input,
  Slider,
  Switch,
  Tooltip,
} from '../components/ui'
import { cn } from '../lib/cn'
import { toast } from '../hooks/useToast'
import { useSettings, useSaveSettings } from '../hooks/useSettings'
import {
  PROXIES_QUERY_KEY,
  checkAllProxies,
  createProxy,
  deleteProxy,
  updateProxy,
  useProxies,
  type ProxyRow,
} from '../hooks/useProxies'
import {
  TEMPLATES_QUERY_KEY,
  createTemplate,
  deleteTemplate,
  updateTemplate,
  useTemplates,
  type TemplateRow,
} from '../hooks/useTemplates'
import { api } from '../api/client'
import { useAppStore } from '../stores/appStore'

type SectionKey =
  | 'general'
  | 'stream'
  | 'analysis'
  | 'autoreply'
  | 'welcome'
  | 'warmup'
  | 'proxies'
  | 'antidetect'
  | 'content'
  | 'metadata'
  | 'backups'
  | 'guide'
  | 'about'

const SECTIONS: Array<{ key: SectionKey; title: string; icon: ReactNode }> = [
  { key: 'general', title: 'Общие', icon: <SettingsIcon className="h-4 w-4" /> },
  { key: 'stream', title: 'Демонстрация экрана', icon: <Monitor className="h-4 w-4" /> },
  { key: 'analysis', title: 'Анализ аккаунтов', icon: <UserSearch className="h-4 w-4" /> },
  { key: 'autoreply', title: 'Автоответ', icon: <Bot className="h-4 w-4" /> },
  { key: 'welcome', title: 'Приветствия', icon: <MessageCircle className="h-4 w-4" /> },
  { key: 'warmup', title: 'Прогрев', icon: <Activity className="h-4 w-4" /> },
  { key: 'proxies', title: 'Прокси', icon: <Network className="h-4 w-4" /> },
  { key: 'antidetect', title: 'Антидетект', icon: <EyeOff className="h-4 w-4" /> },
  { key: 'content', title: 'Контент и датасеты', icon: <ImageIcon className="h-4 w-4" /> },
  { key: 'metadata', title: 'Метаданные', icon: <FileStack className="h-4 w-4" /> },
  { key: 'backups', title: 'Бэкапы', icon: <Database className="h-4 w-4" /> },
  { key: 'guide', title: 'Методичка', icon: <HelpCircle className="h-4 w-4" /> },
  { key: 'about', title: 'О программе', icon: <Info className="h-4 w-4" /> },
]

const DEFAULTS: Record<string, unknown> = {
  language: 'ru',
  autostart: false,
  minimize_to_tray: true,
  cell_size: 'medium',
  analysis_min_followers: 10,
  analysis_min_posts: 1,
  analysis_min_account_age_days: 30,
  analysis_max_follow_ratio: 50,
  autoreply_language: 'en',
  autoreply_llm_url: 'https://api.openai.com/v1',
  autoreply_llm_key: '',
  autoreply_llm_model: 'gpt-4o-mini',
  autoreply_temperature: 0.7,
  welcome_delay_seconds: 60,
  warmup_base_devices: 50,
  warmup_adaptive: true,
  telegram_bot_token: '',
  telegram_chat_ids: '',
  telegram_notify_filters: 'all',
  antidetect_rotate_minutes: 120,
  antidetect_profile: 'samsung',
  human_input_enabled: true,
  human_behavior_profile: 'normal',
  cursor_overlay: true,
  native_pointer: false,
  twocaptcha_api_key: '',
  stream_preset: 'smooth',
  mixing_strategy: 'smart',
  gallery_publish: true,
  metadata_autoclean: true,
  metadata_level: 'medium',
  backup_auto: true,
  backup_time: '03:00',
  backup_keep: 7,
}

export function Settings() {
  const [active, setActive] = useState<SectionKey>('general')
  const { data: server = {} } = useSettings()
  const save = useSaveSettings()
  const [form, setForm] = useState<Record<string, unknown>>({})
  const hydratedRef = useRef(false)

  useEffect(() => {
    if (hydratedRef.current) return
    setForm({ ...DEFAULTS, ...server })
    hydratedRef.current = true
  }, [server])

  const set = (key: string, value: unknown) => setForm((f) => ({ ...f, [key]: value }))
  const get = <T = unknown,>(key: string): T => (form[key] as T) ?? (DEFAULTS[key] as T)

  const dirty = useMemo(() => {
    return Object.keys(form).some((k) => form[k] !== (server[k] ?? DEFAULTS[k]))
  }, [form, server])

  const handleSave = async () => {
    try {
      await save.mutateAsync(form)
      toast.success('Настройки сохранены')
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  return (
    <motion.div
      className="flex h-full bg-[--bg-0]"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <aside className="w-52 shrink-0 overflow-y-auto border-r border-[--line-1] bg-[--bg-1] py-3">
        {SECTIONS.map((s, i) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setActive(s.key)}
            className={cn(
              'flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors',
              active === s.key
                ? 'bg-[--blue]/10 text-[--blue]'
                : 'text-[--txt-1] hover:bg-[--bg-3]/50',
            )}
          >
            <span className="text-[--txt-2]">{s.icon}</span>
            <span className="flex-1 truncate">
              {i + 1}. {s.title}
            </span>
          </button>
        ))}
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 p-6 pb-24">
          {active === 'general' && <GeneralSection form={form} set={set} get={get} />}
          {active === 'stream' && <StreamSection form={form} set={set} get={get} />}
          {active === 'analysis' && <AnalysisSection form={form} set={set} get={get} />}
          {active === 'autoreply' && <AutoReplySection form={form} set={set} get={get} />}
          {active === 'welcome' && <WelcomeSection form={form} set={set} get={get} />}
          {active === 'warmup' && <WarmupSection form={form} set={set} get={get} />}
          {active === 'proxies' && <ProxiesSection />}
          {active === 'antidetect' && <AntidetectSection form={form} set={set} get={get} />}
          {active === 'content' && <ContentSection form={form} set={set} get={get} />}
          {active === 'metadata' && <MetadataSection form={form} set={set} get={get} />}
          {active === 'backups' && <BackupsSection form={form} set={set} get={get} />}
          {active === 'guide' && <GuideSection />}
          {active === 'about' && <AboutSection />}
        </div>

        <div className="sticky bottom-0 z-10 flex items-center justify-end gap-3 border-t border-[--line-1] bg-[--bg-1]/95 px-6 py-3 backdrop-blur">
          {dirty && <span className="text-xs text-[--amber]">Несохранённые изменения</span>}
          <Button
            variant="primary"
            leftIcon={<Save className="h-4 w-4" />}
            onClick={handleSave}
            loading={save.isPending}
            disabled={!dirty}
          >
            Сохранить
          </Button>
        </div>
      </main>
    </motion.div>
  )
}

type SectionProps = {
  form: Record<string, unknown>
  set: (key: string, value: unknown) => void
  get: <T = unknown>(key: string) => T
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <label className="text-sm font-medium text-[--txt-1]">{label}</label>
        {hint && (
          <Tooltip content={hint}>
            <HelpCircle className="h-3.5 w-3.5 text-[--txt-3]" />
          </Tooltip>
        )}
      </div>
      {children}
    </div>
  )
}

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-b border-[--line-1] pb-3">
      <h2 className="text-lg font-semibold text-[--txt-1]">{title}</h2>
      {description && <p className="mt-1 text-sm text-[--txt-3]">{description}</p>}
    </div>
  )
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string
  options: Array<{ value: string; label: string }>
  onChange: (v: string) => void
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 w-full rounded-lg border border-[--line-2] bg-[--bg-3] px-3 text-sm text-[--txt-1] focus:border-[--blue] focus:outline-none focus:ring-2 focus:ring-[--blue]/20"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

function GeneralSection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader title="Общие" />
      <Field label="Язык" hint="Язык интерфейса Chimera">
        <Select
          value={get<string>('language')}
          onChange={(v) => set('language', v)}
          options={[
            { value: 'ru', label: 'Русский' },
            { value: 'en', label: 'English' },
          ]}
        />
      </Field>
      <Field label="Автозапуск" hint="Запускать Chimera при старте Windows">
        <Switch checked={get<boolean>('autostart')} onChange={(v) => set('autostart', v)} />
      </Field>
      <Field label="Сворачивать в трей" hint="При закрытии окна приложение продолжает работать в трее">
        <Switch
          checked={get<boolean>('minimize_to_tray')}
          onChange={(v) => set('minimize_to_tray', v)}
        />
      </Field>
      <Field label="Размер ячеек устройств" hint="Плотность сетки в Phone Grid">
        <Select
          value={get<string>('cell_size')}
          onChange={(v) => set('cell_size', v)}
          options={[
            { value: 'small', label: 'Мелкие' },
            { value: 'medium', label: 'Средние' },
            { value: 'large', label: 'Крупные' },
          ]}
        />
      </Field>
    </>
  )
}

function AnalysisSection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader
        title="Анализ аккаунтов"
        description="Критерии качества для сохранения профилей комментаторов"
      />
      <Field label="Минимум подписчиков" hint="Аккаунты с меньшим числом считаются ботами">
        <Input
          type="number"
          value={get<number>('analysis_min_followers')}
          onChange={(e) => set('analysis_min_followers', Number(e.target.value))}
        />
      </Field>
      <Field label="Минимум постов" hint="Если 0 — аккаунт считается неактивным">
        <Input
          type="number"
          value={get<number>('analysis_min_posts')}
          onChange={(e) => set('analysis_min_posts', Number(e.target.value))}
        />
      </Field>
      <Field label="Минимум возраст (дней)" hint="Свежие аккаунты подозрительны">
        <Input
          type="number"
          value={get<number>('analysis_min_account_age_days')}
          onChange={(e) => set('analysis_min_account_age_days', Number(e.target.value))}
        />
      </Field>
      <Field
        label="Максимум ratio (following/followers)"
        hint="Слишком большое ratio — массфоловинг"
      >
        <Input
          type="number"
          value={get<number>('analysis_max_follow_ratio')}
          onChange={(e) => set('analysis_max_follow_ratio', Number(e.target.value))}
        />
      </Field>
    </>
  )
}

function AutoReplySection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader title="Автоответ" description="LLM-ответы на входящие сообщения (EN only)" />
      <Field label="Язык ответов">
        <div className="flex items-center gap-2">
          <Badge variant="info">EN (fixed)</Badge>
          <span className="text-xs text-[--txt-3]">
            Авто-ответ работает только на английском языке
          </span>
        </div>
      </Field>
      <Field label="LLM API URL" hint="OpenAI-совместимый endpoint">
        <Input
          value={get<string>('autoreply_llm_url')}
          onChange={(e) => set('autoreply_llm_url', e.target.value)}
          placeholder="https://api.openai.com/v1"
        />
      </Field>
      <Field label="API Key" hint="Ключ хранится локально">
        <Input
          type="password"
          value={get<string>('autoreply_llm_key')}
          onChange={(e) => set('autoreply_llm_key', e.target.value)}
          placeholder="sk-..."
        />
      </Field>
      <Field label="Модель">
        <Input
          value={get<string>('autoreply_llm_model')}
          onChange={(e) => set('autoreply_llm_model', e.target.value)}
          placeholder="gpt-4o-mini"
        />
      </Field>
      <Field
        label={`Temperature: ${Number(get<number>('autoreply_temperature')).toFixed(2)}`}
        hint="Креативность ответов (0 — детерминированно, 1 — разнообразно)"
      >
        <Slider
          min={0}
          max={1}
          step={0.05}
          value={get<number>('autoreply_temperature')}
          onChange={(v) => set('autoreply_temperature', v)}
        />
      </Field>
    </>
  )
}

function WelcomeSection({ set, get }: SectionProps) {
  const { data: templates = [] } = useTemplates()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<{ name: string; template_text: string }>({
    name: '',
    template_text: '',
  })

  const refresh = () => qc.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY })

  const addTemplate = async () => {
    if (!draft.name.trim() || !draft.template_text.trim()) return
    try {
      await createTemplate({
        name: draft.name.trim(),
        template_text: draft.template_text.trim(),
        style: 'welcome',
        language: 'en',
        is_active: true,
      })
      setDraft({ name: '', template_text: '' })
      toast.success('Шаблон добавлен')
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const toggleActive = async (t: TemplateRow) => {
    try {
      await updateTemplate(t.id, { is_active: !t.is_active })
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const remove = async (t: TemplateRow) => {
    try {
      await deleteTemplate(t.id)
      toast.success('Шаблон удалён')
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  return (
    <>
      <SectionHeader title="Приветствия" description="Шаблоны сообщений для welcome-цепочек" />
      <Field
        label={`Задержка между отправками: ${get<number>('welcome_delay_seconds')} сек`}
        hint="Добавляет случайный jitter ±30%"
      >
        <Slider
          min={30}
          max={120}
          step={5}
          value={get<number>('welcome_delay_seconds')}
          onChange={(v) => set('welcome_delay_seconds', v)}
        />
      </Field>

      <div className="space-y-2">
        <div className="text-sm font-medium text-[--txt-1]">Шаблоны ({templates.length})</div>
        <div className="space-y-2">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-start gap-3 rounded-lg border border-[--line-1] bg-[--bg-1] p-3"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[--txt-1]">{t.name}</span>
                  <Badge variant={t.is_active ? 'success' : 'neutral'}>
                    {t.is_active ? 'активен' : 'выкл'}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-[--txt-3]">{t.template_text}</div>
              </div>
              <Switch checked={t.is_active} onChange={() => toggleActive(t)} />
              <button
                type="button"
                onClick={() => remove(t)}
                className="text-[--txt-3] hover:text-[--red]"
                aria-label="Удалить"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2 rounded-lg border border-dashed border-[--line-2] p-3">
        <div className="text-sm font-medium text-[--txt-1]">Новый шаблон</div>
        <Input
          value={draft.name}
          onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
          placeholder="Название"
        />
        <textarea
          value={draft.template_text}
          onChange={(e) => setDraft((d) => ({ ...d, template_text: e.target.value }))}
          placeholder="Hey {username}! Love your photos ✨"
          className="min-h-[80px] w-full rounded-lg border border-[--line-2] bg-[--bg-3] p-3 text-sm text-[--txt-1] focus:border-[--blue] focus:outline-none focus:ring-2 focus:ring-[--blue]/20"
        />
        <Button
          variant="secondary"
          leftIcon={<Plus className="h-3 w-3" />}
          size="sm"
          onClick={addTemplate}
          disabled={!draft.name.trim() || !draft.template_text.trim()}
        >
          Добавить
        </Button>
      </div>
    </>
  )
}

function WarmupSection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader
        title="Прогрев"
        description="Базовое число устройств для коэффициента прогрева"
      />
      <Field label="Базовое число устройств" hint="Коэффициент = active_devices / base. Default 50">
        <Input
          type="number"
          value={get<number>('warmup_base_devices')}
          onChange={(e) => set('warmup_base_devices', Number(e.target.value))}
        />
      </Field>
      <Field label="Адаптивный коэффициент" hint="Автоматически перенормирует при росте парка">
        <Switch
          checked={get<boolean>('warmup_adaptive')}
          onChange={(v) => set('warmup_adaptive', v)}
        />
      </Field>
    </>
  )
}

function TelegramSection({ set, get }: SectionProps) {
  const [testing, setTesting] = useState(false)

  const test = async () => {
    setTesting(true)
    try {
      await api.post('/api/telegram/test', {
        bot_token: get<string>('telegram_bot_token'),
        chat_ids: get<string>('telegram_chat_ids'),
      })
      toast.success('Тестовое сообщение отправлено')
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <>
      <SectionHeader title="Telegram" description="Уведомления о входящих сообщениях" />
      <Field label="Bot Token" hint="Получите у @BotFather">
        <Input
          type="password"
          value={get<string>('telegram_bot_token')}
          onChange={(e) => set('telegram_bot_token', e.target.value)}
          placeholder="123456:ABC..."
        />
      </Field>
      <Field label="Chat IDs" hint="Через запятую. Личный чат или @channel">
        <Input
          value={get<string>('telegram_chat_ids')}
          onChange={(e) => set('telegram_chat_ids', e.target.value)}
          placeholder="123456789, -100987654321"
        />
      </Field>
      <Field label="Фильтры">
        <Select
          value={get<string>('telegram_notify_filters')}
          onChange={(v) => set('telegram_notify_filters', v)}
          options={[
            { value: 'all', label: 'Все сообщения' },
            { value: 'english_only', label: 'Только на английском' },
            { value: 'male_only', label: 'Только от мужчин' },
          ]}
        />
      </Field>
      <div>
        <Button
          variant="secondary"
          leftIcon={<Bell className="h-4 w-4" />}
          onClick={test}
          loading={testing}
        >
          Тест уведомления
        </Button>
      </div>
    </>
  )
}

function ProxiesSection() {
  const { data: proxies = [] } = useProxies()
  const qc = useQueryClient()
  const [draft, setDraft] = useState({
    address: '',
    port: 1080,
    protocol: 'http',
    username: '',
    password: '',
    country: '',
  })
  const [checking, setChecking] = useState(false)

  const refresh = () => qc.invalidateQueries({ queryKey: PROXIES_QUERY_KEY })

  const add = async () => {
    if (!draft.address || !draft.port) return
    try {
      await createProxy({
        address: draft.address,
        port: Number(draft.port),
        protocol: draft.protocol,
        username: draft.username || null,
        password: draft.password || null,
        country: draft.country || null,
        is_active: true,
      })
      setDraft({ address: '', port: 1080, protocol: 'http', username: '', password: '', country: '' })
      toast.success('Прокси добавлен')
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const remove = async (p: ProxyRow) => {
    try {
      await deleteProxy(p.id)
      toast.success('Прокси удалён')
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const toggle = async (p: ProxyRow) => {
    try {
      await updateProxy(p.id, { is_active: !p.is_active })
      refresh()
    } catch (err) {
      toast.danger((err as Error).message)
    }
  }

  const checkAll = async () => {
    setChecking(true)
    try {
      await checkAllProxies()
      toast.success('Проверка запущена')
      setTimeout(refresh, 2000)
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setChecking(false)
    }
  }

  return (
    <>
      <div className="flex items-center justify-between border-b border-[--line-1] pb-3">
        <div>
          <h2 className="text-lg font-semibold text-[--txt-1]">Прокси</h2>
          <p className="mt-1 text-sm text-[--txt-3]">
            {proxies.length} записей · {proxies.filter((p) => p.leak_check_passed).length} прошли проверку
          </p>
        </div>
        <Button
          variant="secondary"
          leftIcon={<Shield className="h-4 w-4" />}
          onClick={checkAll}
          loading={checking}
        >
          Проверить все
        </Button>
      </div>

      <div className="overflow-hidden rounded-lg border border-[--line-1]">
        <table className="w-full text-sm">
          <thead className="bg-[--bg-2] text-xs uppercase text-[--txt-2]">
            <tr>
              <th className="px-3 py-2 text-left">Адрес</th>
              <th className="px-3 py-2 text-left">Тип</th>
              <th className="px-3 py-2 text-left">Страна</th>
              <th className="px-3 py-2 text-left">Статус</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {proxies.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-xs text-[--txt-3]">
                  Нет прокси
                </td>
              </tr>
            )}
            {proxies.map((p) => (
              <tr key={p.id} className="border-t border-[--line-1]">
                <td className="px-3 py-2 font-mono text-xs">
                  {p.address}:{p.port}
                </td>
                <td className="px-3 py-2 uppercase text-[--txt-2]">{p.protocol}</td>
                <td className="px-3 py-2 text-[--txt-2]">{p.country ?? '—'}</td>
                <td className="px-3 py-2">
                  <Badge variant={p.leak_check_passed ? 'success' : 'warning'}>
                    {p.leak_check_passed ? 'ok' : 'не проверен'}
                  </Badge>
                </td>
                <td className="px-3 py-2 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Switch checked={p.is_active} onChange={() => toggle(p)} />
                    <button
                      type="button"
                      onClick={() => remove(p)}
                      className="text-[--txt-3] hover:text-[--red]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-2 rounded-lg border border-dashed border-[--line-2] p-3">
        <div className="text-sm font-medium text-[--txt-1]">Добавить прокси</div>
        <div className="grid grid-cols-2 gap-2">
          <Input
            value={draft.address}
            onChange={(e) => setDraft((d) => ({ ...d, address: e.target.value }))}
            placeholder="host.example.com"
          />
          <Input
            type="number"
            value={draft.port}
            onChange={(e) => setDraft((d) => ({ ...d, port: Number(e.target.value) }))}
            placeholder="1080"
          />
          <Select
            value={draft.protocol}
            onChange={(v) => setDraft((d) => ({ ...d, protocol: v }))}
            options={[
              { value: 'http', label: 'HTTP' },
              { value: 'https', label: 'HTTPS' },
              { value: 'socks5', label: 'SOCKS5' },
            ]}
          />
          <Input
            value={draft.country}
            onChange={(e) => setDraft((d) => ({ ...d, country: e.target.value }))}
            placeholder="US"
          />
          <Input
            value={draft.username}
            onChange={(e) => setDraft((d) => ({ ...d, username: e.target.value }))}
            placeholder="username"
          />
          <Input
            type="password"
            value={draft.password}
            onChange={(e) => setDraft((d) => ({ ...d, password: e.target.value }))}
            placeholder="password"
          />
        </div>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Plus className="h-3 w-3" />}
          onClick={add}
          disabled={!draft.address || !draft.port}
        >
          Добавить
        </Button>
      </div>
    </>
  )
}

function AntidetectSection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader
        title="Антидетект"
        description="Ротация fingerprint, человеческое поведение и обход капчи"
      />
      <Field
        label={`Интервал ротации: ${get<number>('antidetect_rotate_minutes')} мин`}
        hint="Как часто обновлять device fingerprint"
      >
        <Slider
          min={30}
          max={720}
          step={10}
          value={get<number>('antidetect_rotate_minutes')}
          onChange={(v) => set('antidetect_rotate_minutes', v)}
        />
      </Field>
      <Field label="Профиль устройств" hint="Используемые build.prop шаблоны">
        <Select
          value={get<string>('antidetect_profile')}
          onChange={(v) => set('antidetect_profile', v)}
          options={[
            { value: 'samsung', label: 'Samsung Galaxy' },
            { value: 'pixel', label: 'Google Pixel' },
            { value: 'xiaomi', label: 'Xiaomi' },
            { value: 'mixed', label: 'Смешанный парк' },
          ]}
        />
      </Field>

      <div className="mt-4 rounded-lg border border-[--line-1] bg-[--bg-1] p-4">
        <div className="mb-3 text-sm font-medium text-[--txt-1]">
          Живой ввод (human behavior)
        </div>
        <p className="mb-3 text-xs text-[--txt-3]">
          Каждый тап и свайп идёт через HumanBehaviorEngine: случайный jitter
          позиции, естественная длительность свайпа, кривая Безье для курсора
          и вариативная скорость набора текста. Платформам видно поведение
          живого пользователя, а не бота.
        </p>
        <Field label="Включить живой ввод" hint="Все действия будут идти через human_tap/swipe/type">
          <Switch
            checked={get<boolean>('human_input_enabled')}
            onChange={(v) => set('human_input_enabled', v)}
          />
        </Field>
        <Field label="Поведенческий профиль" hint="Calm — осторожный (ночной), Normal — обычный, Fast — активный">
          <Select
            value={get<string>('human_behavior_profile')}
            onChange={(v) => set('human_behavior_profile', v)}
            options={[
              { value: 'calm', label: 'Calm · спокойный' },
              { value: 'normal', label: 'Normal · обычный' },
              { value: 'fast', label: 'Fast · быстрый' },
            ]}
          />
        </Field>
        <Field
          label="Оверлей курсора в демо"
          hint="Показывать палец/тап на стриме устройства"
        >
          <Switch
            checked={get<boolean>('cursor_overlay')}
            onChange={(v) => set('cursor_overlay', v)}
          />
        </Field>
        <Field
          label="Нативный курсор на устройстве"
          hint="Включает show_touches + pointer_location на Android. Касания видны прямо на телефоне."
        >
          <Switch
            checked={get<boolean>('native_pointer')}
            onChange={(v) => set('native_pointer', v)}
          />
        </Field>
      </div>

      <div className="mt-4 rounded-lg border border-[--line-1] bg-[--bg-1] p-4">
        <div className="mb-3 text-sm font-medium text-[--txt-1]">Обход капчи</div>
        <p className="mb-3 text-xs text-[--txt-3]">
          Используется сервис 2Captcha. Поддерживаются reCAPTCHA v2/v3,
          hCaptcha и image-challenge. Ключ хранится локально.
        </p>
        <Field label="2Captcha API Key" hint="Получите на 2captcha.com/enterpage">
          <Input
            type="password"
            value={get<string>('twocaptcha_api_key')}
            onChange={(e) => set('twocaptcha_api_key', e.target.value)}
            placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          />
        </Field>
      </div>
    </>
  )
}

type MixId = 'smart' | 'cross' | 'stride' | 'interleave' | 'random_offset' | 'wear'

interface MixDef {
  id: MixId
  brand: string
  ru: string
  short: string
  pattern: string[] // three demo lines: pattern across posts
  pros: string[]
  best: string
}

const MIX_DEFS: MixDef[] = [
  {
    id: 'smart',
    brand: 'SmartMix',
    ru: 'Умный микс',
    short:
      'Главная стратегия: ротация по «непохожим» тройкам + защита от свежих фото, которые недавно публиковались. Растягивает датасет в 2–3 раза дольше, чем простая выдача.',
    pattern: ['пост 1: 1, 3, 5', 'пост 2: 2, 4, 6', 'пост 3: 2, 3, 1 (сдвиг)'],
    pros: ['Меньше всего повторов', 'Сам отдаёт приоритет новым фото', 'Без ручной настройки'],
    best: 'Любой средний/крупный датасет (рекомендуется по умолчанию).',
  },
  {
    id: 'cross',
    brand: 'CrossRotate',
    ru: 'Кросс-ротация',
    short:
      'Берёт окно из датасета и катит его по диагонали: каждый пост — другая тройка с другим шагом. То же, что Smart, но без подмены «свежих» фото.',
    pattern: ['пост 1: 1, 3, 5', 'пост 2: 2, 4, 6', 'пост 3: 1, 4, 7'],
    pros: ['Чёткий детерминированный паттерн', 'Хорошо для аналитики', 'Нет случайностей'],
    best: 'Когда нужно предсказуемое расписание контента.',
  },
  {
    id: 'stride',
    brand: 'ZebraStep',
    ru: 'Зебра',
    short:
      'Шагает по датасету через одну позицию, потом сдвигается. Идеально для коллекций, где соседние фото похожи (например, серии с одной локации).',
    pattern: ['пост 1: 1, 3, 5', 'пост 2: 2, 4, 6', 'пост 3: 1, 2, 3'],
    pros: ['Похожие фото не попадают в один пост', 'Простой паттерн'],
    best: 'Серии с похожими соседними кадрами.',
  },
  {
    id: 'interleave',
    brand: 'EvenOdd',
    ru: 'Чёт-нечёт',
    short:
      'Простое чередование: один пост — чётные индексы, следующий — нечётные. Каждый кадр публикуется ровно через раз.',
    pattern: ['пост 1: чётные', 'пост 2: нечётные', 'пост 3: разворот'],
    pros: ['Идеально равномерный износ', 'Самое простое поведение'],
    best: 'Маленькие датасеты, где важно «продержать» парк подольше.',
  },
  {
    id: 'random_offset',
    brand: 'RandomDrift',
    ru: 'Случайный сдвиг',
    short:
      'Каждый раз случайный старт + случайный шаг. Максимум вариативности, но и предсказать порядок нельзя.',
    pattern: ['пост 1: 4, 7, 1', 'пост 2: 9, 2, 5', 'пост 3: 3, 8, 0'],
    pros: ['Никто не угадает паттерн', 'Хорош против сравнений'],
    best: 'Большие датасеты + параноидальные ниши.',
  },
  {
    id: 'wear',
    brand: 'ClassicWear',
    ru: 'Классический износ',
    short:
      'Берёт три самых редко публиковавшихся фото. Без всякой ротации — просто «у кого меньше показов, тот и идёт».',
    pattern: ['пост 1: 3 наименее износ.', 'пост 2: 3 след. наименее износ.', 'пост 3: …'],
    pros: ['Гарантированно равномерный износ', 'Прозрачный'],
    best: 'Маленький датасет (до ~10 фото), редкие публикации.',
  },
]

function ContentSection({ set, get }: SectionProps) {
  const current = get<string>('mixing_strategy') as MixId
  return (
    <>
      <SectionHeader
        title="Контент и датасеты"
        description="Стратегии смешивания фото и публикация из галереи устройства"
      />

      <div className="space-y-3">
        <div className="text-sm font-medium text-[--txt-1]">
          Стратегия смешивания датасета
        </div>
        <p className="text-xs text-[--txt-3]">
          Когда в датасете больше 3 фото, программа решает, какие именно три из них
          поставить в очередной пост. Эти алгоритмы — разные принципы такого
          выбора. Кликните на карточку, чтобы выбрать.
        </p>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {MIX_DEFS.map((m) => {
            const active = m.id === current
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => set('mixing_strategy', m.id)}
                className={cn(
                  'flex flex-col gap-2 rounded-xl border p-3 text-left transition-colors',
                  active
                    ? 'border-[--blue] bg-[--blue]/5'
                    : 'border-[--line-1] bg-[--bg-1] hover:bg-[--bg-2]',
                )}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-[--txt-1]">{m.brand}</div>
                    <div className="text-xs text-[--txt-2]">{m.ru}</div>
                  </div>
                  {active && <Badge variant="info">Выбрано</Badge>}
                  {m.id === 'smart' && !active && (
                    <Badge variant="success">Рекомендуем</Badge>
                  )}
                </div>
                <p className="text-xs text-[--txt-3]">{m.short}</p>
                <div className="rounded-md bg-[--bg-3] p-2 font-mono text-[11px] leading-snug text-[--txt-2]">
                  {m.pattern.map((p, i) => (
                    <div key={i}>{p}</div>
                  ))}
                </div>
                <ul className="space-y-0.5 text-[11px] text-[--txt-2]">
                  {m.pros.map((p, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-[--green]">✓</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
                <div className="text-[11px] text-[--txt-3]">
                  <span className="text-[--txt-2]">Когда подходит:</span> {m.best}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <Field
        label="Публикация из галереи устройства"
        hint="Перед постом медиа кладётся в /sdcard/DCIM/Camera на телефоне аккаунта, и пост берёт его как из обычной галереи. Так платформа видит нативную публикацию."
      >
        <Switch
          checked={get<boolean>('gallery_publish')}
          onChange={(v) => set('gallery_publish', v)}
        />
      </Field>

      <div className="rounded-lg border border-[--line-1] bg-[--bg-1] p-3 text-xs text-[--txt-3]">
        <div className="mb-1 font-medium text-[--txt-2]">Как работает смешивание</div>
        Датасет из N фото → каждый пост берёт ровно 3 кадра. SIPR (Smart Image
        Pool Rotator) ведёт счётчик «износа» по каждому файлу. Стратегия решает,
        какие индексы взять. Чем «умнее» стратегия — тем дольше датасет
        «работает» без повторов одной и той же тройки.
      </div>
    </>
  )
}

function StreamSection({ set, get }: SectionProps) {
  const current = get<string>('stream_preset')
  type Preset = {
    id: 'smooth' | 'balanced' | 'quality'
    title: string
    badge: string
    desc: string
    metrics: { fps: number; w: number; q: number }
  }
  const PRESETS: Preset[] = [
    {
      id: 'smooth',
      title: 'Плавность',
      badge: 'Рекомендуем',
      desc: 'Максимальный FPS, минимальный кадр. Самая низкая задержка — управление телефоном «как в реальности».',
      metrics: { fps: 42, w: 420, q: 60 },
    },
    {
      id: 'balanced',
      title: 'Баланс',
      badge: '',
      desc: 'Средний компромисс между чёткостью и скоростью. Хорошо подходит для обычной работы.',
      metrics: { fps: 30, w: 600, q: 72 },
    },
    {
      id: 'quality',
      title: 'Качество',
      badge: '',
      desc: 'Большой кадр и аккуратный JPEG. FPS ниже, зато текст на экране телефона читается чётко.',
      metrics: { fps: 24, w: 720, q: 80 },
    },
  ]
  return (
    <>
      <SectionHeader
        title="Демонстрация экрана"
        description="Как стримить экраны телефонов: чем меньше задержка — тем «живее» управление."
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {PRESETS.map((p) => {
          const active = p.id === current
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => set('stream_preset', p.id)}
              className={cn(
                'flex flex-col gap-2 rounded-xl border p-4 text-left transition-colors',
                active
                  ? 'border-[--blue] bg-[--blue]/5'
                  : 'border-[--line-1] bg-[--bg-1] hover:bg-[--bg-2]',
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-[--blue]" />
                  <span className="font-semibold text-[--txt-1]">{p.title}</span>
                </div>
                {active ? (
                  <Badge variant="info">Выбрано</Badge>
                ) : p.badge ? (
                  <Badge variant="success">{p.badge}</Badge>
                ) : null}
              </div>
              <p className="text-xs text-[--txt-3]">{p.desc}</p>
              <div className="grid grid-cols-3 gap-2 rounded-md bg-[--bg-3] p-2 text-center text-[11px]">
                <div>
                  <div className="text-[--txt-1] font-semibold">{p.metrics.fps}</div>
                  <div className="text-[--txt-3]">кадров/с</div>
                </div>
                <div>
                  <div className="text-[--txt-1] font-semibold">{p.metrics.w}px</div>
                  <div className="text-[--txt-3]">ширина</div>
                </div>
                <div>
                  <div className="text-[--txt-1] font-semibold">{p.metrics.q}</div>
                  <div className="text-[--txt-3]">качество</div>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      <div className="rounded-lg border border-[--line-1] bg-[--bg-1] p-3 text-xs text-[--txt-3]">
        <div className="mb-1 font-medium text-[--txt-2]">Как это работает</div>
        Картинка экрана собирается на хосте: ADB снимает кадр в RAM, сжимает в
        JPEG и шлёт в окно как непрерывный MJPEG-поток. Чем меньше ширина и
        качество — тем меньше байт нужно отправить и тем быстрее новый кадр
        окажется на экране. Пресет «Плавность» ставит акцент на низкую задержку
        — как у LaiXi или scrcpy.
      </div>
    </>
  )
}

function MetadataSection({ set, get }: SectionProps) {
  return (
    <>
      <SectionHeader title="Метаданные" description="Очистка EXIF/XMP и микро-перцептивные изменения" />
      <Field label="Автоочистка" hint="Очищать каждое фото перед публикацией">
        <Switch
          checked={get<boolean>('metadata_autoclean')}
          onChange={(v) => set('metadata_autoclean', v)}
        />
      </Field>
      <Field
        label="Уровень"
        hint="minimal — только EXIF; medium — EXIF+XMP+LSB; aggressive — + crop/brightness"
      >
        <Select
          value={get<string>('metadata_level')}
          onChange={(v) => set('metadata_level', v)}
          options={[
            { value: 'minimal', label: 'Minimal' },
            { value: 'medium', label: 'Medium' },
            { value: 'aggressive', label: 'Aggressive' },
          ]}
        />
      </Field>
    </>
  )
}

function BackupsSection({ set, get }: SectionProps) {
  const [creating, setCreating] = useState(false)
  const create = async () => {
    setCreating(true)
    try {
      await api.post('/api/settings/backup-now')
      toast.success('Бэкап создан')
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setCreating(false)
    }
  }
  return (
    <>
      <SectionHeader title="Бэкапы" description="Автоматические копии базы данных" />
      <Field label="Автоматические бэкапы" hint="Создавать ежедневно в указанное время">
        <Switch checked={get<boolean>('backup_auto')} onChange={(v) => set('backup_auto', v)} />
      </Field>
      <Field label="Время" hint="HH:MM локального времени">
        <Input
          type="time"
          value={get<string>('backup_time')}
          onChange={(e) => set('backup_time', e.target.value)}
        />
      </Field>
      <Field
        label={`Хранить последних: ${get<number>('backup_keep')}`}
        hint="Старые бэкапы автоматически удаляются"
      >
        <Slider
          min={1}
          max={30}
          step={1}
          value={get<number>('backup_keep')}
          onChange={(v) => set('backup_keep', v)}
        />
      </Field>
      <div>
        <Button
          variant="secondary"
          leftIcon={<Sparkles className="h-4 w-4" />}
          onClick={create}
          loading={creating}
        >
          Создать сейчас
        </Button>
      </div>
    </>
  )
}

function GuideSection() {
  const setShowOnboarding = useAppStore((s) => s.setShowOnboarding)
  const sections: Array<{ title: string; body: string }> = [
    {
      title: '1. Подключение телефона (Android)',
      body:
        'Включите режим разработчика: Настройки → О телефоне → 7 раз тапните по «Номер сборки». Затем Настройки → Система → Для разработчиков → «Отладка по USB». Подключите кабель и подтвердите запрос «Разрешить отладку по USB» на экране телефона.',
    },
    {
      title: '2. Подключение телефона (iOS, без джейлбрейка)',
      body:
        'Подключите iPhone, нажмите «Доверять». Chimera установит libimobiledevice автоматически. Для управления нажатиями используется WebDriverAgent — установится через Xcode и Apple ID. Доступны: стрим экрана, скриншоты, запуск приложений, наблюдение сети.',
    },
    {
      title: '3. Подключение телефона (iOS, джейлбрейк)',
      body:
        'palera1n (15.0–16.6.1), Dopamine (16.7+, A12+) или checkra1n (iOS 14). Создайте бэкап, отключите «Найти iPhone». Установите твики: OpenSSH, AppSync Unified, Liberty Lite, Frida server. ОБЯЗАТЕЛЬНО смените дефолтный пароль "alpine". В Sileo → пропишите SSH-доступ в Настройках Chimera.',
    },
    {
      title: '4. Антидетект и прокси',
      body:
        'Настройки → Антидетект: подмена IDFV/IDFA, MAC, локали, часового пояса. Настройки → Прокси: HTTP/SOCKS5 с проверкой работоспособности. Каждому телефону можно привязать свой прокси. Проверка IP — ПКМ на карточке телефона → «Обновить IP».',
    },
    {
      title: '5. Аккаунты и привязка',
      body:
        'Раздел «Аккаунты» — визуальная карта с привязкой к телефонам и платформам. Кнопка «Добавить аккаунт» — выбор телефона, платформы (Instagram/TikTok/YouTube/Twitter/Facebook/Threads), логин/пароль. Цветные нити показывают привязку.',
    },
    {
      title: '6. Датасеты и автопостинг',
      body:
        'Раздел «Датасеты»: загружайте папки с фото, Chimera чистит EXIF и метаданные. В «Планировщике» создавайте автопостинг с диапазоном дней и часов — посты будут случайно распределены в окне.',
    },
    {
      title: '7. Прогрев аккаунтов',
      body:
        'Настройки → Прогрев: длительность, веса действий (скролл/просмотр профилей/лайки/подписки). Запуск — кнопка «Прогреть» на карточке телефона. Поведение имитируется HumanBehaviorEngine с естественными траекториями.',
    },
    {
      title: '8. Сообщения и приветствия',
      body:
        '«Сообщения» → «Мужские контакты»: пул отфильтрованных мужских пользователей из комментариев и ЛС. Можно отправлять приветствия группой. Вкладка «Платформы» показывает метрики по аккаунтам (комментарии/ответы/ЛС/последняя активность).',
    },
    {
      title: '9. Стрим экрана и задержка',
      body:
        'Настройки → Демонстрация экрана: 4 пресета (Smooth = минимальная задержка). При двойном клике на телефоне он становится мастером — ввод дублируется на остальные. ПКМ → «Открыть на весь экран» для управления одним телефоном.',
    },
    {
      title: '10. Telegram-бот и авторизация',
      body:
        'Авторизация выдаётся одноразово через Telegram-бот: при первом запуске вы получаете 6-значный код, отправляете его боту командой /start <код>. После каждого обновления приложения авторизация запрашивается повторно. FAQ и состояние телефонов также доступны через бота.',
    },
  ]
  return (
    <>
      <SectionHeader
        title="Методичка"
        description="Полное руководство по настройке и использованию Chimera. При первом запуске мы провели вас через визард — здесь та же информация, доступная в любой момент."
      />
      <div className="rounded-xl border border-[--blue]/30 bg-[--blue]/5 p-4">
        <div className="mb-2 text-sm font-semibold text-[--txt-1]">
          Запустить визард настройки заново
        </div>
        <div className="mb-3 text-xs text-[--txt-3]">
          Если хотите ещё раз пройти пошаговую настройку — нажмите кнопку.
          Авторизация и данные останутся.
        </div>
        <Button
          variant="primary"
          size="sm"
          leftIcon={<HelpCircle className="h-4 w-4" />}
          onClick={() => setShowOnboarding(true)}
        >
          Открыть визард
        </Button>
      </div>
      <div className="space-y-2">
        {sections.map((s, i) => (
          <details
            key={i}
            className="group rounded-md border border-[--line-1] bg-[--bg-2] p-3 open:bg-[--bg-1]"
          >
            <summary className="cursor-pointer text-sm font-semibold text-[--txt-1] marker:text-[--txt-3]">
              {s.title}
            </summary>
            <div className="mt-2 whitespace-pre-line text-xs text-[--txt-2]">
              {s.body}
            </div>
          </details>
        ))}
      </div>
    </>
  )
}

function AboutSection() {
  const [info, setInfo] = useState<{
    version?: string
    data_dir?: string
    pid?: number
    uptime_seconds?: number
  }>({})

  useEffect(() => {
    api
      .get('/api/dashboard/metrics')
      .then((r) => setInfo(r.data as typeof info))
      .catch(() => undefined)
  }, [])

  return (
    <>
      <SectionHeader title="О программе" />
      <div className="flex items-center gap-4 rounded-xl border border-[--line-1] bg-[--bg-1] p-5">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[--blue]/10 text-[--blue]">
          <Sparkles className="h-8 w-8" />
        </div>
        <div>
          <div className="text-lg font-semibold text-[--txt-1]">Chimera</div>
          <div className="text-sm text-[--txt-3]">Версия {info.version ?? 'dev'}</div>
        </div>
      </div>
      <Field label="Путь к данным">
        <Input value={info.data_dir ?? ''} readOnly />
      </Field>
      <div className="text-xs text-[--txt-3]">
        © 2026 Chimera. Все права защищены.
      </div>
    </>
  )
}
