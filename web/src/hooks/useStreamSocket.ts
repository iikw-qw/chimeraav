/**
 * Hook для подключения к видеостриму устройства.
 * Depends on: useWebSocket
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';

interface StreamStats {
  fps: number;
  framesReceived: number;
  bytesReceived: number;
  latencyMs: number;
  connected: boolean;
  resolution: string;
}

interface UseStreamSocketOptions {
  deviceId: string;
  autoConnect?: boolean;
  onFrame?: (data: ArrayBuffer) => void;
  onMetadata?: (meta: Record<string, unknown>) => void;
}

export function useStreamSocket(options: UseStreamSocketOptions) {
  const { deviceId, autoConnect = true, onFrame, onMetadata } = options;

  const [stats, setStats] = useState<StreamStats>({
    fps: 0,
    framesReceived: 0,
    bytesReceived: 0,
    latencyMs: 0,
    connected: false,
    resolution: '',
  });

  const frameCountRef = useRef(0);
  const bytesRef = useRef(0);
  const lastFpsUpdate = useRef(performance.now());
  const callbacksRef = useRef({ onFrame, onMetadata });
  callbacksRef.current = { onFrame, onMetadata };

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/view/${deviceId}`;

  const handleMessage = useCallback((event: MessageEvent) => {
    if (event.data instanceof ArrayBuffer) {
      frameCountRef.current++;
      bytesRef.current += event.data.byteLength;
      callbacksRef.current.onFrame?.(event.data);
    } else if (typeof event.data === 'string') {
      try {
        const meta = JSON.parse(event.data);
        callbacksRef.current.onMetadata?.(meta);
      } catch {
        // ignore non-JSON text
      }
    }
  }, []);

  const handleOpen = useCallback(() => {
    setStats(prev => ({ ...prev, connected: true }));
  }, []);

  const handleClose = useCallback(() => {
    setStats(prev => ({ ...prev, connected: false, fps: 0 }));
  }, []);

  const { send, close, connect, isConnected } = useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
    onOpen: handleOpen,
    onClose: handleClose,
    autoConnect,
    binaryType: 'arraybuffer',
  });

  // FPS counter (обновление каждую секунду)
  useEffect(() => {
    const interval = setInterval(() => {
      const now = performance.now();
      const elapsed = (now - lastFpsUpdate.current) / 1000;
      const fps = Math.round(frameCountRef.current / elapsed);

      setStats(prev => ({
        ...prev,
        fps,
        framesReceived: prev.framesReceived + frameCountRef.current,
        bytesReceived: prev.bytesReceived + bytesRef.current,
        connected: isConnected,
      }));

      frameCountRef.current = 0;
      bytesRef.current = 0;
      lastFpsUpdate.current = now;
    }, 1000);

    return () => clearInterval(interval);
  }, [isConnected]);

  const requestScreenshot = useCallback(() => {
    send(JSON.stringify({ type: 'screenshot' }));
  }, [send]);

  return {
    stats,
    connect,
    close,
    send,
    isConnected,
    requestScreenshot,
  };
}
