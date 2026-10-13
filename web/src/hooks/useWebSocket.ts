/**
 * WebSocket hook с автореконнектом и exponential backoff.
 * Depends on: React
 */

import { useEffect, useRef, useCallback, useState } from 'react';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: MessageEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  autoConnect?: boolean;
  maxRetries?: number;
  binaryType?: BinaryType;
}

interface UseWebSocketReturn {
  send: (data: string | ArrayBuffer | Blob) => void;
  close: () => void;
  connect: () => void;
  readyState: number;
  isConnected: boolean;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    autoConnect = true,
    maxRetries = 10,
    binaryType = 'arraybuffer',
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const [readyState, setReadyState] = useState(WebSocket.CLOSED);

  const callbacksRef = useRef({ onMessage, onOpen, onClose, onError });
  callbacksRef.current = { onMessage, onOpen, onClose, onError };

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);
      ws.binaryType = binaryType;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        retriesRef.current = 0;
        setReadyState(WebSocket.OPEN);
        callbacksRef.current.onOpen?.();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        callbacksRef.current.onMessage?.(event);
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setReadyState(WebSocket.CLOSED);
        callbacksRef.current.onClose?.();

        // Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s max
        if (retriesRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000);
          retriesRef.current++;
          timeoutRef.current = setTimeout(() => {
            if (mountedRef.current) connect();
          }, delay);
        }
      };

      ws.onerror = (error) => {
        if (!mountedRef.current) return;
        callbacksRef.current.onError?.(error);
      };

      wsRef.current = ws;
      setReadyState(WebSocket.CONNECTING);
    } catch (e) {
      console.error('[useWebSocket] Connection error:', e);
    }
  }, [url, binaryType, maxRetries]);

  const send = useCallback((data: string | ArrayBuffer | Blob) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const close = useCallback(() => {
    retriesRef.current = maxRetries;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [maxRetries]);

  useEffect(() => {
    mountedRef.current = true;
    if (autoConnect) connect();

    return () => {
      mountedRef.current = false;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, autoConnect]);

  return {
    send,
    close,
    connect,
    readyState,
    isConnected: readyState === WebSocket.OPEN,
  };
}
