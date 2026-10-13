/**
 * Accessibility Service для автоматизации UI на Android.
 * Зависит от: Android Accessibility API
 */
package com.chimera.agent.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import java.util.concurrent.ConcurrentHashMap

class AccessibilityHelper : AccessibilityService() {

    companion object {
        private const val TAG = "ChimeraA11y"

        @Volatile
        var instance: AccessibilityHelper? = null
            private set

        // Кеш найденных элементов
        val elementCache = ConcurrentHashMap<String, ElementInfo>()

        fun isEnabled(): Boolean = instance != null
    }

    data class ElementInfo(
        val resourceId: String?,
        val className: String?,
        val text: String?,
        val contentDescription: String?,
        val bounds: android.graphics.Rect?,
        val isClickable: Boolean,
        val isEditable: Boolean,
        val timestamp: Long = System.currentTimeMillis()
    )

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this

        val info = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPES_ALL_MASK
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                    AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
                    AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
            notificationTimeout = 100
        }
        serviceInfo = info

        Log.i(TAG, "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Отслеживание изменений UI для обновления кеша
        event ?: return

        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                val packageName = event.packageName?.toString() ?: return
                scope.launch {
                    updateElementCache(packageName)
                }
            }
        }
    }

    override fun onInterrupt() {
        Log.w(TAG, "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        scope.cancel()
        Log.i(TAG, "Accessibility service destroyed")
    }

    /**
     * Поиск элемента по resource ID
     */
    fun findElementById(resourceId: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val nodes = root.findAccessibilityNodeInfosByViewId(resourceId)
        return nodes?.firstOrNull()
    }

    /**
     * Поиск элемента по тексту
     */
    fun findElementByText(text: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val nodes = root.findAccessibilityNodeInfosByText(text)
        return nodes?.firstOrNull()
    }

    /**
     * Поиск элемента по content-description
     */
    fun findElementByDescription(description: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return findNodeRecursive(root) { node ->
            node.contentDescription?.toString()?.contains(description, ignoreCase = true) == true
        }
    }

    /**
     * Поиск элемента по className
     */
    fun findElementByClassName(className: String): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return findNodeRecursive(root) { node ->
            node.className?.toString() == className
        }
    }

    /**
     * Рекурсивный поиск узла по предикату
     */
    private fun findNodeRecursive(
        node: AccessibilityNodeInfo,
        predicate: (AccessibilityNodeInfo) -> Boolean
    ): AccessibilityNodeInfo? {
        if (predicate(node)) return node

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val result = findNodeRecursive(child, predicate)
            if (result != null) return result
        }
        return null
    }

    /**
     * Получение всех кликабельных элементов
     */
    fun getClickableElements(): List<ElementInfo> {
        val root = rootInActiveWindow ?: return emptyList()
        val elements = mutableListOf<ElementInfo>()
        collectElements(root, elements) { it.isClickable }
        return elements
    }

    /**
     * Получение всех полей ввода
     */
    fun getEditableElements(): List<ElementInfo> {
        val root = rootInActiveWindow ?: return emptyList()
        val elements = mutableListOf<ElementInfo>()
        collectElements(root, elements) { it.isEditable }
        return elements
    }

    /**
     * Получение всех видимых элементов
     */
    fun getAllVisibleElements(): List<ElementInfo> {
        val root = rootInActiveWindow ?: return emptyList()
        val elements = mutableListOf<ElementInfo>()
        collectElements(root, elements) { it.isVisibleToUser }
        return elements
    }

    private fun collectElements(
        node: AccessibilityNodeInfo,
        elements: MutableList<ElementInfo>,
        filter: (AccessibilityNodeInfo) -> Boolean
    ) {
        if (filter(node)) {
            val bounds = android.graphics.Rect()
            node.getBoundsInScreen(bounds)

            elements.add(
                ElementInfo(
                    resourceId = node.viewIdResourceName,
                    className = node.className?.toString(),
                    text = node.text?.toString(),
                    contentDescription = node.contentDescription?.toString(),
                    bounds = bounds,
                    isClickable = node.isClickable,
                    isEditable = node.isEditable
                )
            )
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectElements(child, elements, filter)
        }
    }

    /**
     * Клик по элементу
     */
    fun clickElement(node: AccessibilityNodeInfo): Boolean {
        return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    /**
     * Ввод текста в поле
     */
    fun inputText(node: AccessibilityNodeInfo, text: String): Boolean {
        val args = android.os.Bundle()
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    /**
     * Скролл вниз
     */
    fun scrollDown(node: AccessibilityNodeInfo? = null): Boolean {
        val target = node ?: rootInActiveWindow ?: return false
        return target.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
    }

    /**
     * Скролл вверх
     */
    fun scrollUp(node: AccessibilityNodeInfo? = null): Boolean {
        val target = node ?: rootInActiveWindow ?: return false
        return target.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
    }

    /**
     * Получение текущего package name
     */
    fun getCurrentPackage(): String? {
        val root = rootInActiveWindow ?: return null
        return root.packageName?.toString()
    }

    /**
     * Жест: назад
     */
    fun pressBack(): Boolean {
        return performGlobalAction(GLOBAL_ACTION_BACK)
    }

    /**
     * Жест: домой
     */
    fun pressHome(): Boolean {
        return performGlobalAction(GLOBAL_ACTION_HOME)
    }

    /**
     * Жест: недавние
     */
    fun pressRecents(): Boolean {
        return performGlobalAction(GLOBAL_ACTION_RECENTS)
    }

    /**
     * Обновление кеша элементов для текущего пакета
     */
    private fun updateElementCache(packageName: String) {
        val root = rootInActiveWindow ?: return
        val elements = mutableListOf<ElementInfo>()
        collectElements(root, elements) { true }

        elements.forEach { elem ->
            val key = "${packageName}:${elem.resourceId ?: elem.text ?: elem.contentDescription}"
            if (key.length > packageName.length + 1) {
                elementCache[key] = elem
            }
        }

        // Очистка старых записей (>5 мин)
        val cutoff = System.currentTimeMillis() - 300_000
        elementCache.entries.removeIf { it.value.timestamp < cutoff }
    }

    /**
     * Ожидание появления элемента
     */
    suspend fun waitForElement(
        resourceId: String? = null,
        text: String? = null,
        timeoutMs: Long = 10_000,
        pollMs: Long = 500
    ): AccessibilityNodeInfo? {
        val start = System.currentTimeMillis()

        while (System.currentTimeMillis() - start < timeoutMs) {
            val node = when {
                resourceId != null -> findElementById(resourceId)
                text != null -> findElementByText(text)
                else -> null
            }
            if (node != null) return node
            delay(pollMs)
        }
        return null
    }

    /**
     * Получение UI-дерева как JSON-строки для отправки на сервер
     */
    fun getUiTreeJson(): String {
        val root = rootInActiveWindow ?: return "[]"
        val sb = StringBuilder()
        sb.append("[")
        buildTreeJson(root, sb, 0)
        sb.append("]")
        return sb.toString()
    }

    private fun buildTreeJson(node: AccessibilityNodeInfo, sb: StringBuilder, depth: Int) {
        if (depth > 15) return

        val bounds = android.graphics.Rect()
        node.getBoundsInScreen(bounds)

        if (sb.length > 1) sb.append(",")

        sb.append("{")
        sb.append("\"id\":\"${escape(node.viewIdResourceName ?: "")}\",")
        sb.append("\"cls\":\"${escape(node.className?.toString() ?: "")}\",")
        sb.append("\"txt\":\"${escape(node.text?.toString() ?: "")}\",")
        sb.append("\"desc\":\"${escape(node.contentDescription?.toString() ?: "")}\",")
        sb.append("\"click\":${node.isClickable},")
        sb.append("\"edit\":${node.isEditable},")
        sb.append("\"vis\":${node.isVisibleToUser},")
        sb.append("\"b\":[${bounds.left},${bounds.top},${bounds.right},${bounds.bottom}]")

        if (node.childCount > 0) {
            sb.append(",\"ch\":[")
            for (i in 0 until node.childCount) {
                val child = node.getChild(i) ?: continue
                buildTreeJson(child, sb, depth + 1)
            }
            sb.append("]")
        }

        sb.append("}")
    }

    private fun escape(s: String): String {
        return s.replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
    }
}
