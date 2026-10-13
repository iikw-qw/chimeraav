/**
 * Broadway.js WASM fallback для H.264 декодирования.
 * Используется когда WebCodecs API недоступен.
 * Зависит от: broadway (npm)
 */

export type FrameReadyCallback = (
  buffer: Uint8Array,
  width: number,
  height: number
) => void;

interface BroadwayDecoder {
  decode(data: Uint8Array): void;
  onPictureDecoded: ((buffer: Uint8Array, width: number, height: number, infos: unknown[]) => void) | null;
}

declare global {
  interface Window {
    Decoder?: new (config?: Record<string, unknown>) => BroadwayDecoder;
  }
}

export class BroadwayFallback {
  private decoder: BroadwayDecoder | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private onFrame: FrameReadyCallback | null = null;
  private framesDecoded = 0;
  private initialized = false;

  constructor(canvas?: HTMLCanvasElement) {
    this.canvas = canvas || null;
    if (this.canvas) {
      this.ctx = this.canvas.getContext('2d');
    }
  }

  /**
   * Проверка доступности Broadway.js
   */
  static isAvailable(): boolean {
    return typeof window !== 'undefined' && typeof window.Decoder !== 'undefined';
  }

  /**
   * Инициализация Broadway декодера
   */
  async initialize(onFrame?: FrameReadyCallback): Promise<boolean> {
    if (onFrame) {
      this.onFrame = onFrame;
    }

    try {
      // Динамическая загрузка Broadway если не загружен
      if (!window.Decoder) {
        await this._loadBroadway();
      }

      if (!window.Decoder) {
        console.error('[Broadway] Decoder not available after load');
        return false;
      }

      this.decoder = new window.Decoder({
        useWorker: true,
        workerFile: '/broadway/Decoder.js',
        webgl: 'prefer',
      });

      this.decoder.onPictureDecoded = (buffer, width, height) => {
        this.framesDecoded++;

        if (this.onFrame) {
          this.onFrame(new Uint8Array(buffer), width, height);
        }

        if (this.canvas && this.ctx) {
          this._renderToCanvas(buffer, width, height);
        }
      };

      this.initialized = true;
      return true;
    } catch (e) {
      console.error('[Broadway] Init failed:', e);
      return false;
    }
  }

  /**
   * Декодирование NAL unit
   */
  feed(data: ArrayBuffer): void {
    if (!this.decoder || !this.initialized) return;

    try {
      this.decoder.decode(new Uint8Array(data));
    } catch (e) {
      console.warn('[Broadway] Decode error:', e);
    }
  }

  /**
   * Рендеринг кадра на canvas
   */
  private _renderToCanvas(buffer: Uint8Array | ArrayLike<number>, width: number, height: number): void {
    if (!this.canvas || !this.ctx) return;

    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }

    const imageData = this.ctx.createImageData(width, height);
    const rgba = imageData.data;

    // YUV420 → RGBA
    const ySize = width * height;
    const uvSize = (width >> 1) * (height >> 1);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const yIndex = y * width + x;
        const uvIndex = (y >> 1) * (width >> 1) + (x >> 1);

        const Y = buffer[yIndex];
        const U = buffer[ySize + uvIndex] - 128;
        const V = buffer[ySize + uvSize + uvIndex] - 128;

        const rgbaIndex = yIndex * 4;
        rgba[rgbaIndex] = Math.max(0, Math.min(255, Y + 1.402 * V));
        rgba[rgbaIndex + 1] = Math.max(0, Math.min(255, Y - 0.344136 * U - 0.714136 * V));
        rgba[rgbaIndex + 2] = Math.max(0, Math.min(255, Y + 1.772 * U));
        rgba[rgbaIndex + 3] = 255;
      }
    }

    this.ctx.putImageData(imageData, 0, 0);
  }

  private async _loadBroadway(): Promise<void> {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/broadway/Decoder.js';
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Broadway.js'));
      document.head.appendChild(script);
    });
  }

  setCanvas(canvas: HTMLCanvasElement): void {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
  }

  getFramesDecoded(): number {
    return this.framesDecoded;
  }

  isReady(): boolean {
    return this.initialized;
  }

  destroy(): void {
    this.decoder = null;
    this.canvas = null;
    this.ctx = null;
    this.initialized = false;
    this.framesDecoded = 0;
  }
}
