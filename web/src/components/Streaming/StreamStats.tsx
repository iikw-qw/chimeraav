/**
 * Статистика стрима: FPS, bitrate, viewers, время работы.
 * Depends on: React
 */

import React from 'react';

interface StreamStatsProps {
  fps: number;
  bitrate?: number;
  viewers?: number;
  framesDecoded: number;
  framesDropped?: number;
  decoder: string;
  uptime?: number;
}

export const StreamStats: React.FC<StreamStatsProps> = ({
  fps,
  bitrate,
  viewers,
  framesDecoded,
  framesDropped = 0,
  decoder,
  uptime,
}) => {
  const formatBitrate = (bps: number): string => {
    if (bps >= 1_000_000) return `${(bps / 1_000_000).toFixed(1)} Mbps`;
    if (bps >= 1_000) return `${(bps / 1_000).toFixed(0)} Kbps`;
    return `${bps} bps`;
  };

  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* FPS */}
      <div className="card p-3 text-center">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">FPS</p>
        <p className={`text-xl font-bold ${
          fps >= 25 ? 'text-green-500' : fps >= 15 ? 'text-yellow-500' : 'text-red-500'
        }`}>
          {fps}
        </p>
      </div>

      {/* Bitrate */}
      {bitrate !== undefined && (
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Bitrate</p>
          <p className="text-xl font-bold text-blue-500">{formatBitrate(bitrate)}</p>
        </div>
      )}

      {/* Decoder */}
      <div className="card p-3 text-center">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Декодер</p>
        <p className="text-sm font-medium dark:text-white">{decoder}</p>
      </div>

      {/* Frames */}
      <div className="card p-3 text-center">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Кадры</p>
        <p className="text-lg font-bold dark:text-white">
          {framesDecoded.toLocaleString()}
        </p>
        {framesDropped > 0 && (
          <p className="text-[10px] text-red-400">-{framesDropped} пропущено</p>
        )}
      </div>

      {/* Viewers */}
      {viewers !== undefined && (
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Зрители</p>
          <p className="text-xl font-bold text-purple-500">{viewers}</p>
        </div>
      )}

      {/* Uptime */}
      {uptime !== undefined && (
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Время работы</p>
          <p className="text-lg font-bold dark:text-white">{formatUptime(uptime)}</p>
        </div>
      )}
    </div>
  );
};
