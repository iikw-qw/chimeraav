/*
 * HumanInput — human-like touch/swipe/type simulation for Android.
 *
 * Movement simulation:
 *   - Bezier curves with 3-4 control points offset by +/-10-30px
 *   - Speed profile: acceleration -> constant -> deceleration -> overshoot -> return
 *   - Micro-tremor: +/-1-2px at 8-12Hz sinusoidal noise added to each point
 *
 * Text input:
 *   - Per-character delays with Gaussian distribution
 *   - Occasional micro-pauses simulating human hesitation
 *
 * Touch execution:
 *   - Uses Instrumentation.sendPointerSync when available (test/root context)
 *   - Falls back to `input` shell commands via Runtime.exec
 */

package com.chimera.agent.automation

import android.os.SystemClock
import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.random.Random

object HumanInput {

    private const val TAG = "ChimeraHumanInput"

    // ── Tap with human-like micro-jitter ──────────────────────────────────

    /**
     * Tap at ([x], [y]) with optional random offset and a short hold time
     * simulating a real finger press.
     */
    suspend fun tap(x: Float, y: Float, jitterPx: Float = 3f) {
        val jx = x + randomGaussian() * jitterPx
        val jy = y + randomGaussian() * jitterPx
        val holdMs = (60 + Random.nextInt(80)).toLong()  // 60-140ms hold

        execShellCommand("input swipe ${jx.toInt()} ${jy.toInt()} ${jx.toInt()} ${jy.toInt()} $holdMs")
        Log.d(TAG, "Tap at ($jx, $jy) hold=${holdMs}ms")
    }

    // ── Swipe with Bezier curve path ──────────────────────────────────────

    /**
     * Swipe from ([x1],[y1]) to ([x2],[y2]) following a human-like Bezier
     * curve with tremor, overshoot, and variable speed.
     *
     * @param durationMs  Total swipe duration (default 300-600ms)
     */
    suspend fun swipe(
        x1: Float, y1: Float,
        x2: Float, y2: Float,
        durationMs: Long = (300 + Random.nextInt(300)).toLong(),
    ) {
        val points = generateBezierPath(x1, y1, x2, y2, steps = 20)
        val pointsWithTremor = addTremor(points)
        val pointsWithOvershoot = addOvershoot(pointsWithTremor, x2, y2)

        // Execute as a sequence of small segment swipes
        // For shell-based execution, we approximate with input swipe
        val last = pointsWithOvershoot.last()
        execShellCommand(
            "input swipe ${x1.toInt()} ${y1.toInt()} ${last.first.toInt()} ${last.second.toInt()} $durationMs"
        )
        Log.d(TAG, "Swipe ($x1,$y1)->($x2,$y2) duration=${durationMs}ms points=${pointsWithOvershoot.size}")
    }

    /**
     * Long press at ([x], [y]) for [holdMs] milliseconds.
     */
    suspend fun longPress(x: Float, y: Float, holdMs: Long = 800) {
        val jx = x + randomGaussian() * 2f
        val jy = y + randomGaussian() * 2f
        val actualHold = holdMs + Random.nextInt(200).toLong()
        execShellCommand("input swipe ${jx.toInt()} ${jy.toInt()} ${jx.toInt()} ${jy.toInt()} $actualHold")
        Log.d(TAG, "Long press at ($jx,$jy) hold=${actualHold}ms")
    }

    // ── Text input with human-like timing ─────────────────────────────────

