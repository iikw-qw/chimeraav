import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, FileText, Plus, Trash2, Upload, X } from 'lucide-react'
import { Badge, Button, Input } from '../components/ui'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'

interface Caption {
  id: string
  text: string
  category: string
  platform: string
  language: string
}

const PLATFORMS = ['instagram', 'tiktok', 'facebook', 'twitter', 'linkedin', 'vk', 'reddit'] as const
const CATEGORIES = ['general', 'lifestyle', 'mood', 'motivation', 'travel', 'food', 'fitness'] as const

function platformColor(p: string): string {
  const map: Record<string, string> = {
    instagram: '#E1306C', tiktok: '#25F4EE', facebook: '#1877F2',
    twitter: '#1DA1F2', linkedin: '#0A66C2', vk: '#4C75A3', reddit: '#FF4500',
  }
  return map[p] ?? '#7C8DA8'
}

export function Captions() {
  const [captions, setCaptions] = useState<Caption[]>([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [filterPlatform, setFilterPlatform] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [search, setSearch] = useState('')

  const load = async () => {
    try {
      const { data } = await api.get<Caption[]>('/api/captions')
      setCaptions(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    return captions.filter((c) => {
      if (filterPlatform && c.platform !== filterPlatform) return false
      if (filterCategory && c.category !== filterCategory) return false
      if (search && !c.text.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [captions, filterPlatform, filterCategory, search])

  const remove = async (id: string) => {
    await api.delete(`/api/captions/${id}`)
    setCaptions((prev) => prev.filter((c) => c.id !== id))
  }

  const handleImport = async () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.csv'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const form = new FormData()
      form.append('file', file)
      try {
        const { data } = await api.post('/api/captions/import', form)
        toast.success(`Импортировано: ${data.imported} подписей`)
        load()
      } catch (err) {
        toast.danger((err as Error).message, 'Импорт')
      }
    }
    input.click()
  }

  const handleExport = () => {
    window.open(`${api.defaults.baseURL ?? ''}/api/captions/export`, '_blank')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[--line-1] px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-[--txt-1]">Подписи</div>
          <div className="text-xs text-[--txt-3]">
            Библиотека подписей для автопостинга — {captions.length} шт.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" leftIcon={<Upload className="h-3.5 w-3.5" />} onClick={handleImport}>
            Импорт CSV
          </Button>
          <Button size="sm" variant="ghost" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={handleExport}>
            Экспорт
          </Button>
          <Button size="sm" variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>
            Добавить
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3 border-b border-[--line-1] bg-[--bg-2] px-6 py-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск..."
          className="max-w-xs"
        />
        <select
          value={filterPlatform}
          onChange={(e) => setFilterPlatform(e.target.value)}
          className="h-8 rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none"
        >
          <option value="">Все платформы</option>
          {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="h-8 rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none"
        >
          <option value="">Все категории</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="text-xs text-[--txt-3]">{filtered.length} из {captions.length}</span>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="text-center text-sm text-[--txt-3]">Загрузка...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center text-sm text-[--txt-3]">
            Нет подписей. Добавьте первую или импортируйте CSV.
          </div>
        ) : (
          <div className="grid gap-2">
            {filtered.map((c) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="group flex items-center gap-3 rounded-lg border border-[--line-1] bg-[--bg-1] px-4 py-2.5"
              >
                <FileText className="h-4 w-4 shrink-0 text-[--txt-3]" />
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm text-[--txt-1]">{c.text}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Badge
                      variant="info"
                      className="text-[10px]"
                      style={{ borderColor: platformColor(c.platform), color: platformColor(c.platform) } as React.CSSProperties}
                    >
                      {c.platform}
                    </Badge>
                    <span className="text-[10px] text-[--txt-3]">{c.category}</span>
                    <span className="text-[10px] text-[--txt-3]">{c.language}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove(c.id)}
                  className="rounded p-1 text-[--txt-3] opacity-0 transition-opacity hover:bg-[--bg-3] hover:text-[--red] group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      <AnimatePresence>
        {addOpen && <AddCaptionModal onClose={() => { setAddOpen(false); load() }} />}
      </AnimatePresence>
    </div>
  )
}

function AddCaptionModal({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState('')
  const [category, setCategory] = useState('general')
  const [platform, setPlatform] = useState('instagram')
  const [language, setLanguage] = useState('en')
  const [busy, setBusy] = useState(false)

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    try {
      await api.post('/api/captions', { text: text.trim(), category, platform, language })
      toast.success('Подпись добавлена')
      onClose()
    } catch (err) {
      toast.danger((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
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
        <div className="flex items-center justify-between border-b border-[--line-1] px-5 py-3">
          <div className="text-sm font-semibold text-[--txt-1]">Новая подпись</div>
          <button type="button" onClick={onClose} className="rounded p-1 text-[--txt-2] hover:bg-[--bg-3]">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3 p-5">
          <label className="block text-xs text-[--txt-2]">
            Текст подписи
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="mt-1 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-3 py-2 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
              rows={3}
              autoFocus
            />
          </label>
          <div className="grid grid-cols-3 gap-3">
            <label className="block text-xs text-[--txt-2]">
              Категория
              <select value={category} onChange={(e) => setCategory(e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none">
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="block text-xs text-[--txt-2]">
              Платформа
              <select value={platform} onChange={(e) => setPlatform(e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none">
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label className="block text-xs text-[--txt-2]">
              Язык
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="mt-1 h-8 w-full rounded-md border border-[--line-1] bg-[--bg-3] px-2 text-xs text-[--txt-1] outline-none">
                <option value="en">English</option>
                <option value="ru">Русский</option>
                <option value="es">Español</option>
              </select>
            </label>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-[--line-1] bg-[--bg-2] px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
          <Button type="submit" variant="primary" disabled={busy || !text.trim()}>
            {busy ? 'Сохраняем...' : 'Добавить'}
          </Button>
        </div>
      </motion.form>
    </motion.div>
  )
}
