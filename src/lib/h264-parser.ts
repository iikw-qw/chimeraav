// H.264 Annex-B NAL-unit utilities.
// На сервере фрейм приходит как один NAL unit с 4-байтным start-кодом
// 0x00 00 00 01. WebCodecs VideoDecoder принимает ровно такой формат, поэтому
// здесь нужны только helpers — определение типа NAL и keyframe.

export const NAL_TYPE_SPS = 7
export const NAL_TYPE_PPS = 8
export const NAL_TYPE_IDR = 5

export interface NalInfo {
  type: number
  isKeyframe: boolean
  isParamSet: boolean
}

export function nalType(frame: Uint8Array): number {
  if (frame.length < 5) return -1
  let start = 0
  if (
    frame[0] === 0x00 &&
    frame[1] === 0x00 &&
    frame[2] === 0x00 &&
    frame[3] === 0x01
  ) {
    start = 4
  } else if (frame[0] === 0x00 && frame[1] === 0x00 && frame[2] === 0x01) {
    start = 3
  }
  if (start >= frame.length) return -1
  return frame[start] & 0x1f
}

export function inspect(frame: Uint8Array): NalInfo {
  const t = nalType(frame)
  return {
    type: t,
    isKeyframe: t === NAL_TYPE_IDR,
    isParamSet: t === NAL_TYPE_SPS || t === NAL_TYPE_PPS,
  }
}

// Extracts an `avcC`-style description (concatenated SPS+PPS in the format
// VideoDecoder expects when configured with `avc.format = 'annexb'`).
// We don't need this for Annex-B mode but keep helper available for callers.
export function concatParamSets(sps: Uint8Array, pps: Uint8Array): Uint8Array {
  const out = new Uint8Array(sps.length + pps.length)
  out.set(sps, 0)
  out.set(pps, sps.length)
  return out
}
