/*
 * AdaptiveBitrate — picks an initial encode resolution / bitrate that fits
 * the device's screen while staying inside our latency budget (≤ 4 Mbps,
 * 720p target).
 *
 * Future work: hook a callback from StreamSender's outbound queue so we
 * can drop bitrate when the WebSocket starts buffering. For now, the
 * server-side backpressure (drop P-frames, request keyframe) is enough to
 * keep things stable on a typical Wi-Fi 5 GHz LAN.
 */

package com.chimera.agent.util

data class EncodeTarget(
    val width: Int,
    val height: Int,
    val framerate: Int,
    val bitrateBps: Int,
)

object AdaptiveBitrate {

    fun initialFor(srcWidth: Int, srcHeight: Int): EncodeTarget {
        val (w, h) = downscaleTo720p(srcWidth, srcHeight)
        // ~3 Mbps for 720p, ~1.5 Mbps for sub-720p.
        val bitrate = if (w >= 1280 || h >= 1280) 3_000_000 else 1_500_000
        return EncodeTarget(width = w, height = h, framerate = 30, bitrateBps = bitrate)
    }

    private fun downscaleTo720p(w: Int, h: Int): Pair<Int, Int> {
        val maxLong = 1280
        val long = maxOf(w, h)
        if (long <= maxLong) return alignToEven(w, h)
        val scale = maxLong.toDouble() / long
        return alignToEven((w * scale).toInt(), (h * scale).toInt())
    }

    // MediaCodec wants even dimensions for YUV chroma planes.
    private fun alignToEven(w: Int, h: Int): Pair<Int, Int> {
        val ew = if (w % 2 == 0) w else w - 1
        val eh = if (h % 2 == 0) h else h - 1
        return ew to eh
    }
}