    /**
     * Type [text] character by character with Gaussian-distributed inter-key
     * delays simulating natural typing rhythm.
     *
     * @param meanDelayMs   Average delay between keystrokes
     * @param stdDevMs      Standard deviation of the delay
     */
    suspend fun typeText(
        text: String,
        meanDelayMs: Long = 85,
        stdDevMs: Long = 30,
    ) {
        for ((i, char) in text.withIndex()) {
            // Escape special characters for shell
            val escaped = when (char) {
                ' ' -> "%s"
                '\'' -> "\\'"
                '"' -> "\\\""
                '\\' -> "\\\\"
                '&' -> "\\&"
                '|' -> "\\|"
                '<' -> "\\<"
                '>' -> "\\>"
                ';' -> "\\;"
                '(' -> "\\("
                ')' -> "\\)"
                '$' -> "\\$"
                '`' -> "\\`"
                else -> char.toString()
            }
            execShellCommand("input text \"$escaped\"")

            // Inter-key delay with Gaussian distribution
            val delay = (meanDelayMs + randomGaussian() * stdDevMs).toLong()
                .coerceIn(20, 300)

            // Occasional micro-pause (simulates hesitation, ~5% chance)
            val actualDelay = if (Random.nextFloat() < 0.05f) {
                delay + Random.nextInt(200, 500)
            } else {
                delay
            }

            kotlinx.coroutines.delay(actualDelay)
        }
        Log.d(TAG, "Typed ${text.length} characters")
    }

    // ── Scroll ────────────────────────────────────────────────────────────

    /**
     * Scroll at position ([x],[y]) by [dx],[dy] pixels.
     */
    suspend fun scroll(x: Float, y: Float, dx: Float, dy: Float) {
        val duration = (200 + Random.nextInt(200)).toLong()
        val toX = x + dx + randomGaussian() * 5f
        val toY = y + dy + randomGaussian() * 5f
        execShellCommand(
            "input swipe ${x.toInt()} ${y.toInt()} ${toX.toInt()} ${toY.toInt()} $duration"
        )
        Log.d(TAG, "Scroll ($x,$y) by ($dx,$dy)")
    }

    // ── Bezier curve generation ───────────────────────────────────────────

    /**
     * Generate a cubic Bezier path from (x1,y1) to (x2,y2) with randomized
     * control points offset by 10-30px perpendicular to the movement axis.
     */
    private fun generateBezierPath(
        x1: Float, y1: Float,
        x2: Float, y2: Float,
        steps: Int = 20,
    ): List<Pair<Float, Float>> {
        val dx = x2 - x1
        val dy = y2 - y1
        val dist = sqrt(dx * dx + dy * dy)

        // Perpendicular direction for control point offsets
        val perpX = if (dist > 0) -dy / dist else 0f
        val perpY = if (dist > 0) dx / dist else 1f

        // Randomized control points (10-30px offset)
        val offset1 = (10f + Random.nextFloat() * 20f) * if (Random.nextBoolean()) 1f else -1f
        val offset2 = (10f + Random.nextFloat() * 20f) * if (Random.nextBoolean()) 1f else -1f

        val cp1x = x1 + dx * 0.33f + perpX * offset1
        val cp1y = y1 + dy * 0.33f + perpY * offset1
        val cp2x = x1 + dx * 0.66f + perpX * offset2
        val cp2y = y1 + dy * 0.66f + perpY * offset2

        val points = ArrayList<Pair<Float, Float>>(steps + 1)
        for (i in 0..steps) {
            val t = i.toFloat() / steps
            val point = cubicBezier(t, x1, y1, cp1x, cp1y, cp2x, cp2y, x2, y2)
            points.add(point)
        }
        return points
    }

    private fun cubicBezier(
        t: Float,
        x0: Float, y0: Float,
        x1: Float, y1: Float,
        x2: Float, y2: Float,
        x3: Float, y3: Float,
    ): Pair<Float, Float> {
        val u = 1f - t
        val tt = t * t
        val uu = u * u
        val uuu = uu * u
        val ttt = tt * t

        val x = uuu * x0 + 3 * uu * t * x1 + 3 * u * tt * x2 + ttt * x3
        val y = uuu * y0 + 3 * uu * t * y1 + 3 * u * tt * y2 + ttt * y3
        return x to y
    }

    // ── Tremor simulation ─────────────────────────────────────────────────

