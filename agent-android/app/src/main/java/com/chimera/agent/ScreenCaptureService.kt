/*
 * ScreenCaptureService — foreground service that owns the full streaming
 * pipeline and the MediaProjection token.
 *
 * Pipeline topology:
 *   MediaProjection → ScreenCapture (VirtualDisplay) → H264Encoder (MediaCodec)
 *                   → StreamSender (queue) → WebSocketClient (OkHttp WS)
 *
 * Only one instance runs at a time. The notification lets the user stop the
 * stream from the shade, and cleaning up here guarantees the VirtualDisplay
 * and codec are released even on a crash or OOM kill.
 */

package com.chimera.agent

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.chimera.agent.automation.ActionExecutor
import com.chimera.agent.capture.H264Encoder
import com.chimera.agent.capture.ScreenCapture
import com.chimera.agent.network.StreamSender
import com.chimera.agent.network.WebSocketClient
import com.chimera.agent.util.AdaptiveBitrate
import com.chimera.agent.util.DeviceInfo
import com.chimera.agent.util.IpChecker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

class ScreenCaptureService : Service() {

    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var pipelineJob: Job? = null
    private var statsJob: Job? = null
    private var ipCheckerJob: Job? = null
    private var projection: MediaProjection? = null
    private var capture: ScreenCapture? = null
    private var encoder: H264Encoder? = null
    private var sender: StreamSender? = null
    private var wsClient: WebSocketClient? = null
    private var actionExecutor: ActionExecutor? = null
    private var ipChecker: IpChecker? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null || intent.action != ACTION_START) return START_NOT_STICKY

        val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, -1)
        @Suppress("DEPRECATION")
        val resultData = intent.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        val serverUrl = intent.getStringExtra(EXTRA_SERVER_URL).orEmpty()
        val deviceId = intent.getStringExtra(EXTRA_DEVICE_ID).orEmpty()

        if (resultData == null || serverUrl.isEmpty() || deviceId.isEmpty()) {
            Log.e(TAG, "Missing required extras, stopping self")
            stopSelf()
            return START_NOT_STICKY
        }

        startInForeground()

        val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val proj = mpm.getMediaProjection(resultCode, resultData)
        if (proj == null) {
            Log.e(TAG, "MediaProjection token rejected by system")
            stopSelf()
            return START_NOT_STICKY
        }
        projection = proj

        pipelineJob = scope.launch {
            runPipeline(serverUrl, deviceId, proj)
        }
        return START_STICKY
    }

    private suspend fun runPipeline(
        serverUrl: String,
        deviceId: String,
        proj: MediaProjection,
    ) {
        // Collect device metadata
        val info = DeviceInfo.collect(this@ScreenCaptureService, deviceId)
        val target = AdaptiveBitrate.initialFor(info.screenWidth, info.screenHeight)

        // WebSocket connection with command handling
        val ws = WebSocketClient(
            url = "$serverUrl/api/ws/stream/$deviceId",
            onConnect = { client ->
                client.sendText(DeviceInfo.metadataJson(info))
            },
            onMessage = { text ->
                handleServerCommand(text)
            },
            onError = { t ->
                Log.w(TAG, "WebSocket error", t)
                updateNotification("Connection error")
            },
        )
        wsClient = ws

        // Stream sender with queue management
        val streamSender = StreamSender(ws)
        sender = streamSender

        // Hardware H.264 encoder
        val enc = H264Encoder(
            width = target.width,
            height = target.height,
            framerate = target.framerate,
            bitrate = target.bitrateBps,
            iFrameIntervalSec = 1,
            onSample = { buffer, isKeyframe ->
                streamSender.sendNal(buffer, isKeyframe)
            },
        )
        encoder = enc
        enc.start()

        // Screen capture via VirtualDisplay
        val cap = ScreenCapture(
            projection = proj,
            width = target.width,
            height = target.height,
            dpi = info.densityDpi,
            inputSurface = enc.inputSurface,
        )
        capture = cap
        cap.start()

        // Action executor for server commands
        actionExecutor = ActionExecutor(this@ScreenCaptureService, ws)

        // External IP checker (every 60 seconds)
        ipChecker = IpChecker()
        ipCheckerJob = scope.launch {
            while (true) {
                try {
                    val externalIp = ipChecker?.fetchExternalIp()
                    if (externalIp != null) {
                        val ipJson = JSONObject().apply {
                            put("type", "ip_update")
                            put("external_ip", externalIp)
                        }
                        ws.sendText(ipJson.toString())
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "IP check failed", t)
                }
                delay(60_000L)
            }
        }

        // Connect WebSocket
        ws.connect()
        updateNotification("Streaming ${target.width}x${target.height}")

        // Periodic stats reporting every 10 seconds
        statsJob = scope.launch {
            while (true) {
                delay(10_000L)
                try {
                    val encStats = enc.snapshotStats()
                    val senderStats = streamSender.snapshotStats()
                    val statsJson = JSONObject().apply {
                        put("type", "stats")
                        put("fps", encStats.fps)
                        put("bitrate", encStats.bitrate)
                        put("frames", encStats.frames)
                        put("queued", senderStats.queuedFrames)
                        put("dropped", senderStats.droppedFrames)
                        put("sent_bytes", senderStats.sentBytes)
                    }
                    ws.sendText(statsJson.toString())

                    // Adaptive bitrate: reduce quality if too many frames are dropping
                    if (senderStats.droppedFrames > 5) {
                        val newBitrate = AdaptiveBitrate.reduceBitrate(enc.currentBitrate)
                        enc.adjustBitrate(newBitrate)
                        Log.i(TAG, "Reduced bitrate to $newBitrate due to backpressure")
                    } else if (senderStats.droppedFrames == 0 && enc.currentBitrate < target.bitrateBps) {
                        val newBitrate = AdaptiveBitrate.increaseBitrate(enc.currentBitrate, target.bitrateBps)
                        enc.adjustBitrate(newBitrate)
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "Stats reporting failed", t)
                }
            }
        }
    }

    private fun handleServerCommand(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type", "")
            if (type == "command") {
                actionExecutor?.execute(json)
            }
        } catch (t: Throwable) {
            Log.w(TAG, "Failed to parse server command", t)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "Service destroyed, releasing pipeline resources")
        pipelineJob?.cancel()
        statsJob?.cancel()
        ipCheckerJob?.cancel()
        capture?.release()
        encoder?.release()
        sender?.close()
        wsClient?.close()
        projection?.stop()
        scope.cancel()
    }

    // ── Foreground notification ───────────────────────────────────────────

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) == null) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    "Chimera Screen Capture",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Active while Chimera agent streams the screen"
                }
            )
        }
        val notification = buildNotification("Starting...")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun updateNotification(text: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun buildNotification(text: String) =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("Chimera Agent")
            .setContentText(text)
            .setOngoing(true)
            .addAction(
                android.R.drawable.ic_media_pause,
                "Stop",
                PendingIntent.getService(
                    this, 0,
                    Intent(this, ScreenCaptureService::class.java).apply {
                        action = ACTION_STOP
                    },
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .build()

    companion object {
        const val ACTION_START = "com.chimera.agent.START"
        const val ACTION_STOP = "com.chimera.agent.STOP"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_SERVER_URL = "server_url"
        const val EXTRA_DEVICE_ID = "device_id"
        private const val CHANNEL_ID = "chimera_capture"
        private const val NOTIFICATION_ID = 0xC417
        private const val TAG = "ChimeraCaptureSvc"
    }
}
