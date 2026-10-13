/*
 * MainActivity — UI entry point for the Chimera Android agent.
 *
 * Responsibilities:
 *   1. Collect server URL + device ID from the user (persisted via SharedPreferences)
 *   2. Request necessary runtime permissions (notification, overlay, accessibility)
 *   3. Acquire a MediaProjection token via the system permission dialog
 *   4. Launch ScreenCaptureService as a foreground service and hand it the token
 *   5. Display a real-time connection status indicator
 */

package com.chimera.agent

import android.Manifest
import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.chimera.agent.automation.AccessibilityHelper
import com.chimera.agent.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: SharedPreferences
    private var serviceBound = false

    // ── Permission launchers (must be registered before onStart) ──────────

    private val notificationLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            Toast.makeText(
                this,
                "Notification permission is required for the foreground service",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private val projectionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startCapture(result.resultCode, result.data!!)
        } else {
            updateStatus("MediaProjection permission denied")
        }
    }

    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this)) {
            updateStatus("Overlay permission granted")
        } else {
            updateStatus("Overlay permission denied")
        }
    }

    // ── Service connection ────────────────────────────────────────────────

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            serviceBound = true
            updateStatus("Service connected")
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBound = false
            updateStatus("Service disconnected")
        }
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = getSharedPreferences("chimera-agent", Context.MODE_PRIVATE)
        binding.serverInput.setText(prefs.getString("server_url", "ws://192.168.1.10:17842"))
        binding.deviceInput.setText(prefs.getString("device_id", Build.SERIAL ?: "device_01"))

        binding.startButton.setOnClickListener { onStartClicked() }
        binding.stopButton.setOnClickListener { onStopClicked() }
        binding.stopButton.isEnabled = false

        updateStatus("Ready")
        ensurePermissions()
    }

    override fun onResume() {
        super.onResume()
        refreshPermissionStatus()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (serviceBound) {
            try {
                unbindService(serviceConnection)
            } catch (_: Throwable) {
            }
            serviceBound = false
        }
    }

    // ── Permissions ───────────────────────────────────────────────────────

    private fun ensurePermissions() {
        // 1. Notification permission (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun refreshPermissionStatus() {
        val overlayOk = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else true

        val accessibilityOk = AccessibilityHelper.isEnabled(this)

        val statusParts = mutableListOf<String>()
        if (!overlayOk) statusParts.add("Overlay: OFF")
        if (!accessibilityOk) statusParts.add("Accessibility: OFF")
        if (statusParts.isEmpty()) {
            statusParts.add("All permissions OK")
        }
        binding.statusText.text = "Status: ${statusParts.joinToString(" | ")}"
    }

    fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            overlayPermissionLauncher.launch(intent)
        }
    }

    fun requestAccessibilityPermission() {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        startActivity(intent)
        Toast.makeText(
            this,
            "Enable Chimera Accessibility Service in the list",
            Toast.LENGTH_LONG
        ).show()
    }

    // ── Start / Stop ──────────────────────────────────────────────────────

    private fun onStartClicked() {
        val serverUrl = binding.serverInput.text.toString().trim()
        val deviceId = binding.deviceInput.text.toString().trim()
        if (serverUrl.isEmpty() || deviceId.isEmpty()) {
            Toast.makeText(this, "Server URL and Device ID are required", Toast.LENGTH_SHORT).show()
            return
        }
        prefs.edit()
            .putString("server_url", serverUrl)
            .putString("device_id", deviceId)
            .apply()

        // Request overlay if not granted
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            requestOverlayPermission()
        }

        // Check accessibility
        if (!AccessibilityHelper.isEnabled(this)) {
            requestAccessibilityPermission()
        }

        // Request notification permission on Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                return
            }
        }

        // Launch MediaProjection permission dialog
        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projectionLauncher.launch(mpm.createScreenCaptureIntent())
        updateStatus("Requesting screen capture permission...")
    }

    private fun onStopClicked() {
        val intent = Intent(this, ScreenCaptureService::class.java)
        stopService(intent)
        if (serviceBound) {
            try {
                unbindService(serviceConnection)
            } catch (_: Throwable) {
            }
            serviceBound = false
        }
        binding.startButton.isEnabled = true
        binding.stopButton.isEnabled = false
        updateStatus("Stopped")
    }

    private fun startCapture(resultCode: Int, data: Intent) {
        val serverUrl = binding.serverInput.text.toString().trim()
        val deviceId = binding.deviceInput.text.toString().trim()

        val intent = Intent(this, ScreenCaptureService::class.java).apply {
            action = ScreenCaptureService.ACTION_START
            putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode)
            putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data)
            putExtra(ScreenCaptureService.EXTRA_SERVER_URL, serverUrl)
            putExtra(ScreenCaptureService.EXTRA_DEVICE_ID, deviceId)
        }
        ContextCompat.startForegroundService(this, intent)
        bindService(intent, serviceConnection, 0)
        serviceBound = true

        binding.startButton.isEnabled = false
        binding.stopButton.isEnabled = true
        updateStatus("Streaming to $serverUrl")
    }

    private fun updateStatus(text: String) {
        binding.statusText.text = "Status: $text"
    }
}
