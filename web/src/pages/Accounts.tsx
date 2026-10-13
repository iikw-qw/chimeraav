/**
 * Страница аккаунтов: таблица + React Flow карта привязки.
 * Зависит от: accountStore, deviceStore, api/client
 */

import { useEffect, useState, useCallback } from 'react'
import { useAccountStore, Account } from '../store/accountStore'
import { useDeviceStore, Device } from '../store/deviceStore'
import { Plus, X, Map, List, Trash2, Edit2 } from 'lucide-react'
import {
  ReactFlow, Background, Controls, MiniMap,
  Node, Edge, useNodesState, useEdgesState, Connection, addEdge,
  MarkerType, Handle, Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import toast from 'react-hot-toast'

const PLATFORM_COLORS: Record<string, string> = {
  instagram: '#E4405F', telegram: '#0088CC', facebook: '#1877F2', tiktok: '#FE2C55',
  twitter: '#000000', linkedin: '#0A66C2', vk: '#4C75A3', youtube: '#FF0000',
  reddit: '#FF4500', threads: '#101010',
}

const PLATFORMS = Object.keys(PLATFORM_COLORS)

export default function Accounts() {
  const { accounts, fetchAccounts, addAccount, updateAccount, deleteAccount } = useAccountStore()
  const { devices, fetchDevices } = useDeviceStore()
  const [view, setView] = useState<'table' | 'map'>('table')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ platform: 'instagram', username: '', password_encrypted: '', device_id: '' })

  useEffect(() => {
    fetchAccounts()
    fetchDevices()
  }, [])

  const handleAdd = async () => {
    try {
      await addAccount({ ...form, device_id: form.device_id || undefined } as any)
      setShowAdd(false)
      setForm({ platform: 'instagram', username: '', password_encrypted: '', device_id: '' })
      toast.success('Аккаунт добавлен')
    } catch {
      toast.error('Ошибка добавления')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Удалить аккаунт?')) return
    try {
      await deleteAccount(id)
      toast.success('Аккаунт удалён')
    } catch {
      toast.error('Ошибка удаления')
    }
  }

  const handleReassign = async (accountId: string, deviceId: string) => {
    try {
      await updateAccount(accountId, { device_id: deviceId } as any)
      toast.success('Привязка обновлена')
    } catch {
      toast.error('Ошибка перепривязки')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Аккаунты и привязка</h1>
        <div className="flex gap-2">
          <button onClick={() => setView('table')} className={`p-2 rounded-lg ${view === 'table' ? 'bg-chimera-100 dark:bg-chimera-900/20 text-chimera-600' : 'text-gray-500'}`}>
            <List size={20} />
          </button>
          <button onClick={() => setView('map')} className={`p-2 rounded-lg ${view === 'map' ? 'bg-chimera-100 dark:bg-chimera-900/20 text-chimera-600' : 'text-gray-500'}`}>
            <Map size={20} />
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> Добавить
          </button>
        </div>
      </div>

      {/* Add modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAdd(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Добавить аккаунт</h3>
              <button onClick={() => setShowAdd(false)}><X size={20} className="text-gray-500" /></button>
            </div>
            <div className="space-y-3">
              <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} className="input-field">
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="input-field" placeholder="Логин" />
              <input type="password" value={form.password_encrypted} onChange={(e) => setForm({ ...form, password_encrypted: e.target.value })} className="input-field" placeholder="Пароль" />
              <select value={form.device_id} onChange={(e) => setForm({ ...form, device_id: e.target.value })} className="input-field">
                <option value="">Без привязки</option>
                {devices.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.device_type})</option>)}
              </select>
              <button onClick={handleAdd} className="btn-primary w-full">Добавить</button>
            </div>
          </div>
        </div>
      )}

      {view === 'table' ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Платформа</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Логин</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Статус</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Устройство</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Подписчики</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Прогрев</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">Действия</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acc) => {
                  const device = devices.find((d) => d.id === acc.device_id)
                  return (
                    <tr key={acc.id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td className="py-3 px-4">
                        <span className="px-2 py-1 rounded text-xs font-medium text-white" style={{ backgroundColor: PLATFORM_COLORS[acc.platform] || '#666' }}>
                          {acc.platform}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-900 dark:text-white">{acc.username}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          acc.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400' :
                          acc.status === 'banned' ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400' :
                          'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                        }`}>
                          {acc.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-gray-600 dark:text-gray-400">{device?.name || '—'}</td>
                      <td className="py-3 px-4 text-gray-600 dark:text-gray-400">{acc.followers_count}</td>
                      <td className="py-3 px-4">
                        <span className={acc.warmup_enabled ? 'text-green-500' : 'text-gray-400'}>{acc.warmup_enabled ? 'Вкл' : 'Выкл'}</span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button onClick={() => handleDelete(acc.id)} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
                          <Trash2 size={14} className="text-red-500" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {accounts.length === 0 && (
                  <tr><td colSpan={7} className="py-12 text-center text-gray-500">Нет аккаунтов</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <AccountMap accounts={accounts} devices={devices} onReassign={handleReassign} />
      )}
    </div>
  )
}

function AccountMap({ accounts, devices, onReassign }: { accounts: Account[]; devices: Device[]; onReassign: (accId: string, devId: string) => void }) {
  const deviceNodes: Node[] = devices.map((d, i) => ({
    id: `device-${d.id}`,
    type: 'default',
    position: { x: 100, y: 100 + i * 200 },
    data: { label: `${d.name}\n${d.ip_address || ''}` },
    style: { width: 180, padding: 16, fontSize: 13, fontWeight: 600, background: '#f0f4ff', border: '2px solid #4c6ef5', borderRadius: 12 },
  }))

  const accNodes: Node[] = accounts.map((a, i) => ({
    id: `acc-${a.id}`,
    type: 'default',
    position: { x: 450, y: 50 + i * 100 },
    data: { label: `${a.username}\n${a.password_encrypted || '***'}` },
    style: {
      width: 160, padding: 10, fontSize: 12,
      border: `2px solid ${PLATFORM_COLORS[a.platform] || '#666'}`,
      borderRadius: 8, background: '#fff',
    },
  }))

  const initialEdges: Edge[] = accounts
    .filter((a) => a.device_id)
    .map((a) => ({
      id: `e-${a.device_id}-${a.id}`,
      source: `device-${a.device_id}`,
      target: `acc-${a.id}`,
      style: { stroke: PLATFORM_COLORS[a.platform] || '#666', strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: PLATFORM_COLORS[a.platform] || '#666' },
    }))

  const [nodes, setNodes, onNodesChange] = useNodesState([...deviceNodes, ...accNodes])
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const onConnect = useCallback((connection: Connection) => {
    const sourceDevId = connection.source?.replace('device-', '')
    const targetAccId = connection.target?.replace('acc-', '')
    if (sourceDevId && targetAccId) {
      onReassign(targetAccId, sourceDevId)
      setEdges((eds) => addEdge(connection, eds))
    }
  }, [onReassign, setEdges])

  return (
    <div className="card" style={{ height: 600 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}
