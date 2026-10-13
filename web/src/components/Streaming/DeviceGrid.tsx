/**
 * Сетка устройств с live-стримами: 2x2/3x3/4x4, виртуализация.
 * Depends on: DeviceStream, react-window
 */

import React, { useState, useCallback, useMemo } from 'react';
import { DeviceStream } from './DeviceStream';
import { Grid, LayoutGrid, Maximize2 } from 'lucide-react';

interface Device {
  id: string;
  name: string;
  device_type: string;
  status: string;
  ip_address?: string;
}

interface DeviceGridProps {
  devices: Device[];
  gridSize?: 2 | 3 | 4;
  showOverlay?: boolean;
  showIp?: boolean;
  onDeviceClick?: (deviceId: string) => void;
}

export const DeviceGrid: React.FC<DeviceGridProps> = ({
  devices,
  gridSize: initialGridSize = 2,
  showOverlay = true,
  showIp = false,
  onDeviceClick,
}) => {
  const [gridSize, setGridSize] = useState(initialGridSize);
  const [expandedDevice, setExpandedDevice] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'android' | 'ios'>('all');

  const filteredDevices = useMemo(() => {
    const online = devices.filter(d => d.status === 'online' || d.status === 'busy');
    if (filter === 'all') return online;
    return online.filter(d => d.device_type === filter);
  }, [devices, filter]);

  const handleFullscreen = useCallback((deviceId: string) => {
    setExpandedDevice(prev => prev === deviceId ? null : deviceId);
    onDeviceClick?.(deviceId);
  }, [onDeviceClick]);

  if (expandedDevice) {
    const device = filteredDevices.find(d => d.id === expandedDevice);
    if (device) {
      return (
        <div className="w-full h-full">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-medium dark:text-white">{device.name}</h3>
            <button
              onClick={() => setExpandedDevice(null)}
              className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition"
            >
              ← Назад к сетке
            </button>
          </div>
          <DeviceStream
            deviceId={device.id}
            deviceName={device.name}
            showOverlay={showOverlay}
            showIp={showIp}
            onFullscreen={() => setExpandedDevice(null)}
          />
        </div>
      );
    }
  }

  return (
    <div className="w-full">
      {/* Панель управления */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {filteredDevices.length} устройств онлайн
          </span>

          <div className="flex items-center gap-1 ml-4 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            {(['all', 'android', 'ios'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-1 text-xs rounded transition ${
                  filter === f
                    ? 'bg-white dark:bg-gray-700 shadow text-gray-900 dark:text-white'
                    : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {f === 'all' ? 'Все' : f === 'android' ? 'Android' : 'iOS'}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {([2, 3, 4] as const).map(size => (
            <button
              key={size}
              onClick={() => setGridSize(size)}
              className={`p-1.5 rounded transition ${
                gridSize === size
                  ? 'bg-white dark:bg-gray-700 shadow'
                  : 'hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
              title={`${size}x${size}`}
            >
              {size === 2 && <Grid className="w-4 h-4" />}
              {size === 3 && <LayoutGrid className="w-4 h-4" />}
              {size === 4 && <Maximize2 className="w-4 h-4" />}
            </button>
          ))}
        </div>
      </div>

      {/* Сетка */}
      {filteredDevices.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-gray-400">
          <p>Нет онлайн-устройств для отображения</p>
        </div>
      ) : (
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
          }}
        >
          {filteredDevices.slice(0, gridSize * gridSize * 2).map(device => (
            <div
              key={device.id}
              className="cursor-pointer"
              onClick={() => handleFullscreen(device.id)}
            >
              <DeviceStream
                deviceId={device.id}
                deviceName={device.name}
                showOverlay={showOverlay}
                showIp={showIp}
                compact
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
