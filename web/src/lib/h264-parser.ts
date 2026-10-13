/**
 * H.264 NAL unit parser for WebSocket binary frames.
 * Depends on: nothing (pure TypeScript)
 */

// NAL unit types
export const NAL_TYPE = {
  SLICE_NON_IDR: 1,
  SLICE_A: 2,
  SLICE_B: 3,
  SLICE_C: 4,
  SLICE_IDR: 5,
  SEI: 6,
  SPS: 7,
  PPS: 8,
  AUD: 9,
} as const;

export interface NALUnit {
  type: number;
  data: Uint8Array;
  isKeyframe: boolean;
}

export interface ParsedFrame {
  nalUnits: NALUnit[];
  isKeyframe: boolean;
  timestamp?: number;
}

/**
 * Разделение бинарного потока на NAL units по start codes (0x000001 или 0x00000001)
 */
export function parseNALUnits(data: Uint8Array): NALUnit[] {
  const units: NALUnit[] = [];
  const startPositions: number[] = [];

  // Поиск start codes
  for (let i = 0; i < data.length - 3; i++) {
    if (data[i] === 0 && data[i + 1] === 0) {
      if (data[i + 2] === 1) {
        startPositions.push(i + 3);
        i += 2;
      } else if (data[i + 2] === 0 && i + 3 < data.length && data[i + 3] === 1) {
        startPositions.push(i + 4);
        i += 3;
      }
    }
  }

  // Если start codes не найдены — весь буфер это одна NAL unit
  if (startPositions.length === 0) {
    if (data.length > 0) {
      const nalType = data[0] & 0x1f;
      units.push({
        type: nalType,
        data: data,
        isKeyframe: nalType === NAL_TYPE.SLICE_IDR,
      });
    }
    return units;
  }

  // Извлечение NAL units
  for (let i = 0; i < startPositions.length; i++) {
    const start = startPositions[i];
    const end = i + 1 < startPositions.length
      ? startPositions[i + 1] - (data[startPositions[i + 1] - 4] === 0 ? 4 : 3)
      : data.length;

    const nalData = data.slice(start, end);
    if (nalData.length === 0) continue;

    const nalType = nalData[0] & 0x1f;
    units.push({
      type: nalType,
      data: nalData,
      isKeyframe: nalType === NAL_TYPE.SLICE_IDR,
    });
  }

  return units;
}

/**
 * Проверка наличие SPS в наборе NAL units
 */
export function hasSPS(units: NALUnit[]): boolean {
  return units.some(u => u.type === NAL_TYPE.SPS);
}

/**
 * Проверка наличия PPS
 */
export function hasPPS(units: NALUnit[]): boolean {
  return units.some(u => u.type === NAL_TYPE.PPS);
}

/**
 * Проверка: содержит ли набор keyframe (IDR)
 */
export function hasKeyframe(units: NALUnit[]): boolean {
  return units.some(u => u.isKeyframe);
}

/**
 * Извлечение параметров из SPS (базовое: разрешение)
 */
export function parseSPSResolution(spsData: Uint8Array): { width: number; height: number } | null {
  if (spsData.length < 4) return null;

  try {
    // Упрощённый парсинг — для полного нужен exp-golomb decoder
    // Возвращаем null, разрешение будет определено VideoDecoder
    return null;
  } catch {
    return null;
  }
}

/**
 * Сборка полного фрейма для VideoDecoder из NAL units
 * Добавляет Annex B start codes (0x00000001)
 */
export function assembleFrame(units: NALUnit[]): Uint8Array {
  let totalSize = 0;
  for (const unit of units) {
    totalSize += 4 + unit.data.length; // 4 bytes start code + data
  }

  const result = new Uint8Array(totalSize);
  let offset = 0;

  for (const unit of units) {
    // Start code: 0x00000001
    result[offset] = 0;
    result[offset + 1] = 0;
    result[offset + 2] = 0;
    result[offset + 3] = 1;
    offset += 4;

    result.set(unit.data, offset);
    offset += unit.data.length;
  }

  return result;
}

/**
 * Подготовка SPS+PPS для инициализации декодера
 */
export function buildDecoderConfig(sps: Uint8Array, pps: Uint8Array): Uint8Array {
  const startCode = new Uint8Array([0, 0, 0, 1]);
  const result = new Uint8Array(startCode.length + sps.length + startCode.length + pps.length);

  let offset = 0;
  result.set(startCode, offset); offset += startCode.length;
  result.set(sps, offset); offset += sps.length;
  result.set(startCode, offset); offset += startCode.length;
  result.set(pps, offset);

  return result;
}
