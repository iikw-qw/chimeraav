/*
 * ActionExecutor — receives JSON commands from the server WebSocket and
 * dispatches them to the appropriate handler (HumanInput, AccessibilityHelper,
 * shell commands).
 *
 * Supported commands:
 *   tap        { x, y }
 *   swipe      { x1, y1, x2, y2, duration? }
 *   longpress  { x, y, duration? }
 *   type       { text }
 *   scroll     { x, y, dx, dy }
 *   keyevent   { code }
 *   screenshot { }             (returns base64-encoded PNG)
 *   open_app   { package }
 *   home / back / recents
 *   shell      { cmd }        (arbitrary shell command)
 *   get_info   { }            (returns device info)
 *   find_element { by, value }
 *   click_element { by, value }
 *
 * Each command response is sent back as a JSON text frame:
 *   { "type": "result", "id": "<command_id>", "status": "ok"|"error", "data": ... }
 */

package com.chimera.agent.automation

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import com.chimera.agent.network.WebSocketClient
import com.chimera.agent.util.DeviceInfo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.InputStreamReader

class ActionExecutor(
    private val context: Context,
    private val ws: WebSocketClient,
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    /**
     * Parse and execute a command JSON received from the server.
     * Runs on a background coroutine so the WebSocket listener is not blocked.
     */
    fun execute(json: JSONObject) {
        val commandId = json.optString("id", "")
        val action = json.optString("action", "")

        scope.launch {
            try {
                val result = dispatch(action, json)
                sendResult(commandId, "ok", result)
            } catch (t: Throwable) {
                Log.e(TAG, "Command failed: $action", t)
                sendResult(commandId, "error", t.message ?: "unknown error")
            }
        }
    }

    private suspend fun dispatch(action: String, json: JSONObject): Any? {
        return when (action) {
            "tap" -> {
                val x = json.getDouble("x").toFloat()
                val y = json.getDouble("y").toFloat()
                HumanInput.tap(x, y)
                "tapped at ($x, $y)"
            }

            "swipe" -> {
                val x1 = json.getDouble("x1").toFloat()
                val y1 = json.getDouble("y1").toFloat()
                val x2 = json.getDouble("x2").toFloat()
                val y2 = json.getDouble("y2").toFloat()
                val duration = json.optLong("duration", 400)
                HumanInput.swipe(x1, y1, x2, y2, duration)
                "swiped ($x1,$y1) -> ($x2,$y2)"
            }

            "longpress" -> {
                val x = json.getDouble("x").toFloat()
                val y = json.getDouble("y").toFloat()
                val duration = json.optLong("duration", 800)
                HumanInput.longPress(x, y, duration)
                "long pressed at ($x, $y)"
            }

            "type" -> {
                val text = json.getString("text")
                HumanInput.typeText(text)
                "typed ${text.length} chars"
            }

            "scroll" -> {
                val x = json.getDouble("x").toFloat()
                val y = json.getDouble("y").toFloat()
                val dx = json.optDouble("dx", 0.0).toFloat()
                val dy = json.optDouble("dy", -300.0).toFloat()
                HumanInput.scroll(x, y, dx, dy)
                "scrolled at ($x,$y) by ($dx,$dy)"
            }

            "keyevent" -> {
                val code = json.getInt("code")
                execShell("input keyevent $code")
                "keyevent $code sent"
            }

            "home" -> {
                execShell("input keyevent 3")
                "home pressed"
            }

            "back" -> {
                execShell("input keyevent 4")
                "back pressed"
            }

            "recents" -> {
                execShell("input keyevent 187")
                "recents pressed"
            }

            "screenshot" -> {
                takeScreenshot()
            }

            "open_app" -> {
                val packageName = json.getString("package")
                openApp(packageName)
                "opened $packageName"
            }

            "shell" -> {
                val cmd = json.getString("cmd")
                val output = execShell(cmd)
                output ?: "no output"
            }

            "get_info" -> {
                val deviceId = json.optString("device_id", "unknown")
                val info = DeviceInfo.collect(context, deviceId)
                DeviceInfo.metadataJson(info)
            }

            "find_element" -> {
                val by = json.getString("by")
                val value = json.getString("value")
                val helper = AccessibilityHelper.instance
                if (helper != null) {
                    val node = helper.findElement(by, value)
                    if (node != null) {
                        val bounds = android.graphics.Rect()
                        node.getBoundsInScreen(bounds)
                        JSONObject().apply {
                            put("found", true)
                            put("text", node.text?.toString() ?: "")
                            put("class", node.className?.toString() ?: "")
                            put("bounds", "${bounds.left},${bounds.top},${bounds.right},${bounds.bottom}")
                        }.toString()
                    } else {
                        JSONObject().put("found", false).toString()
                    }
                } else {
                    throw IllegalStateException("Accessibility service not running")
                }
            }

            "click_element" -> {
                val by = json.getString("by")
                val value = json.getString("value")
                val helper = AccessibilityHelper.instance
                if (helper != null) {
                    val success = helper.clickElement(by, value)
                    if (success) "element clicked" else "element not found"
                } else {
                    throw IllegalStateException("Accessibility service not running")
                }
            }

            "input_text_element" -> {
                val by = json.getString("by")
                val value = json.getString("value")
                val text = json.getString("text")
                val helper = AccessibilityHelper.instance
                if (helper != null) {
                    val success = helper.inputText(by, value, text)
                    if (success) "text entered" else "element not found"
                } else {
                    throw IllegalStateException("Accessibility service not running")
                }
            }

            "get_package" -> {
                val helper = AccessibilityHelper.instance
                helper?.currentPackageName ?: execShell("dumpsys window | grep mCurrentFocus")
                ?: "unknown"
            }

            else -> throw IllegalArgumentException("Unknown action: $action")
        }
    }

    // ── Screenshot ────────────────────────────────────────────────────────

    private fun takeScreenshot(): String {
        // Use screencap shell command and encode as base64
        val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", "screencap -p"))
        val bytes = process.inputStream.readBytes()
        process.waitFor()
        return if (bytes.isNotEmpty()) {
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            JSONObject().apply {
                put("format", "png")
                put("size", bytes.size)
                put("data", b64)
            }.toString()
        } else {
            throw RuntimeException("screencap returned empty output")
        }
    }

    // ── Open app ──────────────────────────────────────────────────────────

    private fun openApp(packageName: String) {
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
        } else {
            // Fallback to monkey command
            execShell("monkey -p $packageName -c android.intent.category.LAUNCHER 1")
        }
    }

    // ── Shell execution ───────────────────────────────────────────────────

    private fun execShell(cmd: String): String? {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", cmd))
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            val output = reader.readText()
            val error = BufferedReader(InputStreamReader(process.errorStream)).readText()
            process.waitFor()
            if (error.isNotEmpty()) {
                Log.w(TAG, "Shell stderr: $error")
            }
            output.trim().ifEmpty { null }
        } catch (t: Throwable) {
            Log.w(TAG, "Shell command failed: $cmd", t)
            null
        }
    }

    // ── Result delivery ───────────────────────────────────────────────────

    private fun sendResult(commandId: String, status: String, data: Any?) {
        val response = JSONObject().apply {
            put("type", "result")
            put("id", commandId)
            put("status", status)
            if (data != null) put("data", data.toString())
        }
        ws.sendText(response.toString())
    }

    companion object {
        private const val TAG = "ChimeraActionExec"
    }
}
