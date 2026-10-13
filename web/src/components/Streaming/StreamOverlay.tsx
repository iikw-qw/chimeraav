/**
 * Оверлей поверх стрима: FPS, задержка, разрешение, IP, VPN.
 * Depends on: React, lucide-react
 */

import React from 'react';
import { Wifi, Shield, Monitor, Clock, Activity } from 'lucide-react';

interface StreamOverlayProps {
  fps: number;
  latencyMs: number;
  resolution: string;
  ipAddress?: string;
  vpnActive?: boolean;
  decoder: string;
  batteryLevel?: number;
  visible?: boolean;
}

export const StreamOverlay: React.FC<StreamOverlayProps> = ({
  fps,
  latencyMs,
  resolution,
  ipAddress,
  vpnActive,
  decoder,
  batteryLevel,
  visible = true,
}) => {
  if (!visible) return null;

  const fpsColor = fps >= 25 ? 'text-green-400' : fps >= 15 ? 'text-yellow-400' : 'text-red-400';
  const latencyColor = latencyMs < 100 ? 'text-green-400' : latencyMs < 200 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="absolute top-2 left-2 right-2 flex items-start justify-between pointer-events-none">
      <div className="flex flex-col gap-1">
        {/* FPS */}
        <div className="flex items-center gap-1 bg-black/50 rounded px-1.5 py-0.5">
          <Activity className={`w-3 h-3 ${fpsColor}`} />
          <span className={`text-[10px] font-mono ${fpsColor}`}>{fps} FPS</span>
        </div>

        {/* Задержка */}
        <div className="flex items-center gap-1 bg-black/50 rounded px-1.5 py-0.5">
          <Clock className={`w-3 h-3 ${latencyColor}`} />
          <span className={`text-[10px] font-mono ${latencyColor}`}>{latencyMs}ms</span>
        </div>

        {/* Разрешение */}
        {resolution && (
          <div className="flex items-center gap-1 bg-black/50 rounded px-1.5 py-0.5">
            <Monitor className="w-3 h-3 text-gray-300" />
            <span className="text-[10px] font-mono text-gray-300">{resolution}</span>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1 items-end">
        {/* Декодер */}
        <div className="bg-black/50 rounded px-1.5 py-0.5">
          <span className="text-[10px] font-mono text-blue-300">{decoder}</span>
        </div>

        {/* IP */}
        {ipAddress && (
          <div className="flex items-center gap-1 bg-black/50 rounded px-1.5 py-0.5">
            <Wifi className="w-3 h-3 text-gray-300" />
            <span className="text-[10px] font-mono text-gray-300">{ipAddress}</span>
          </div>
        )}

        {/* VPN */}
        {vpnActive && (
          <div className="flex items-center gap-1 bg-green-500/30 rounded px-1.5 py-0.5">
            <Shield className="w-3 h-3 text-green-400" />
            <span className="text-[10px] font-mono text-green-400">VPN</span>
          </div>
        )}

        {/* Батарея */}
        {batteryLevel !== undefined && (
          <div className={`bg-black/50 rounded px-1.5 py-0.5 ${
            batteryLevel < 20 ? 'text-red-400' : batteryLevel < 50 ? 'text-yellow-400' : 'text-green-400'
          }`}>
            <span className="text-[10px] font-mono">🔋 {batteryLevel}%</span>
          </div>
        )}
      </div>
    </div>
  );
};
