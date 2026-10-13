/*
 * DeviceInfo — read-only metadata sent to the server right after the
 * WebSocket connects. Lets the operator dashboard show a model name and
 * battery level without an extra round-trip.
 */

package com.chimera.agent.util

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.util.DisplayMetrics
import android.view.WindowManager
import org.json.JSONObject

data class DeviceMeta(
    val deviceId: String,
    val model: String,
    val androidVersion: String,
    val screenWidth: Int,
    val screenHeight: Int,
    val densityDpi: Int,
    val batteryLevel: Int,
)

object DeviceInfo {

    fun collect(ctx: Context, deviceId: String): DeviceMeta {
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        wm.defaultDisplay.getRealMetrics(metrics)

        val battery = batteryLevel(ctx)
        return DeviceMeta(
            deviceId = deviceId,
            model = "${Build.MANUFACTURER} ${Build.MODEL}".trim(),
            androidVersion = Build.VERSION.RELEASE ?: "?",
            screenWidth = metrics.widthPixels,
            screenHeight = metrics.heightPixels,
            densityDpi = metrics.densityDpi,
            batteryLevel = battery,
        )
    }

    fun metadataJson(meta: DeviceMeta): String {
        val obj = JSONObject()
        obj.put("type", "metadata")
        obj.put("device_id", meta.deviceId)
        obj.put("model", meta.model)
        obj.put("android_version", meta.androidVersion)
        obj.put("resolution", "${meta.screenWidth}x${meta.screenHeight}")
        obj.put("battery_level", meta.batteryLevel)
        return obj.toString()
    }

    private fun batteryLevel(ctx: Context): Int {
        val intent: Intent = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            ?: return -1
        val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (level < 0 || scale <= 0) return -1
        return (level * 100 / scale).coerceIn(0, 100)
    }
}
