/**
 * Hook для H.264 декодирования с автовыбором WebCodecs/Broadway.
 * Depends on: webcodecs-decoder, broadway-fallback
 */

import { useRef, useCallback, useEffect, useState } from 'react';
import { WebCodecsDecoder } from '../lib/webcodecs-decoder';
import { BroadwayFallback } from '../lib/broadway-fallback';

interface UseH264DecoderOptions {
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  onStats?: (stats: { fps: number; decoder: string; framesDecoded: number }) => void;
}

export function useH264Decoder(options: UseH264DecoderOptions) {
  const { canvasRef, onStats } = options;

  const webCodecsRef = useRef<WebCodecsDecoder | null>(null);
  const broadwayRef = useRef<BroadwayFallback | null>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const [decoderType, setDecoderType] = useState<'webcodecs' | 'broadway' | 'none'>('none');
  const framesRef = useRef(0);
  const onStatsRef = useRef(onStats);
  onStatsRef.current = onStats;

  const renderVideoFrame = useCallback((frame: VideoFrame) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      frame.close();
      return;
    }

    if (canvas.width !== frame.displayWidth || canvas.height !== frame.displayHeight) {
      canvas.width = frame.displayWidth;
      canvas.height = frame.displayHeight;
      ctxRef.current = canvas.getContext('2d');
    }

    const ctx = ctxRef.current;
    if (ctx) {
      ctx.drawImage(frame, 0, 0);
      framesRef.current++;
    }
    frame.close();
  }, [canvasRef]);

  // Инициализация декодера
  useEffect(() => {
    if (WebCodecsDecoder.isSupported()) {
      const decoder = new WebCodecsDecoder(renderVideoFrame);
      webCodecsRef.current = decoder;
      setDecoderType('webcodecs');
    } else {
      const canvas = canvasRef.current;
      if (canvas) {
        const broadway = new BroadwayFallback(canvas);
        broadway.initialize().then((ok) => {
          if (ok) {
            broadwayRef.current = broadway;
            setDecoderType('broadway');
          }
        });
      }
    }

    // Stats reporting
    const statsInterval = setInterval(() => {
      const fps = framesRef.current;
      framesRef.current = 0;

      const wcStats = webCodecsRef.current?.getStats();
      const totalFrames = wcStats?.framesDecoded ?? broadwayRef.current?.getFramesDecoded() ?? 0;

      onStatsRef.current?.({
        fps,
        decoder: webCodecsRef.current ? 'webcodecs' : broadwayRef.current ? 'broadway' : 'none',
        framesDecoded: totalFrames,
      });
    }, 1000);

    return () => {
      clearInterval(statsInterval);
      webCodecsRef.current?.destroy();
      webCodecsRef.current = null;
      broadwayRef.current?.destroy();
      broadwayRef.current = null;
    };
  }, [canvasRef, renderVideoFrame]);

  const feed = useCallback((data: ArrayBuffer) => {
    if (webCodecsRef.current) {
      webCodecsRef.current.feed(data);
    } else if (broadwayRef.current) {
      broadwayRef.current.feed(data);
    }
  }, []);

  const reset = useCallback(() => {
    webCodecsRef.current?.reset();
  }, []);

  return {
    feed,
    reset,
    decoderType,
    isReady: decoderType !== 'none',
  };
}
