/*
 * H264Encoder — wraps MediaCodec configured for low-latency H.264 encoding
 * from a Surface input. Emits Annex-B-prefixed NAL units via the onSample
 * callback, exactly matching what the Chimera server expects on the producer
 * WebSocket.
 *
 * Tuning for "live remote control" UX:
 *   - CBR (constant bitrate) to keep bandwidth predictable
 *   - 1-second I-frame interval so new viewers can join quickly
 *   - KEY_LOW_LATENCY=1 (Android 11+) to suppress B-frames & lookahead
 *   - KEY_PRIORITY=0 for realtime scheduling priority
 *   - BASELINE profile for maximum browser/WebCodecs compatibility
 *   - Adaptive bitrate: 2-4 Mbps adjusted via adjustBitrate()
 *   - First output contains SPS+PPS parameter sets
 */

package com.chimera.agent.capture

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.view.Surface
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicInteger

class H264Encoder(
    private val width: Int,
    private val height: Int,
    private val framerate: Int,
    bitrate: Int,
    private val iFrameIntervalSec: Int = 1,
    private val onSample: (data: ByteArray, isKeyframe: Boolean) -> Unit,
) {
    private val codec: MediaCodec = MediaCodec.createEncoderByType(MIME_TYPE)
    val inputSurface: Surface

    /** Current effective bitrate in bps. Thread-safe read. */
    val currentBitrate: Int get() = _currentBitrate.get()
    private val _currentBitrate = AtomicInteger(bitrate)

    // ── Stats tracking ────────────────────────────────────────────────────

    private val statsLock = Any()
    private var sampleFps = 0
    private var sampleBytes = 0
    private var totalFrames = 0L
    private var windowStart = System.nanoTime()

    // ── Encoder thread ────────────────────────────────────────────────────

    private val callbackThread = HandlerThread("chimera-encoder-cb").apply { start() }
    private val handler = Handler(callbackThread.looper)

    // SPS+PPS stored so we can re-send on keyframe requests
    @Volatile
    private var spsPps: ByteArray? = null

    init {
        val format = MediaFormat.createVideoFormat(MIME_TYPE, width, height).apply {
            setInteger(
                MediaFormat.KEY_COLOR_FORMAT,
                MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface
            )
            setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
            setInteger(
                MediaFormat.KEY_BITRATE_MODE,
                MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR
            )
            setInteger(MediaFormat.KEY_FRAME_RATE, framerate)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, iFrameIntervalSec)
            setInteger(
                MediaFormat.KEY_PROFILE,
                MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline
            )
            setInteger(
                MediaFormat.KEY_LEVEL,
                MediaCodecInfo.CodecProfileLevel.AVCLevel31
            )
            // Low-latency hint (Android 11+): disables B-frames and look-ahead
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
            }
            // Realtime scheduling priority
            setInteger(MediaFormat.KEY_PRIORITY, 0)
        }

        codec.setCallback(object : MediaCodec.Callback() {
            override fun onInputBufferAvailable(c: MediaCodec, index: Int) {
                // Surface-mode encoder: we never feed input buffers manually
            }

            override fun onOutputBufferAvailable(
                c: MediaCodec, index: Int, info: MediaCodec.BufferInfo,
            ) {
                try {
                    val buf: ByteBuffer = c.getOutputBuffer(index) ?: return
                    if (info.size <= 0) return

                    val isCfg = (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0
                    val isKey = (info.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0 || isCfg

                    buf.position(info.offset)
                    buf.limit(info.offset + info.size)
                    val payload = ByteArray(info.size)
                    buf.get(payload)

                    // Store SPS+PPS for later re-sends
                    if (isCfg) {
                        spsPps = payload.copyOf()
                        Log.i(TAG, "SPS+PPS captured: ${payload.size} bytes")
                    }

                    // Update stats
                    synchronized(statsLock) {
                        sampleFps += 1
                        sampleBytes += payload.size
                        totalFrames += 1
                    }

                    onSample(payload, isKey)
                } finally {
                    try {
                        c.releaseOutputBuffer(index, false)
                    } catch (_: Throwable) {
                    }
                }
            }

            override fun onError(c: MediaCodec, e: MediaCodec.CodecException) {
                Log.e(TAG, "MediaCodec encoder error", e)
            }

            override fun onOutputFormatChanged(c: MediaCodec, format: MediaFormat) {
                Log.i(TAG, "Encoder output format changed: $format")
            }
        }, handler)

        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        inputSurface = codec.createInputSurface()
    }

    fun start() {
        codec.start()
        Log.i(TAG, "H264Encoder started: ${width}x${height} @ ${framerate}fps, " +
            "${_currentBitrate.get() / 1000}kbps CBR, idr=${iFrameIntervalSec}s")
    }

    /**
     * Dynamically adjust the encoder bitrate without restarting the codec.
     * Takes effect from the next frame.
     */
    fun adjustBitrate(newBitrateBps: Int) {
        val clamped = newBitrateBps.coerceIn(MIN_BITRATE, MAX_BITRATE)
        _currentBitrate.set(clamped)
        try {
            val params = Bundle().apply {
                putInt(MediaCodec.PARAMETER_KEY_VIDEO_BITRATE, clamped)
            }
            codec.setParameters(params)
            Log.i(TAG, "Bitrate adjusted to ${clamped / 1000} kbps")
        } catch (t: Throwable) {
            Log.w(TAG, "Failed to adjust bitrate", t)
        }
    }

    /**
     * Request an immediate keyframe (IDR). Useful when a new viewer connects
     * or after a network reconnection.
     */
    fun requestKeyframe() {
        try {
            val params = Bundle().apply {
                putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0)
            }
            codec.setParameters(params)
            Log.i(TAG, "Keyframe requested")
        } catch (t: Throwable) {
            Log.w(TAG, "Failed to request keyframe", t)
        }
    }

    /** Return the cached SPS+PPS, or null if not yet emitted. */
    fun getSpsPps(): ByteArray? = spsPps?.copyOf()

    /**
     * Snapshot the current stats window and reset counters. Call every ~10s.
     */
    fun snapshotStats(): Snapshot = synchronized(statsLock) {
        val now = System.nanoTime()
        val elapsedSec = ((now - windowStart) / 1e9).coerceAtLeast(0.001)
        val fps = (sampleFps / elapsedSec).toInt()
        val bps = ((sampleBytes * 8) / elapsedSec).toInt()
        sampleFps = 0
        sampleBytes = 0
        windowStart = now
        Snapshot(fps, bps, totalFrames)
    }

    fun release() {
        try {
            codec.signalEndOfInputStream()
        } catch (_: Throwable) {
        }
        try {
            codec.stop()
        } catch (_: Throwable) {
        }
        try {
            codec.release()
        } catch (_: Throwable) {
        }
        try {
            inputSurface.release()
        } catch (_: Throwable) {
        }
        if (callbackThread.isAlive) callbackThread.quitSafely()
        Log.i(TAG, "H264Encoder released")
    }

    data class Snapshot(val fps: Int, val bitrate: Int, val frames: Long)

    companion object {
        private const val MIME_TYPE = MediaFormat.MIMETYPE_VIDEO_AVC
        private const val TAG = "ChimeraEncoder"
        const val MIN_BITRATE = 500_000      // 500 kbps floor
        const val MAX_BITRATE = 4_000_000    // 4 Mbps ceiling
    }
}
