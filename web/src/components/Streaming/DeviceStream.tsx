/**
 * Компонент стриминга одного устройства: canvas + оверлей + кнопки.
 * Depends on: useStreamSocket, useH264Decoder
 */

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { useStreamSocket } from '../../hooks/useStreamSocket';
import { useH264Decoder } from '../../hooks/useH264Decoder';
import { Maximize2, Minimize2, Pause, Play, Camera, Wifi, WifiOff } from 'lucide-react';

interface DeviceStreamProps {
  deviceId: string;
  deviceName?: string;
  showOverlay?: boolean;
  showIp?: boolean;
  compact?: boolean;
  onFullscreen?: (deviceId: string) => void;
}

export const DeviceStream: React.FC<DeviceStreamProps> = ({
  deviceId,
  deviceName,
  showOverlay = true,
  showIp = false,
  compact = false,
  onFullscreen,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [decoderStats, setDecoderStats] = useState({ fps: 0, decoder: '', framesDecoded: 0 });
  const [metadata, setMetadata] = useState<Record<string, unknown>>({});

  const { feed, decoderType } = useH264Decoder({
    canvasRef,
    onStats: setDecoderStats,
  });

  const handleFrame = useCallback((data: ArrayBuffer) => {
    if (!paused) {
      feed(data);
    }
  }, [feed, paused]);

  const handleMetadata = useCallback((meta: Record<string, unknown>) => {
    setMetadata(prev => ({ ...prev, ...meta }));
  }, []);

  const { stats, isConnected, requestScreenshot } = useStreamSocket({
    deviceId,
    onFrame: handleFrame,
    onMetadata: handleMetadata,
  });

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      await containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      await document.exitFullscreen();
      setIsFullscreen(false);
    }

    onFullscreen?.(deviceId);
  }, [deviceId, onFullscreen]);

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, []);

  const handleScreenshot = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `screenshot_${deviceId}_${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
    }, 'image/png');
  }, [deviceId]);

  return (
    <div
      ref={containerRef}
      className={`relative bg-gray-900 rounded-lg overflow-hidden group ${
        compact ? 'aspect-[9/16]' : 'aspect-video'
      }`}
    >
      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="w-full h-full object-contain"
        style={{ imageRendering: 'auto' }}
      />

      {/* Статус подключения */}
      {!isConnected && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80">
          <div className="text-center text-gray-400">
            <WifiOff className="w-12 h-12 mx-auto mb-2" />
            <p className="text-sm">Нет подключения</p>
            {deviceName && <p className="text-xs mt-1">{deviceName}</p>}
          </div>
        </div>
      )}

      {/* Оверлей с информацией */}
      {showOverlay && isConnected && (
        <div className="absolute top-0 left-0 right-0 p-2 bg-gradient-to-b from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex items-center justify-between text-white text-xs">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1">
                <Wifi className="w-3 h-3 text-green-400" />
                {decoderStats.fps} FPS
              </span>
              <span className="text-gray-300">|</span>
              <span>{decoderType === 'webcodecs' ? 'WebCodecs' : 'Broadway'}</span>
              {metadata.resolution && (
                <>
                  <span className="text-gray-300">|</span>
                  <span>{String(metadata.resolution)}</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              {showIp && metadata.ip_address && (
                <span className="text-gray-300">{String(metadata.ip_address)}</span>
              )}
              {metadata.vpn_active && (
                <span className="px-1 bg-green-500/30 rounded text-green-300 text-[10px]">VPN</span>
              )}
            </div>
          </div>
          {deviceName && (
            <p className="text-white text-xs mt-1 font-medium">{deviceName}</p>
          )}
        </div>
      )}

      {/* Кнопки управления */}
      <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPaused(!paused)}
            className="p-1.5 bg-white/20 hover:bg-white/30 rounded-full transition"
            title={paused ? 'Продолжить' : 'Пауза'}
          >
            {paused ? (
              <Play className="w-4 h-4 text-white" />
            ) : (
              <Pause className="w-4 h-4 text-white" />
            )}
          </button>
          <button
            onClick={handleScreenshot}
            className="p-1.5 bg-white/20 hover:bg-white/30 rounded-full transition"
            title="Скриншот"
          >
            <Camera className="w-4 h-4 text-white" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 bg-white/20 hover:bg-white/30 rounded-full transition"
            title={isFullscreen ? 'Выйти из полного экрана' : 'Полный экран'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4 text-white" />
            ) : (
              <Maximize2 className="w-4 h-4 text-white" />
            )}
          </button>
        </div>
      </div>

      {/* Паузa */}
      {paused && isConnected && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Pause className="w-16 h-16 text-white/50" />
        </div>
      )}
    </div>
  );
};
