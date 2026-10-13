/*
 * WebSocketClient — OkHttp WebSocket wrapper with automatic reconnection
 * using capped exponential backoff (1s -> 2s -> 4s -> 8s -> 30s max).
 *
 * Features:
 *   - Binary frame sending for NAL unit delivery (hot path, never blocks)
 *   - Text frame sending for metadata/stats JSON
 *   - Heartbeat via OkHttp's built-in ping interval (5 seconds)
 *   - Receives text commands from server for action execution
 *   - Sends device metadata JSON as the first message on connect
 *   - Thread-safe: the encoder and stats loops call from different threads
 */

package com.chimera.agent.network

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

class WebSocketClient(
    private val url: String,
    private val onConnect: ((WebSocketClient) -> Unit)? = null,
    private val onMessage: ((String) -> Unit)? = null,
    private val onError: ((Throwable) -> Unit)? = null,
) {
    private val client: OkHttpClient = OkHttpClient.Builder()
        .pingInterval(HEARTBEAT_INTERVAL_SEC, TimeUnit.SECONDS)
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)   // infinite read for streaming
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private val socket = AtomicReference<WebSocket?>(null)
    private val running = AtomicBoolean(false)
    private val reconnectThread = Thread(::reconnectLoop).apply {
        name = "chimera-ws-reconnect"
        isDaemon = true
    }

    // Backoff state
    private val currentBackoffMs = AtomicLong(INITIAL_BACKOFF_MS)

    // Connection state observable
    @Volatile
    var isConnected: Boolean = false
        private set

    /**
     * Start the connection. Spawns a reconnect thread that will keep trying
     * to establish and maintain the WebSocket connection.
     */
    fun connect() {
        if (!running.compareAndSet(false, true)) return
        reconnectThread.start()
        Log.i(TAG, "WebSocket client started for $url")
    }

    /**
     * Gracefully close the WebSocket and stop the reconnect thread.
     */
    fun close() {
        running.set(false)
        isConnected = false
        socket.getAndSet(null)?.close(1000, "client shutdown")
        reconnectThread.interrupt()
        client.dispatcher.executorService.shutdown()
        Log.i(TAG, "WebSocket client closed")
    }

    /**
     * Send a binary frame (NAL unit). Returns false if the socket is not
     * connected — the caller should drop the frame rather than buffering.
     */
    fun sendBinary(data: ByteArray): Boolean {
        val ws = socket.get() ?: return false
        return ws.send(data.toByteString(0, data.size))
    }

    fun sendBinary(bytes: ByteString): Boolean {
        val ws = socket.get() ?: return false
        return ws.send(bytes)
    }

    /**
     * Send a text frame (JSON metadata, stats, command responses).
     */
    fun sendText(text: String): Boolean {
        val ws = socket.get() ?: return false
        return ws.send(text)
    }

    // ── Reconnect loop with exponential backoff ───────────────────────────

    private fun reconnectLoop() {
        while (running.get()) {
            val current = socket.get()
            if (current != null) {
                // Already connected; wait a bit and check again
                try {
                    Thread.sleep(1000)
                } catch (_: InterruptedException) {
                    return
                }
                continue
            }

            // Attempt connection
            try {
                Log.i(TAG, "Connecting to $url ...")
                val request = Request.Builder().url(url).build()
                val ws = client.newWebSocket(request, listener)
                socket.set(ws)
            } catch (t: Throwable) {
                Log.w(TAG, "Connection attempt failed", t)
                onError?.invoke(t)
            }

            // Backoff before next attempt
            val delay = currentBackoffMs.get()
            try {
                Thread.sleep(delay)
            } catch (_: InterruptedException) {
                return
            }

            // Exponential backoff: 1s -> 2s -> 4s -> 8s -> 16s -> 30s (capped)
            currentBackoffMs.updateAndGet { prev ->
                (prev * 2).coerceAtMost(MAX_BACKOFF_MS)
            }
        }
    }

    // ── WebSocket listener ────────────────────────────────────────────────

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            Log.i(TAG, "WebSocket opened: $url")
            isConnected = true
            currentBackoffMs.set(INITIAL_BACKOFF_MS) // reset backoff on success
            onConnect?.invoke(this@WebSocketClient)
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            Log.d(TAG, "WS text message: ${text.take(200)}")
            onMessage?.invoke(text)
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            Log.d(TAG, "WS binary message: ${bytes.size} bytes")
            // Binary messages from server are not expected in normal operation
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            Log.i(TAG, "WebSocket closing: $code / $reason")
            webSocket.close(code, reason)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            Log.i(TAG, "WebSocket closed: $code / $reason")
            isConnected = false
            socket.compareAndSet(webSocket, null)
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.w(TAG, "WebSocket failure: ${t.message}", t)
            isConnected = false
            socket.compareAndSet(webSocket, null)
            onError?.invoke(t)
        }
    }

    companion object {
        private const val TAG = "ChimeraWS"
        private const val HEARTBEAT_INTERVAL_SEC = 5L
        private const val INITIAL_BACKOFF_MS = 1000L       // 1 second
        private const val MAX_BACKOFF_MS = 30_000L         // 30 seconds
    }
}
