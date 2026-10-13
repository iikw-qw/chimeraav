// WebCodecs-based H.264 decoder.
// Wraps the browser-native VideoDecoder; receives Annex-B NAL units from the
// server and produces VideoFrames that can be drawn on a canvas.
//
// Why WebCodecs and not MSE: MSE buffers ~1-3 s before playback. We want
// sub-150 ms end-to-end latency, which requires a decoder that exposes
// per-frame output. WebCodecs is supported in Chrome 94+, Edge 94+, Safari
// 16.4+. For the rest we fall back to broadway-fallback.ts.

import { NAL_TYPE_SPS, NAL_TYPE_PPS, nalType } from './h264-parser'

export interface DecoderEvents {
  onFrame: (frame: VideoFrame) => void
  onError: (err: Error) => void
}

export function isWebCodecsSupported(): boolean {
  return typeof window !== 'undefined' && 'VideoDecoder' in window
}

export class WebCodecsH264Decoder {
  private decoder: VideoDecoder | null = null
  private configured = false
  private sps: Uint8Array | null = null
  private pps: Uint8Array | null = null
  private waitingForKeyframe = true
  // Browsers reject H.264 without an explicit profile/level codec string. We
  // pick the level out of the SPS, but until we have it we assume 4.0 which
  // covers everything up to 1080p30 — wide enough for our 720p stream.
  private codecString = 'avc1.42E01E' // baseline profile, level 3.0 default

  constructor(private events: DecoderEvents) {}

  async start(): Promise<void> {
    if (!isWebCodecsSupported()) {
      throw new Error('WebCodecs VideoDecoder is not available in this browser')
    }
    this.decoder = new VideoDecoder({
      output: (frame) => {
        try {
          this.events.onFrame(frame)
        } finally {
          // VideoFrame must be closed by the consumer to free GPU memory.
          // The hook closes after rendering — see useH264Decoder.
        }
      },
      error: (e) => {
        this.events.onError(e instanceof Error ? e : new Error(String(e)))
        this.waitingForKeyframe = true
      },
    })
  }

  // Push one Annex-B NAL unit. Returns true if the frame was forwarded to the
  // decoder (i.e. it was a slice / IDR), false if it was consumed as parameter
  // set or dropped while waiting for a keyframe.
  push(frame: Uint8Array, captureTsUs: number): boolean {
    if (!this.decoder) return false
    const nt = nalType(frame)

    if (nt === NAL_TYPE_SPS) {
      this.sps = frame
      this.tryConfigure()
      return false
    }
    if (nt === NAL_TYPE_PPS) {
      this.pps = frame
      this.tryConfigure()
      return false
    }

    // We don't have parameter sets yet — can't decode anything.
    if (!this.configured) return false

    const isKey = nt === 5 // IDR
    if (this.waitingForKeyframe) {
      if (!isKey) return false
      this.waitingForKeyframe = false
    }

    try {
      const chunk = new EncodedVideoChunk({
        type: isKey ? 'key' : 'delta',
        timestamp: captureTsUs,
        data: frame,
      })
      this.decoder.decode(chunk)
      return true
    } catch (err) {
      this.events.onError(err instanceof Error ? err : new Error(String(err)))
      this.waitingForKeyframe = true
      return false
    }
  }

  private tryConfigure(): void {
    if (this.configured || !this.decoder || !this.sps) return
    // Extract profile_idc and level_idc from SPS to build the codec string:
    // SPS = [start_code | nal_header | profile_idc | constraint_flags | level_idc | ...]
    const start = this.sps[0] === 0 && this.sps[1] === 0 && this.sps[2] === 0 && this.sps[3] === 1 ? 4 : 3
    if (this.sps.length >= start + 4) {
      const profileIdc = this.sps[start + 1]
      const constraintFlags = this.sps[start + 2]
      const levelIdc = this.sps[start + 3]
      const hex = (n: number) => n.toString(16).padStart(2, '0').toUpperCase()
      this.codecString = `avc1.${hex(profileIdc)}${hex(constraintFlags)}${hex(levelIdc)}`
    }

    const config: VideoDecoderConfig = {
      codec: this.codecString,
      // 'annexb' tells the decoder our chunks already include start codes.
      // Without this, Chrome wants AVCC-style length-prefixed NALs.
      // @ts-ignore — typings lag the WebCodecs spec on 'description' optional
      description: undefined,
      optimizeForLatency: true,
    }
    try {
      this.decoder.configure(config)
      this.configured = true
      this.waitingForKeyframe = true
    } catch (err) {
      this.events.onError(err instanceof Error ? err : new Error(String(err)))
    }
  }

  // Forces re-sync — call after a backpressure event where the server tells
  // us the queue was reset (i.e. we missed P-frames).
  resync(): void {
    this.waitingForKeyframe = true
  }

  async close(): Promise<void> {
    try {
      this.decoder?.close()
    } catch {
      // ignore
    }
    this.decoder = null
    this.configured = false
    this.sps = null
    this.pps = null
  }
}
