/*
 * StreamSender — receives encoded NAL units from H264Encoder, manages a
 * bounded queue, and pushes frames through the WebSocket.
 *
 * Backpressure policy:
 *   - The queue holds up to MAX_QUEUE_SIZE frames.
 *   - When full, new P-frames are dropped (we never drop SPS/PPS or IDR).
 *   - Drops are counted so the pipeline can react (e.g. request a keyframe,
 *     reduce bitrate).
 *
 * The first output from the encoder is a CODEC_CONFIG buffer containing
 * concatenated SPS+PPS; we split on Annex-B start codes (0x00000001) and
 * send each parameter set as a separate binary WebSocket message.
 *
 * Stats are accumulated in a rolling window and read by the stats reporter
 * in ScreenCaptureService every 10 seconds.
 */

package com.chimera.agent.network

import android.util.Log
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class StreamSender(private val ws: WebSocketClient) {

    private val queue = LinkedBlockingQueue<Frame>(MAX_QUEUE_SIZE)
    private val running = AtomicBoolean(true)

    // ── Stats ─────────────────────────────────────────────────────────────

    private val statsLock = Any()
    private var statsSentBytes = 0L
    private var statsDroppedFrames = 0
    private var statsQueuedFrames = 0

    // Sender thread drains the queue and writes to the WebSocket
    private val senderThread = Thread(::drainLoop).apply {
        name = "chimera-stream-sender"
        isDaemon = true
        start()
    }

    /**
     * Enqueue a NAL unit for sending. Called from the encoder callback thread.
     *
     * If the queue is full, non-keyframes are silently dropped.
     * Keyframes (and SPS/PPS) are always enqueued (with a brief wait).
     */
    fun sendNal(payload: ByteArray, isKeyframe: Boolean) {
        if (!running.get()) return

        // SPS+PPS / keyframes may contain multiple start codes; split them
        if (isKeyframe && payload.size > 8 && containsMultipleStartCodes(payload)) {
            for (nal in splitAnnexB(payload)) {
                enqueueFrame(Frame(nal, isKeyframe = true))
            }
            return
        }

        enqueueFrame(Frame(payload, isKeyframe))
    }

    private fun enqueueFrame(frame: Frame) {
        if (frame.isKeyframe) {
            // Keyframes get priority: wait briefly for space
            val ok = queue.offer(frame, 50, TimeUnit.MILLISECONDS)
            if (!ok) {
                // Force room by dropping the oldest non-keyframe
                queue.poll()
                queue.offer(frame)
                synchronized(statsLock) { statsDroppedFrames++ }
            }
        } else {
            val ok = queue.offer(frame)
            if (!ok) {
                // Backpressure: drop this P-frame
                synchronized(statsLock) { statsDroppedFrames++ }
            }
        }
        synchronized(statsLock) { statsQueuedFrames = queue.size }
    }

    private fun drainLoop() {
        while (running.get()) {
            try {
                val frame = queue.poll(500, TimeUnit.MILLISECONDS) ?: continue
                val sent = ws.sendBinary(frame.data)
                if (sent) {
                    synchronized(statsLock) {
                        statsSentBytes += frame.data.size
                        statsQueuedFrames = queue.size
                    }
                } else {
                    // WebSocket not connected; drop frame
                    synchronized(statsLock) { statsDroppedFrames++ }
                }
            } catch (_: InterruptedException) {
                return
            } catch (t: Throwable) {
                Log.w(TAG, "Error in sender loop", t)
            }
        }
    }

    /**
     * Snapshot the current stats window and reset counters.
     */
    fun snapshotStats(): Stats = synchronized(statsLock) {
        val s = Stats(
            sentBytes = statsSentBytes,
            droppedFrames = statsDroppedFrames,
            queuedFrames = statsQueuedFrames,
        )
        statsSentBytes = 0
        statsDroppedFrames = 0
        s
    }

    fun close() {
        running.set(false)
        senderThread.interrupt()
        ws.close()
    }

    // ── Annex-B splitting ─────────────────────────────────────────────────

    private fun containsMultipleStartCodes(buf: ByteArray): Boolean {
        var count = 0
        var i = 0
        while (i + 4 <= buf.size) {
            if (buf[i].toInt() == 0 && buf[i + 1].toInt() == 0 &&
                buf[i + 2].toInt() == 0 && buf[i + 3].toInt() == 1
            ) {
                count++
                if (count > 1) return true
                i += 4
            } else {
                i++
            }
        }
        return false
    }

    private fun splitAnnexB(buf: ByteArray): List<ByteArray> {
        val starts = ArrayList<Int>()
        var i = 0
        while (i + 4 <= buf.size) {
            if (buf[i].toInt() == 0 && buf[i + 1].toInt() == 0 &&
                buf[i + 2].toInt() == 0 && buf[i + 3].toInt() == 1
            ) {
                starts.add(i)
                i += 4
            } else {
                i++
            }
        }
        if (starts.size <= 1) return listOf(buf)
        val out = ArrayList<ByteArray>(starts.size)
        for (idx in starts.indices) {
            val from = starts[idx]
            val to = if (idx + 1 < starts.size) starts[idx + 1] else buf.size
            out.add(buf.copyOfRange(from, to))
        }
        return out
    }

    // ── Data classes ──────────────────────────────────────────────────────

    private data class Frame(val data: ByteArray, val isKeyframe: Boolean)

    data class Stats(
        val sentBytes: Long,
        val droppedFrames: Int,
        val queuedFrames: Int,
    )

    companion object {
        private const val TAG = "ChimeraStreamSender"
        private const val MAX_QUEUE_SIZE = 120  // ~4 seconds at 30fps
    }
}
