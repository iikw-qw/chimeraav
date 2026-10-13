import { useState } from 'react'
import { motion } from 'framer-motion'
import { Crosshair, Monitor, MousePointerClick, Smartphone } from 'lucide-react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { useDevices } from '../hooks/useDevices'
import { toast } from '../hooks/useToast'

interface ClickVector {
  x: number | null
  y: number | null
  area_w: number
  area_h: number
}

type Target = 'phone' | 'pc'

export function AutoClicker() {
  const { data: devices } = useDevices()
  const [target, setTarget] = useState<Target>('pc')
  const [deviceId, setDeviceId] = useState('')
  const [mode, setMode] = useState<'photo' | 'sequential'>('photo')
  const [buttonText, setButtonText] = useState('')
  const [count, setCount] = useState(10)
  const [delayMin, setDelayMin] = useState(8)
  const [delayMax, setDelayMax] = useState(13)
  const [waitText, setWaitText] = useState('')
  const [captchaKey, setCaptchaKey] = useState('')
  const [vectors, setVectors] = useState<ClickVector[]>([])
  const [running, setRunning] = useState(false)
  const [pcX, setPcX] = useState<number | null>(null)
  const [pcY, setPcY] = useState<number | null>(null)
  const [pcW, setPcW] = useState(15)
  const [pcH, setPcH] = useState(10)
  const [capturing, setCapturing] = useState(false)

  const addVector = () =>
    setVectors((v) => [...v, { x: null, y: null, area_w: 20, area_h: 10 }])
  const removeVector = (i: number) =>
    setVectors((v) => v.filter((_, idx) => idx !== i))

  const capturePosition = async () => {
    setCapturing(true)
    toast.success('Наведите мышь на нужную позицию... (3 сек)')
    await new Promise((r) => setTimeout(r, 3000))
    try {
      const { data } = await api.get<{ x: number; y: number }>('/api/autoclicker/mouse-position')
      setPcX(data.x)
      setPcY(data.y)
      toast.success(`Позиция: ${data.x}, ${data.y}`)
    } catch (err) {
      toast.danger((err as Error).message)
    }
    setCapturing(false)
  }

  const handleStart = async () => {
    if (target === 'phone' && (!deviceId || !buttonText)) {
      toast.warning('Выберите устройство и текст кнопки')
      return
    }
    if (target === 'pc' && (pcX === null || pcY === null)) {
      toast.warning('Укажите координаты X и Y')
      return
    }
    setRunning(true)
    try {
      const payload =
        target === 'pc'
          ? {
              target: 'pc',
              count,
              mode,
              x: pcX,
              y: pcY,
              area_w: pcW,
              area_h: pcH,
              delay_min: delayMin,
              delay_max: delayMax,
            }
          : {
              target: 'phone',
              device_id: deviceId,
              button_text: buttonText,
              count,
              mode,
              delay_min: delayMin,
              delay_max: delayMax,
              wait_for_completion: waitText || null,
              vectors: vectors.filter((v) => v.x != null && v.y != null),
              captcha_api_key: captchaKey,
            }
      const { data } = await api.post('/api/autoclicker/start', payload)
      toast.success(data.message)
    } catch (err) {
      toast.danger((err as Error).message)
      setRunning(false)
    }
  }

  const handleStop = async () => {
    const id = target === 'pc' ? '__pc__' : deviceId
    try {
      await api.post('/api/autoclicker/stop', null, { params: { device_id: id } })
      toast.success('AutoClicker остановлен')
    } catch (err) {
      toast.danger((err as Error).message)
    }
    setRunning(false)
  }

  const androidDevices = (devices ?? []).filter((d) => d.platform === 'android')
  const inputCls =
    'mt-1 block w-full rounded-md border border-[--line-1] bg-[--bg-2] px-3 py-2 text-sm text-[--text-1]'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full overflow-y-auto p-5 space-y-5"
    >
      <div className="flex items-center gap-2 text-[--text-1] text-lg font-semibold">
        <MousePointerClick size={18} />
        Автокликер
      </div>

      <div className="flex gap-3 mb-2">
        {([
          { key: 'pc', label: 'На компьютере', Icon: Monitor },
          { key: 'phone', label: 'На телефоне', Icon: Smartphone },
        ] as const).map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTarget(key)}
            className={
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors ' +
              (target === key
                ? 'border-[--blue] bg-[--blue-glow] text-[--text-1]'
                : 'border-[--line-1] bg-[--bg-2] text-[--text-3] hover:text-[--text-1]')
            }
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4 max-w-3xl">
        <div className="space-y-3">
          {target === 'phone' && (
            <label className="block text-xs text-[--text-2]">
              Устройство
              <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)} className={inputCls}>
                <option value="">Выберите...</option>
                {androidDevices.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
          )}

          {target === 'pc' && (
            <>
              <div className="flex items-end gap-2">
                <label className="block text-xs text-[--text-2] flex-1">
                  X
                  <input type="number" value={pcX ?? ''} onChange={(e) => setPcX(e.target.value ? Number(e.target.value) : null)} placeholder="X" className={inputCls} />
                </label>
                <label className="block text-xs text-[--text-2] flex-1">
                  Y
                  <input type="number" value={pcY ?? ''} onChange={(e) => setPcY(e.target.value ? Number(e.target.value) : null)} placeholder="Y" className={inputCls} />
                </label>
                <Button size="sm" variant="secondary" onClick={capturePosition} disabled={capturing} leftIcon={<Crosshair className="h-3.5 w-3.5" />}>
                  {capturing ? 'Ждите...' : 'Указать'}
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="block text-xs text-[--text-2]">
                  Разброс W
                  <input type="number" value={pcW} onChange={(e) => setPcW(Number(e.target.value))} min={0} className={inputCls} />
                </label>
                <label className="block text-xs text-[--text-2]">
                  Разброс H
                  <input type="number" value={pcH} onChange={(e) => setPcH(Number(e.target.value))} min={0} className={inputCls} />
                </label>
              </div>
            </>
          )}

          <label className="block text-xs text-[--text-2]">
            Режим
            <div className="mt-1 flex gap-3">
              {(['photo', 'sequential'] as const).map((m) => (
                <label key={m} className="flex items-center gap-1.5 text-sm text-[--text-1]">
                  <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
                  {m === 'photo' ? 'Фото (пакетный)' : 'Последовательный'}
                </label>
              ))}
            </div>
          </label>

          {target === 'phone' && (
            <label className="block text-xs text-[--text-2]">
              Текст кнопки
              <input type="text" value={buttonText} onChange={(e) => setButtonText(e.target.value)} placeholder="Like, Follow, Subscribe..." className={inputCls} />
            </label>
          )}

          <label className="block text-xs text-[--text-2]">
            Количество кликов
            <input type="number" value={count} onChange={(e) => setCount(Number(e.target.value))} min={1} max={10000} className={inputCls} />
          </label>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-xs text-[--text-2]">
              Задержка мин (сек)
              <input type="number" value={delayMin} onChange={(e) => setDelayMin(Number(e.target.value))} min={0.5} step={0.5} className={inputCls} />
            </label>
            <label className="block text-xs text-[--text-2]">
              Задержка макс (сек)
              <input type="number" value={delayMax} onChange={(e) => setDelayMax(Number(e.target.value))} min={1} step={0.5} className={inputCls} />
            </label>
          </div>

          {target === 'phone' && mode === 'sequential' && (
            <label className="block text-xs text-[--text-2]">
              Текст завершения
              <input type="text" value={waitText} onChange={(e) => setWaitText(e.target.value)} placeholder="Done, Ready..." className={inputCls} />
            </label>
          )}

          {target === 'phone' && (
            <>
              <label className="block text-xs text-[--text-2]">
                2Captcha API ключ
                <input type="text" value={captchaKey} onChange={(e) => setCaptchaKey(e.target.value)} placeholder="Необязательно" className={inputCls} />
              </label>

              <div className="text-xs text-[--text-2]">
                Векторы нажатия ({vectors.length})
                <button type="button" onClick={addVector} className="ml-2 text-[--blue] hover:underline">+ Добавить</button>
              </div>
              {vectors.map((v, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input type="number" placeholder="x" value={v.x ?? ''} onChange={(e) => { const copy = [...vectors]; copy[i] = { ...copy[i], x: e.target.value ? Number(e.target.value) : null }; setVectors(copy) }} className="w-16 rounded border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]" />
                  <input type="number" placeholder="y" value={v.y ?? ''} onChange={(e) => { const copy = [...vectors]; copy[i] = { ...copy[i], y: e.target.value ? Number(e.target.value) : null }; setVectors(copy) }} className="w-16 rounded border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]" />
                  <input type="number" placeholder="w" value={v.area_w} onChange={(e) => { const copy = [...vectors]; copy[i] = { ...copy[i], area_w: Number(e.target.value) }; setVectors(copy) }} className="w-14 rounded border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]" />
                  <input type="number" placeholder="h" value={v.area_h} onChange={(e) => { const copy = [...vectors]; copy[i] = { ...copy[i], area_h: Number(e.target.value) }; setVectors(copy) }} className="w-14 rounded border border-[--line-1] bg-[--bg-2] px-2 py-1 text-xs text-[--text-1]" />
                  <button type="button" onClick={() => removeVector(i)} className="text-[--red] text-xs">x</button>
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        {!running ? (
          <Button variant="primary" onClick={handleStart}>
            Запустить
          </Button>
        ) : (
          <Button variant="ghost" onClick={handleStop}>
            Остановить
          </Button>
        )}
      </div>
    </motion.div>
  )
}
