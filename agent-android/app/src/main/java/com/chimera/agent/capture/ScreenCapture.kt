/*
 * ScreenCapture — wraps MediaProjection.createVirtualDisplay so the encoder's
 * input Surface receives frames at the requested resolution.
 *
 * The Surface comes from H264Encoder; we own the VirtualDisplay lifecycle here.
 * Keeping the two concerns separated means the encoder can be restarted (e.g.
 * to adjust bitrate) without re-acquiring the projection token.
 *
 * Resolution is scaled to 720p maximum while maintaining the original aspect
 * ratio. The AdaptiveBitrate utility pre-computes the target dimensions.
 */

package com.chimera.agent.capture

import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.view.Surface

class ScreenCapture(
    private val projection: MediaProjection,
    private val width: Int,
    private val height: Int,
    private val dpi: Int,
    private val inputSurface: Surface,
) {
    private val callbackThread = HandlerThread("chimera-capture-cb").apply { start() }
    private val handler = Handler(callbackThread.looper)
    private var virtualDisplay: VirtualDisplay? = null
    private var released = false

    /*
     * Android 14+ requires a registered Callback before createVirtualDisplay
     * will deliver frames. On older APIs this is harmless.
     */
    private val callback = object : MediaProjection.Callback() {
        override fun onStop() {
            Log.i(TAG, "MediaProjection stopped by system")
            release()
        }
    }

    /**
     * Begin capturing the screen into the provided Surface at [width]x[height].
     * The VirtualDisplay mirrors the primary display with AUTO_MIRROR so it
     * follows orientation changes automatically.
     */
    fun start() {
        projection.registerCallback(callback, handler)

        virtualDisplay = projection.createVirtualDisplay(
            "ChimeraCapture",
            width,
            height,
            dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            inputSurface,
            object : VirtualDisplay.Callback() {
                override fun onPaused() {
                    Log.d(TAG, "VirtualDisplay paused")
                }
                override fun onResumed() {
                    Log.d(TAG, "VirtualDisplay resumed")
                }
                override fun onStopped() {
                    Log.d(TAG, "VirtualDisplay stopped")
                }
            },
            handler,
        )
        Log.i(TAG, "VirtualDisplay created: ${width}x${height} @ ${dpi}dpi")
    }

    /**
     * Resize the VirtualDisplay without re-creating it. Useful when
     * AdaptiveBitrate downgrades quality on a poor network.
     */
    fun resize(newWidth: Int, newHeight: Int, newDpi: Int) {
        virtualDisplay?.resize(newWidth, newHeight, newDpi)
        Log.i(TAG, "VirtualDisplay resized to ${newWidth}x${newHeight}")
    }

    /**
     * Release the VirtualDisplay and unregister the projection callback.
     * Safe to call multiple times.
     */
    fun release() {
        if (released) return
        released = true
        try {
            virtualDisplay?.release()
        } catch (t: Throwable) {
            Log.w(TAG, "Error releasing VirtualDisplay", t)
        }
        virtualDisplay = null
        try {
            projection.unregisterCallback(callback)
        } catch (t: Throwable) {
            Log.w(TAG, "Error unregistering callback", t)
        }
        if (callbackThread.isAlive) {
            callbackThread.quitSafely()
        }
        Log.i(TAG, "ScreenCapture released")
    }

    companion object {
        private const val TAG = "ChimeraScreenCapture"
    }
}
