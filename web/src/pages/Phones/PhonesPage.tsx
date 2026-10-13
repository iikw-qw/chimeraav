/**
 * Страница "Телефоны" с вкладками Android/iOS.
 * Зависит от: deviceStore, api/client
 */

import { useState, useEffect } from 'react'
import { useDeviceStore, Device } from '../../store/deviceStore'
import { Smartphone, RefreshCw, Power, Crosshair, Camera, Trash2 } from 'lucide-react'
import { StatusBadge } from '../../components/common/StatusBadge'
import toast from 'react-hot-toast'

export default function PhonesPage() {
  const [tab, setTab] = useState<'android' | 'ios'>('android')
  const { devices, isLoading, fetchDevices, sendCommand, deleteDevice } = useDeviceStore()

  useEffect(() => {
    fetchDevices()
    const interval = setInterval(() => fetchDevices(), 15000)
    return () => clearInterval(interval)
  }, [])

  const filtered = devices.filter((d) => d.device_type === tab)

  const handleCommand = async (device: Device, cmd: string) => {
    try {
      await sendCommand(device.id, { type: cmd })
      toast.success(`Команда "${cmd}" отправлена: ${device.name}`)
    } catch {
      toast.error('Ошибка отправки команды')
    }
  }

  const handleDelete = async (device: Device) => {
    if (!confirm(`Удалить устройство ${device.name}?`)) return
    try {
      await deleteDevice(device.id)
      toast.success('Устройство удалено')
    } catch {
      toast.error('Ошибка удаления')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Телефоны</h1>
        <button onClick={() => fetchDevices()} className="btn-secondary flex items-center gap-2" disabled={isLoading}>
          <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setTab('android')}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
            tab === 'android' ? 'bg-green-500 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
          }`}
        >
          <Smartphone size={16} className="inline mr-2" />
          Android ({devices.filter((d) => d.device_type === 'android').length})
        </button>
        <button
          onClick={() => setTab('ios')}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
            tab === 'ios' ? 'bg-gray-800 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
          }`}
        >
          iOS ({devices.filter((d) => d.device_type === 'ios').length})
        </button>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Имя</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Статус</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Модель</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Батарея</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">IP</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">VPN</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Температура</th>
                <th className="text-right py-3 px-4 font-medium text-gray-500">Действия</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((device) => (
                <tr key={device.id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <td className="py-3 px-4">
                    <span className="font-medium text-gray-900 dark:text-white">{device.name}</span>
                    {device.serial_number && <span className="text-xs text-gray-400 block">{device.serial_number}</span>}
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={device.status} />
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                    {device.manufacturer} {device.model}
                    {device.os_version && <span className="text-xs text-gray-400 block">{device.os_version}</span>}
                  </td>
                  <td className="py-3 px-4">
                    {device.battery_level != null ? (
                      <span className={`font-medium ${device.battery_level < 20 ? 'text-red-500' : device.battery_level < 50 ? 'text-yellow-500' : 'text-green-500'}`}>
                        {device.battery_level}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400 text-xs font-mono">
                    {device.ip_address || '—'}
                    {device.external_ip && <span className="block text-gray-400">{device.external_ip}</span>}
                  </td>
                  <td className="py-3 px-4">
                    {device.vpn_active ? (
                      <span className="text-green-500 font-medium text-xs">Active</span>
                    ) : (
                      <span className="text-gray-400 text-xs">Off</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                    {device.temperature ? `${device.temperature.toFixed(1)}°C` : '—'}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleCommand(device, 'reboot')} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Перезагрузить">
                        <RefreshCw size={14} className="text-gray-500" />
                      </button>
                      <button onClick={() => handleCommand(device, 'screenshot')} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Скриншот">
                        <Camera size={14} className="text-gray-500" />
                      </button>
                      <button onClick={() => handleCommand(device, 'calibrate')} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Калибровка">
                        <Crosshair size={14} className="text-gray-500" />
                      </button>
                      <button onClick={() => handleCommand(device, 'disconnect')} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Отключить">
                        <Power size={14} className="text-orange-500" />
                      </button>
                      <button onClick={() => handleDelete(device)} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Удалить">
                        <Trash2 size={14} className="text-red-500" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-500">
                    Нет устройств {tab === 'android' ? 'Android' : 'iOS'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
