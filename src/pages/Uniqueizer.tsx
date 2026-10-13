import { useState } from 'react'
import { motion } from 'framer-motion'
import { ImagePlus, Sparkles } from 'lucide-react'
import { Button, Input } from '../components/ui'
import { api } from '../api/client'
import { toast } from '../hooks/useToast'

interface UniqueResult {
  hash_before: string
  hash_after: string
  changes: string[]
  output: string
}

export function Uniqueizer() {
  const [filePath, setFilePath] = useState('')
  const [type, setType] = useState<'photo' | 'video'>('photo')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<UniqueResult | null>(null)

  const run = async () => {
    if (!filePath.trim()) return
    setBusy(true)
    setResult(null)
    try {
      const { data } = await api.post<UniqueResult>('/api/content/uniqueize', {
        file_path: filePath.trim(),
        type,
      })
      setResult(data)
      toast.success('Контент уникализирован')
    } catch (err) {
      toast.danger((err as Error).message, 'Уникализация')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[--line-1] px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-[--txt-1]">Уникализатор</div>
          <div className="text-xs text-[--txt-3]">
            Сделайте фото/видео уникальным — невидимые модификации обходят детект дубликатов.
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-lg space-y-4">
          <label className="block text-xs text-[--txt-2]">
            Путь к файлу
            <Input
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="C:\photos\image.jpg"
            />
          </label>

          <div className="flex items-center gap-3">
            <label className="block text-xs text-[--txt-2]">
              Тип
              <div className="mt-1 flex gap-2">
                {(['photo', 'video'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setType(t)}
                    className={
                      'rounded-md border-2 px-4 py-1.5 text-xs font-medium transition-all ' +
                      (type === t
                        ? 'border-[--blue] bg-[--blue-glow] text-[--blue]'
                        : 'border-[--line-1] text-[--txt-2] hover:text-[--txt-1]')
                    }
                  >
                    {t === 'photo' ? 'Фото' : 'Видео'}
                  </button>
                ))}
              </div>
            </label>
          </div>

          <Button
            variant="primary"
            onClick={run}
            disabled={busy || !filePath.trim()}
            leftIcon={<Sparkles className="h-4 w-4" />}
          >
            {busy ? 'Обработка...' : 'Уникализировать'}
          </Button>

          {result && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-3 rounded-xl border border-[--line-2] bg-[--bg-2] p-4"
            >
              <div className="text-sm font-semibold text-[--txt-1]">Результат</div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-[--line-1] bg-[--bg-3] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-[--txt-3]">До</div>
                  <div className="mt-1 font-mono text-xs text-[--txt-2]">{result.hash_before}</div>
                </div>
                <div className="rounded-lg border border-[--line-1] bg-[--bg-3] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-[--txt-3]">После</div>
                  <div className="mt-1 font-mono text-xs text-[--blue]">{result.hash_after}</div>
                </div>
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-wider text-[--txt-3]">Изменения</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {result.changes.map((c, i) => (
                    <span
                      key={i}
                      className="rounded-md bg-[--bg-3] px-2 py-0.5 text-[10px] text-[--txt-2]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </div>

              <div className="text-xs text-[--txt-3]">
                Выход: <span className="font-mono text-[--txt-2]">{result.output}</span>
              </div>
            </motion.div>
          )}

          <div className="rounded-lg border border-[--line-1] bg-[--bg-2] p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-[--txt-2]">
              <ImagePlus className="h-4 w-4" />
              Что делает уникализатор?
            </div>
            <ul className="space-y-1 text-[11px] text-[--txt-3]">
              <li>Лёгкий кроп (1-3% с каждой стороны)</li>
              <li>Яркость и контраст (±3-8%)</li>
              <li>Насыщенность (±5%)</li>
              <li>Микро-поворот (±1.5°)</li>
              <li>LSB модификация пикселей (невидимо)</li>
              <li>Удаление EXIF метаданных</li>
              <li>Случайное JPEG качество (85-95)</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
