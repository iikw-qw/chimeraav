/**
 * WebCodecs H.264 VideoDecoder — декодирование H.264 в реальном времени.
 * Зависит от: h264-parser
 */

import { parseNALUnits, NAL_TYPE, assembleFrame, type NALUnit } from './h264-parser';

export interface DecoderStats {
  framesDecoded: number;
  framesDropped: number;
  avgDecodeMs: number;
  lastFrameTime: number;
}

export type FrameCallback = (frame: VideoFrame) => void;

export class WebCodecsDecoder {
  private decoder: VideoDecoder | null = null;
  private sps: Uint8Array | null = null;
  private pps: Uint8Array | null = null;
  private initialized = false;
  private onFrame: FrameCallback;
  private stats: DecoderStats = {
    framesDecoded: 0,
    framesDropped: 0,
    avgDecodeMs: 0,
    lastFrameTime: 0,
  };
  private pendingFrames: Uint8Array[] = [];
  private frameTimestamp = 0;

  constructor(onFrame: FrameCallback) {
    this.onFrame = onFrame;
  }

  /**
   * Проверка поддержки WebCodecs
   */
  static isSupported(): boolean {
    return typeof VideoDecoder !== 'undefined';
  }

  /**
   * Обработка бинарного сообщения из WebSocket
   */
  feed(data: ArrayBuffer): void {
    const uint8 = new Uint8Array(data);
    const nalUnits = parseNALUnits(uint8);

    for (const nal of nalUnits) {
      if (nal.type === NAL_TYPE.SPS) {
        this.sps = nal.data;
        this._tryInitialize();
        continue;
      }

      if (nal.type === NAL_TYPE.PPS) {
        this.pps = nal.data;
        this._tryInitialize();
        continue;
      }

      if (nal.type === NAL_TYPE.SLICE_IDR || nal.type === NAL_TYPE.SLICE_NON_IDR) {
        this._decodeFrame(nal);
      }
    }
  }

  private _tryInitialize(): void {
    if (this.initialized || !this.sps || !this.pps) return;

    try {
      this.decoder = new VideoDecoder({
        output: (frame) => {
          this.stats.framesDecoded++;
          this.stats.lastFrameTime = performance.now();
          this.onFrame(frame);
        },
        error: (error) => {
          console.error('[WebCodecsDecoder] Decoder error:', error);
          this.initialized = false;
          this.decoder = null;
        },
      });

      // Codec string для H.264 Baseline Profile
      const profileIdc = this.sps[1];
      const profileCompat = this.sps[2];
      const levelIdc = this.sps[3];
      const codec = `avc1.${profileIdc.toString(16).padStart(2, '0')}${profileCompat.toString(16).padStart(2, '0')}${levelIdc.toString(16).padStart(2, '0')}`;

      this.decoder.configure({
        codec,
        optimizeForLatency: true,
      });

      this.initialized = true;

      // Декодировать накопленные фреймы
      for (const frame of this.pendingFrames) {
        this._decodeRaw(frame, false);
      }
      this.pendingFrames = [];
    } catch (e) {
      console.error('[WebCodecsDecoder] Init failed:', e);
    }
  }

  private _decodeFrame(nal: NALUnit): void {
    if (!this.initialized || !this.decoder) {
      if (nal.isKeyframe) {
        this.pendingFrames.push(nal.data);
      }
      return;
    }

    const frame = assembleFrame([nal]);
    this._decodeRaw(frame, nal.isKeyframe);
  }

  private _decodeRaw(data: Uint8Array, isKeyframe: boolean): void {
    if (!this.decoder || this.decoder.state === 'closed') return;

    try {
      const chunk = new EncodedVideoChunk({
        type: isKeyframe ? 'key' : 'delta',
        timestamp: this.frameTimestamp,
        data,
      });

      this.frameTimestamp += 33333; // ~30 FPS in microseconds

      if (this.decoder.decodeQueueSize > 5) {
        this.stats.framesDropped++;
        return;
      }

      this.decoder.decode(chunk);
    } catch (e) {
      console.warn('[WebCodecsDecoder] Decode error:', e);
    }
  }

  getStats(): DecoderStats {
    return { ...this.stats };
  }

  isReady(): boolean {
    return this.initialized;
  }

  reset(): void {
    if (this.decoder && this.decoder.state !== 'closed') {
      try {
        this.decoder.reset();
      } catch {
        // ignore
      }
    }
    this.initialized = false;
    this.sps = null;
    this.pps = null;
    this.pendingFrames = [];
    this.frameTimestamp = 0;
  }

  destroy(): void {
    if (this.decoder && this.decoder.state !== 'closed') {
      try {
        this.decoder.close();
      } catch {
        // ignore
      }
    }
    this.decoder = null;
    this.initialized = false;
    this.sps = null;
    this.pps = null;
    this.pendingFrames = [];
  }
}
