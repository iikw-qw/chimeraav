/**
 * Карта устройств: сетка live-стримов + панель прогрева.
 */

import { useEffect, useState } from 'react'
import { useDeviceStore, Device } from '../store/deviceStore'
import { Wifi, WifiOff, Battery, Thermometer, Monitor } from 'lucide-react'
import api from '../api/client'

export default function DeviceMap() {
  const { devices, fetchDevices } = useDeviceStore()
  const [gridSize, setGridSize] = useState<'2x2' | '3x3' | '4x4'>('3x3')
  const [warmupCoeff, setWarmupCoeff] = useState(0)
  const [filter, setFilter] = useState<string>('all')

  useEffect(() => {
    fetchDevices()
    loadWarmupCoeff()
    const interval = setInterval(() => {
      fetchDevices()
      loadWarmupCoeff()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadWarmupCoeff = async () => {
    try {
      const { data } = await api.get('/settings?scope=global')
      const wc = data.find((s: any) => s.key === 'warmup_coefficient')
      if (wc) setWarmupCoeff(wc.value)
    } catch { /* ignore */ }
  }

  const filtered = devices.filter((d) => filter === 'all' || d.device_type === filter)
  const cols = gridSize === '2x2' ? 2 : gridSize === '3x3' ? 3 : 4

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Карта устройств</h1>
        <div className="flex items-center gap-3">
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="input-field !w-auto">
            <option value="all">Все</option>
            <option value="android">Android</option>
            <option value="ios">iOS</option>
          </select>
          <select value={gridSize} onChange={(e) => setGridSize(e.target.value as any)} className="input-field !w-auto">
            <option value="2x2">2x2</option>
            <option value="3x3">3x3</option>
            <option value="4x4">4x4</option>
          </select>
        </div>
      </div>

      {/* Warmup panel */}
      <div className="card bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/10 dark:to-amber-900/10 border-orange-200 dark:border-orange-800">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-orange-800 dark:text-orange-300">Коэффициент прогрева</h3>
            <p className="text-sm text-orange-600 dark:text-orange-400">
              {warmupCoeff.toFixed(2)} — активно {devices.filter((d) => d.status === 'online').length}/{devices.length}
            </p>
          </div>
          <div className="w-48 bg-orange-200 dark:bg-orange-800 rounded-full h-3">
            <div
              className="bg-orange-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(warmupCoeff * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Device grid */}
      <div className={`grid gap-4`} style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {filtered.map((device) => (
          <DeviceCard key={device.id} device={device} />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            <Monitor size={48} className="mx-auto mb-3 opacity-50" />
            <p>Нет подключённых устройств</p>
          </div>
        )}
      </div>
    </div>
  )
}

function DeviceCard({ device }: { device: Device }) {
  const isOnline = device.status === 'online' || device.status === 'busy'

  return (
    <div className="card relative overflow-hidden group cursor-pointer hover:shadow-lg transition-shadow">
      {/* Stream placeholder */}
      <div className="aspect-[9/16] max-h-64 bg-gray-900 rounded-lg mb-3 flex items-center justify-center">
        {isOnline ? (
          <div className="text-center text-gray-500">
            <Monitor size={32} className="mx-auto mb-2" />
            <p className="text-xs">Live Stream</p>
          </div>
        ) : (
          <div className="text-center text-gray-600">
            <WifiOff size={32} className="mx-auto mb-2" />
            <p className="text-xs">Offline</p>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-gray-900 dark:text-white text-sm truncate">{device.name}</h3>
          <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-green-500' : 'bg-gray-400'}`} />
        </div>
        <p className="text-xs text-gray-500">{device.model || device.device_type}</p>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {device.battery_level != null && (
            <span className="flex items-center gap-1"><Battery size={12} /> {device.battery_level}%</span>
          )}
          {device.ip_address && (
            <span className="flex items-center gap-1"><Wifi size={12} /> {device.ip_address}</span>
          )}
          {device.vpn_active && (
            <span className="text-green-500 font-medium">VPN</span>
          )}
        </div>
      </div>
    </div>
  )
}
