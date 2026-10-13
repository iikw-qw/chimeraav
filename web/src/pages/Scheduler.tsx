/**
 * Планировщик: календарь, планы, таймлайн.
 * Зависит от: api/client
 */

import { useEffect, useState } from 'react'
import { Calendar as CalendarIcon, Plus, X, Play, Pause, Trash2, Clock, Edit2 } from 'lucide-react'
import { format, addDays, startOfMonth, endOfMonth, eachDayOfInterval, isToday, isSameDay } from 'date-fns'
import { ru } from 'date-fns/locale'
import api from '../api/client'
import toast from 'react-hot-toast'

interface Plan {
  id: string
  name: string
  accounts: string[]
  dataset_id?: string
  frequency?: string
  posts_per_day: number
  start_date?: string
  end_date?: string
  caption_style?: string
  status: string
  last_run_at?: string
  created_at: string
}

export default function Scheduler() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [datasets, setDatasets] = useState<any[]>([])
  const [accounts, setAccounts] = useState<any[]>([])
  const [view, setView] = useState<'calendar' | 'list' | 'timeline'>('list')
  const [showModal, setShowModal] = useState(false)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [form, setForm] = useState({
    name: '', accounts: [] as string[], dataset_id: '', frequency: 'daily',
    posts_per_day: 1, start_date: '', end_date: '', caption_style: 'casual',
  })

  useEffect(() => {
    loadPlans()
    loadDatasets()
    loadAccounts()
  }, [])

  const loadPlans = async () => {
    try {
      const { data } = await api.get('/scheduler')
      setPlans(data)
    } catch { /* ignore */ }
  }

  const loadDatasets = async () => {
    try {
      const { data } = await api.get('/posts/datasets/list')
      setDatasets(data)
    } catch { /* ignore */ }
  }

  const loadAccounts = async () => {
    try {
      const { data } = await api.get('/accounts')
      setAccounts(data)
    } catch { /* ignore */ }
  }

  const createPlan = async () => {
    try {
      await api.post('/scheduler', form)
      setShowModal(false)
      setForm({ name: '', accounts: [], dataset_id: '', frequency: 'daily', posts_per_day: 1, start_date: '', end_date: '', caption_style: 'casual' })
      loadPlans()
      toast.success('План создан')
    } catch {
      toast.error('Ошибка создания плана')
    }
  }

  const togglePlan = async (plan: Plan) => {
    const newStatus = plan.status === 'active' ? 'paused' : 'active'
    try {
      await api.put(`/scheduler/${plan.id}`, { status: newStatus })
      loadPlans()
      toast.success(`План ${newStatus === 'active' ? 'активирован' : 'приостановлен'}`)
    } catch {
      toast.error('Ошибка')
    }
  }

  const deletePlan = async (id: string) => {
    if (!confirm('Удалить план?')) return
    try {
      await api.delete(`/scheduler/${id}`)
      loadPlans()
      toast.success('План удалён')
    } catch {
      toast.error('Ошибка удаления')
    }
  }

  const toggleAccount = (accId: string) => {
    setForm((f) => ({
      ...f,
      accounts: f.accounts.includes(accId) ? f.accounts.filter((a) => a !== accId) : [...f.accounts, accId],
    }))
  }

  const monthDays = eachDayOfInterval({ start: startOfMonth(currentDate), end: endOfMonth(currentDate) })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Планировщик</h1>
        <div className="flex gap-2">
          {(['list', 'calendar', 'timeline'] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`px-3 py-1.5 rounded-lg text-sm font-medium ${view === v ? 'bg-chimera-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}>
              {v === 'list' ? 'Список' : v === 'calendar' ? 'Календарь' : 'Таймлайн'}
            </button>
          ))}
          <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> Добавить план
          </button>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-lg shadow-xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Новый план</h3>
              <button onClick={() => setShowModal(false)}><X size={20} className="text-gray-500" /></button>
            </div>
            <div className="space-y-3">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" placeholder="Название плана" />
              <select value={form.dataset_id} onChange={(e) => setForm({ ...form, dataset_id: e.target.value })} className="input-field">
                <option value="">Выберите датасет</option>
                {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <div className="grid grid-cols-2 gap-3">
                <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input-field" />
                <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input-field" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <select value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} className="input-field">
                  <option value="daily">Ежедневно</option>
                  <option value="weekdays">Будни</option>
                  <option value="custom">Выбранные дни</option>
                </select>
                <input type="number" value={form.posts_per_day} onChange={(e) => setForm({ ...form, posts_per_day: Number(e.target.value) })} className="input-field" min={1} max={20} placeholder="Постов/день" />
              </div>
              <select value={form.caption_style} onChange={(e) => setForm({ ...form, caption_style: e.target.value })} className="input-field">
                <option value="casual">Casual</option>
                <option value="professional">Professional</option>
                <option value="funny">Funny</option>
                <option value="storytelling">Storytelling</option>
              </select>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Аккаунты</label>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {accounts.map((a: any) => (
                    <label key={a.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded cursor-pointer">
                      <input type="checkbox" checked={form.accounts.includes(a.id)} onChange={() => toggleAccount(a.id)} className="rounded" />
                      <span className="text-sm text-gray-700 dark:text-gray-300">{a.username} ({a.platform})</span>
                    </label>
                  ))}
                </div>
              </div>
              <button onClick={createPlan} className="btn-primary w-full">Создать план</button>
            </div>
          </div>
        </div>
      )}

      {/* Views */}
      {view === 'list' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {plans.map((plan) => (
            <div key={plan.id} className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 dark:text-white">{plan.name}</h3>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  plan.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400' :
                  plan.status === 'paused' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400' :
                  'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                }`}>{plan.status}</span>
              </div>
              <div className="text-sm text-gray-500 space-y-1 mb-4">
                <p>{plan.posts_per_day} постов/день • {plan.frequency}</p>
                {plan.start_date && <p>{plan.start_date} — {plan.end_date || '...'}</p>}
                <p>{plan.accounts.length} аккаунтов</p>
                {plan.last_run_at && <p className="text-xs">Последний запуск: {new Date(plan.last_run_at).toLocaleString()}</p>}
              </div>
              <div className="flex gap-2">
                <button onClick={() => togglePlan(plan)} className="btn-secondary flex items-center gap-1 text-sm">
                  {plan.status === 'active' ? <><Pause size={14} /> Пауза</> : <><Play size={14} /> Запуск</>}
                </button>
                <button onClick={() => deletePlan(plan.id)} className="btn-danger flex items-center gap-1 text-sm">
                  <Trash2 size={14} /> Удалить
                </button>
              </div>
            </div>
          ))}
          {plans.length === 0 && (
            <div className="col-span-2 card text-center py-12 text-gray-500">
              <CalendarIcon size={48} className="mx-auto mb-3 opacity-50" />
              <p>Нет планов. Создайте первый план автопостинга.</p>
            </div>
          )}
        </div>
      )}

      {view === 'calendar' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <button onClick={() => setCurrentDate(addDays(startOfMonth(currentDate), -1))} className="btn-secondary text-sm">&lt;</button>
            <h3 className="font-semibold text-gray-900 dark:text-white">{format(currentDate, 'LLLL yyyy', { locale: ru })}</h3>
            <button onClick={() => setCurrentDate(addDays(endOfMonth(currentDate), 1))} className="btn-secondary text-sm">&gt;</button>
          </div>
          <div className="grid grid-cols-7 gap-1">
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((d) => (
              <div key={d} className="text-center text-xs font-medium text-gray-500 py-2">{d}</div>
            ))}
            {monthDays.map((day) => (
              <div
                key={day.toISOString()}
                className={`p-2 text-center rounded-lg text-sm ${
                  isToday(day) ? 'bg-chimera-100 dark:bg-chimera-900/20 text-chimera-700 font-bold' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                {format(day, 'd')}
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'timeline' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Таймлайн постов</h3>
          <div className="space-y-3">
            {plans.filter((p) => p.status === 'active').map((plan) => (
              <div key={plan.id} className="flex items-center gap-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="w-3 h-3 bg-green-500 rounded-full flex-shrink-0" />
                <div className="flex-1">
                  <p className="font-medium text-gray-900 dark:text-white text-sm">{plan.name}</p>
                  <p className="text-xs text-gray-500">{plan.posts_per_day} постов/день • {plan.accounts.length} аккаунтов</p>
                </div>
                <Clock size={14} className="text-gray-400" />
              </div>
            ))}
            {plans.filter((p) => p.status === 'active').length === 0 && (
              <p className="text-center text-gray-500 py-8">Нет активных планов</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
