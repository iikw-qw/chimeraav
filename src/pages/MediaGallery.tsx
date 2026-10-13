import { useCallback, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Image, Trash2, Upload, Wand2 } from 'lucide-react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { toast } from '../hooks/useToast'

interface MediaItem {
  id: string
  filename: string
  file_path: string
  file_type: string
  file_size: number | null
  width: number | null
  height: number | null
  tags: string[]
  quality_score: number | null
  is_unique: boolean
  created_at: string
}

async function fetchMedia(fileType: string | null, minQuality: number | null): Promise<MediaItem[]> {
  const params: Record<string, string> = {}
  if (fileType) params.file_type = fileType
  if (minQuality !== null) params.min_quality = String(minQuality)
  const { data } = await api.get<MediaItem[]>('/api/media', { params })
  return data
}

export function MediaGallery() {
  const qc = useQueryClient()
  const [fileType, setFileType] = useState<string | null>(null)
  const [minQuality, setMinQuality] = useState<number | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dragging, setDragging] = useState(false)

  const { data: items = [] } = useQuery({
    queryKey: ['media', fileType, minQuality],
    queryFn: () => fetchMedia(fileType, minQuality),
    refetchInterval: 10_000,
  })

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/api/media/upload', form)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['media'] })
      toast.success('Файл загружен')
    },
    onError: (err: Error) => toast.danger(err.message),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/media/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['media'] })
      toast.success('Удалено')
    },
  })

  const batchDeleteMut = useMutation({
    mutationFn: (ids: string[]) => api.post('/api/media/batch-delete', ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['media'] })
      setSelected(new Set())
      toast.success('Удалено')
    },
  })

  const uniqueizeMut = useMutation({
    mutationFn: (id: string) => api.post(`/api/media/${id}/uniqueize`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['media'] })
      toast.success('Уникализация завершена')
    },
    onError: (err: Error) => toast.danger(err.message),
  })

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return
      Array.from(files).forEach((f) => uploadMut.mutate(f))
    },
    [uploadMut],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles],
  )

  const toggleSelect = (id: string) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const formatSize = (bytes: number | null) => {
    if (!bytes) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full overflow-y-auto p-5 space-y-4"
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[--text-1] text-lg font-semibold">
          <Image size={18} />
          Медиа-галерея
          <span className="text-xs font-normal text-[--text-3]">({items.length})</span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={fileType ?? ''}
            onChange={(e) => setFileType(e.target.value || null)}
            className="rounded-md border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]"
          >
            <option value="">Все типы</option>
            <option value="photo">Фото</option>
            <option value="video">Видео</option>
          </select>
          <select
            value={minQuality === null ? '' : String(minQuality)}
            onChange={(e) => setMinQuality(e.target.value ? Number(e.target.value) : null)}
            className="rounded-md border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]"
          >
            <option value="">Любое качество</option>
            <option value="80">80+</option>
            <option value="60">60+</option>
            <option value="40">40+</option>
          </select>
          {selected.size > 0 && (
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<Trash2 className="h-3.5 w-3.5" />}
              onClick={() => batchDeleteMut.mutate([...selected])}
            >
              Удалить ({selected.size})
            </Button>
          )}
          <label className="cursor-pointer inline-flex items-center justify-center gap-2 rounded-lg font-medium h-8 px-3 text-xs bg-[--blue] text-white shadow-[0_2px_12px_rgba(91,155,255,0.3)] hover:shadow-[0_4px_20px_rgba(91,155,255,0.4)] hover:brightness-110 active:scale-[0.98] transition-all duration-150">
            <input
              type="file"
              multiple
              accept="image/*,video/*"
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <Upload className="h-3.5 w-3.5" />
            Загрузить
          </label>
        </div>
      </header>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={
          'grid grid-cols-4 gap-3 min-h-[200px] rounded-lg border-2 border-dashed p-3 transition-colors ' +
          (dragging
            ? 'border-[--blue] bg-[--blue-glow]'
            : 'border-transparent')
        }
      >
        {items.length === 0 && (
          <div className="col-span-4 flex flex-col items-center justify-center gap-2 py-12 text-[--text-3]">
            <Upload size={32} />
            <span className="text-sm">Перетащите файлы сюда или нажмите «Загрузить»</span>
          </div>
        )}
        {items.map((item) => (
          <div
            key={item.id}
            onClick={() => toggleSelect(item.id)}
            className={
              'group relative cursor-pointer rounded-lg border bg-[--bg-2] p-2 transition-colors ' +
              (selected.has(item.id)
                ? 'border-[--blue] ring-1 ring-[--blue]'
                : 'border-[--line-1] hover:border-[--line-3]')
            }
          >
            <div className="flex h-32 items-center justify-center rounded bg-[--bg-3] text-[--text-3]">
              {item.file_type === 'photo' ? (
                <Image size={36} />
              ) : (
                <span className="text-xs uppercase">{item.file_type}</span>
              )}
            </div>
            <div className="mt-2 space-y-1">
              <div className="truncate text-xs text-[--text-1]">{item.filename}</div>
              <div className="flex items-center gap-2 text-[10px] text-[--text-3]">
                <span>{formatSize(item.file_size)}</span>
                {item.width && item.height && (
                  <span>
                    {item.width}×{item.height}
                  </span>
                )}
                {item.quality_score !== null && (
                  <span
                    className={
                      item.quality_score >= 70
                        ? 'text-[--green]'
                        : item.quality_score >= 40
                          ? 'text-[--yellow]'
                          : 'text-[--red]'
                    }
                  >
                    Q:{item.quality_score.toFixed(0)}
                  </span>
                )}
                {item.is_unique && <span className="text-[--green]">U</span>}
              </div>
            </div>
            <div className="absolute right-1 top-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  uniqueizeMut.mutate(item.id)
                }}
                className="rounded bg-[--bg-1]/80 p-1 text-[--text-2] hover:text-[--blue]"
                title="Уникализировать"
              >
                <Wand2 size={14} />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  deleteMut.mutate(item.id)
                }}
                className="rounded bg-[--bg-1]/80 p-1 text-[--text-2] hover:text-[--red]"
                title="Удалить"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
