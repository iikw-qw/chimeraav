/**
 * Проверка внешнего IP-адреса через api.ipify.org.
 * Зависит от: OkHttp
 */
package com.chimera.agent.util

import android.util.Log
import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class IpChecker(
    private val checkIntervalMs: Long = 60_000L
) {
    companion object {
        private const val TAG = "IpChecker"
        private const val IPIFY_URL = "https://api.ipify.org?format=text"
        private const val IPIFY_JSON_URL = "https://api.ipify.org?format=json"
        private val FALLBACK_URLS = listOf(
            "https://api.my-ip.io/v2/ip.txt",
            "https://checkip.amazonaws.com",
            "https://ifconfig.me/ip",
        )
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val currentIp = AtomicReference<String?>(null)
    private var onIpChanged: ((String) -> Unit)? = null
    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    /**
     * Получение текущего внешнего IP
     */
    fun getCurrentIp(): String? = currentIp.get()

    /**
     * Установка callback при изменении IP
     */
    fun setOnIpChanged(callback: (String) -> Unit) {
        onIpChanged = callback
    }

    /**
     * Однократная проверка внешнего IP
     */
    suspend fun checkIp(): String? = withContext(Dispatchers.IO) {
        // Основной сервис
        var ip = fetchIp(IPIFY_URL)

        // Fallback если основной не ответил
        if (ip == null) {
            for (url in FALLBACK_URLS) {
                ip = fetchIp(url)
                if (ip != null) break
            }
        }

        if (ip != null) {
            val prevIp = currentIp.getAndSet(ip)
            if (prevIp != null && prevIp != ip) {
                Log.i(TAG, "External IP changed: $prevIp -> $ip")
                onIpChanged?.invoke(ip)
            } else if (prevIp == null) {
                Log.i(TAG, "External IP detected: $ip")
                onIpChanged?.invoke(ip)
            }
        }

        ip
    }

    /**
     * Запуск периодической проверки IP
     */
    fun startPeriodicCheck() {
        stopPeriodicCheck()
        job = scope.launch {
            while (isActive) {
                try {
                    checkIp()
                } catch (e: Exception) {
                    Log.e(TAG, "IP check failed: ${e.message}")
                }
                delay(checkIntervalMs)
            }
        }
        Log.i(TAG, "Periodic IP check started (interval: ${checkIntervalMs}ms)")
    }

    /**
     * Остановка периодической проверки
     */
    fun stopPeriodicCheck() {
        job?.cancel()
        job = null
    }

    /**
     * Проверка VPN/прокси (сравнение локального и внешнего IP)
     */
    suspend fun isVpnActive(): Boolean = withContext(Dispatchers.IO) {
        val externalIp = checkIp() ?: return@withContext false

        try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces()
            val localIps = mutableListOf<String>()

            while (interfaces.hasMoreElements()) {
                val ni = interfaces.nextElement()
                val addresses = ni.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (!addr.isLoopbackAddress && addr is java.net.Inet4Address) {
                        localIps.add(addr.hostAddress ?: "")
                    }
                }
            }

            // Если внешний IP не совпадает ни с одним локальным — VPN/прокси активен
            !localIps.contains(externalIp)
        } catch (e: Exception) {
            Log.e(TAG, "VPN check failed: ${e.message}")
            false
        }
    }

    private fun fetchIp(url: String): String? {
        return try {
            val request = Request.Builder()
                .url(url)
                .header("User-Agent", "Chimera-Agent/5.0")
                .build()

            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string()?.trim()
                // Валидация формата IP
                if (body != null && body.matches(Regex("\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}"))) {
                    body
                } else {
                    null
                }
            } else {
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch IP from $url: ${e.message}")
            null
        }
    }

    fun destroy() {
        stopPeriodicCheck()
        scope.cancel()
    }
}
