// Broadway.js-style fallback H.264 decoder.
//
// We do NOT bundle Broadway.js itself (it adds ~300 KB of WASM and is rarely
// needed — every supported browser ships WebCodecs since 2022). Instead this
// module exposes the same shape as WebCodecsH264Decoder so callers can
// substitute it. If the user's browser lacks WebCodecs, a console hint is
// printed pointing at the on-disk fallback location; we render a static
// message in the UI rather than crash.
//
// If you ever ship Broadway.js, drop its `Decoder.js` build under
// `public/broadway/` and replace `push()` here with the actual call. The
// signature is kept tiny so the swap is a one-liner.

import {
  WebCodecsH264Decoder,
  isWebCodecsSupported,
  type DecoderEvents,
} from './webcodecs-decoder'
import { NAL_TYPE_SPS, NAL_TYPE_PPS, nalType } from './h264-parser'

export class BroadwayFallbackDecoder {
  private sps: Uint8Array | null = null
  private pps: Uint8Array | null = null
  private warnedOnce = false

  constructor(private events: DecoderEvents) {}

  async start(): Promise<void> {
    if (!this.warnedOnce) {
      this.warnedOnce = true
      this.events.onError(
        new Error(
          'WebCodecs is not available in this browser. ' +
            'Live H.264 streaming requires Chrome 94+, Edge 94+ or Safari 16.4+.',
        ),
      )
    }
  }

  push(frame: Uint8Array, _captureTsUs: number): boolean {
    const nt = nalType(frame)
    if (nt === NAL_TYPE_SPS) this.sps = frame
    else if (nt === NAL_TYPE_PPS) this.pps = frame
    return false
  }

  resync(): void {
    // no-op
  }

  async close(): Promise<void> {
    this.sps = null
    this.pps = null
  }
}

export type AnyH264Decoder = WebCodecsH264Decoder | BroadwayFallbackDecoder

export function createDecoder(events: DecoderEvents): {
  kind: 'webcodecs' | 'fallback'
  instance: AnyH264Decoder
} {
  if (isWebCodecsSupported()) {
    return { kind: 'webcodecs', instance: new WebCodecsH264Decoder(events) }
  }
  return { kind: 'fallback', instance: new BroadwayFallbackDecoder(events) }
}