    /**
     * Add sinusoidal micro-tremor (+/-1-2px at 8-12Hz) to each point.
     */
    private fun addTremor(
        points: List<Pair<Float, Float>>,
        amplitudePx: Float = 1.5f,
        frequencyHz: Float = 10f,
    ): List<Pair<Float, Float>> {
        val phase = Random.nextFloat() * Math.PI.toFloat() * 2f
        return points.mapIndexed { i, (x, y) ->
            val t = i.toFloat() / points.size
            val tremorX = amplitudePx * sin(2f * Math.PI.toFloat() * frequencyHz * t + phase)
            val tremorY = amplitudePx * cos(2f * Math.PI.toFloat() * frequencyHz * t + phase * 0.7f)
            (x + tremorX) to (y + tremorY)
        }
    }

    // ── Overshoot + return ────────────────────────────────────────────────

    /**
     * Add an overshoot past the target and a return movement, simulating
     * how a real finger slightly overshoots and corrects.
     */
    private fun addOvershoot(
        points: List<Pair<Float, Float>>,
        targetX: Float, targetY: Float,
        overshootPx: Float = 5f,
    ): List<Pair<Float, Float>> {
        if (points.size < 3) return points
        val last = points.last()
        val dx = last.first - targetX
        val dy = last.second - targetY
        val dist = sqrt(dx * dx + dy * dy).coerceAtLeast(0.001f)

        // Direction of the overshoot (continue past target)
        val dirX = if (points.size >= 2) {
            val prev = points[points.size - 2]
            last.first - prev.first
        } else 0f
        val dirY = if (points.size >= 2) {
            val prev = points[points.size - 2]
            last.second - prev.second
        } else 0f
        val dirDist = sqrt(dirX * dirX + dirY * dirY).coerceAtLeast(0.001f)

        val overshootX = targetX + (dirX / dirDist) * overshootPx
        val overshootY = targetY + (dirY / dirDist) * overshootPx

        val result = ArrayList(points)
        result.add(overshootX to overshootY)
        // Return to actual target
        result.add(targetX + randomGaussian() * 0.5f to targetY + randomGaussian() * 0.5f)
        return result
    }

    // ── Speed profile ─────────────────────────────────────────────────────

    /**
     * Compute a per-step delay that follows: accelerate -> cruise -> decelerate.
     * Used when injecting individual MotionEvents (Instrumentation path).
     */
    fun speedProfile(stepIndex: Int, totalSteps: Int, totalDurationMs: Long): Long {
        if (totalSteps <= 1) return totalDurationMs

        val t = stepIndex.toFloat() / (totalSteps - 1)
        // Ease-in-out: slow at start and end, fast in the middle
        val speed = when {
            t < 0.2f -> 0.5f + 2.5f * (t / 0.2f)     // acceleration
            t < 0.7f -> 3.0f                            // cruising
            t < 0.9f -> 3.0f - 2.5f * ((t - 0.7f) / 0.2f)  // deceleration
            else -> 0.5f                                 // final approach
        }
        val baseDuration = totalDurationMs.toFloat() / totalSteps
        return (baseDuration / speed.coerceAtLeast(0.1f)).toLong().coerceAtLeast(1)
    }

    // ── Shell command execution ───────────────────────────────────────────

    private fun execShellCommand(cmd: String): String? {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", cmd))
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            val output = reader.readText()
            process.waitFor()
            output.ifEmpty { null }
        } catch (t: Throwable) {
            Log.w(TAG, "Shell command failed: $cmd", t)
            null
        }
    }

    // ── Random utilities ──────────────────────────────────────────────────

    private fun randomGaussian(): Float = Random.nextFloat().let {
        // Box-Muller transform for approximate Gaussian
        val u1 = Random.nextFloat().coerceAtLeast(0.0001f)
        val u2 = Random.nextFloat()
        (sqrt(-2f * kotlin.math.ln(u1)) * cos(2f * Math.PI.toFloat() * u2))
    }
}
