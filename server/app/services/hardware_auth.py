"""
Авторизация привязанная к железу: hardware ID, информация о хосте, метрики.
"""

import hashlib
import platform
import socket
import uuid

import structlog

logger = structlog.get_logger(__name__)

_psutil_available = False
try:
    import psutil
    _psutil_available = True
except ImportError:
    logger.warning("psutil not installed — host metrics will be unavailable")


def get_hardware_id() -> str:
    parts = []
    mac = ':'.join(f'{(uuid.getnode() >> i) & 0xff:02x}' for i in range(0, 48, 8))
    parts.append(mac)
    parts.append(socket.gethostname())
    parts.append(platform.processor() or "unknown_cpu")
    parts.append(platform.system() + platform.release())
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_host_info() -> dict:
    ram_gb = 0
    mac_address = ':'.join(f'{(uuid.getnode() >> i) & 0xff:02x}' for i in range(0, 48, 8))
    if _psutil_available:
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    return {
        "hardware_id": get_hardware_id(),
        "hostname": socket.gethostname(),
        "os_name": platform.system(),
        "os_version": platform.release(),
        "cpu_info": platform.processor() or "unknown",
        "ram_gb": ram_gb,
        "mac_address": mac_address,
    }


def get_host_metrics() -> dict:
    if not _psutil_available:
        return {
            "cpu_percent": 0,
            "ram_percent": 0,
            "disk_percent": 0,
            "network_sent_mb": 0,
            "network_recv_mb": 0,
            "uptime_seconds": 0,
        }
    net = psutil.net_io_counters()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:\\').percent,
        "network_sent_mb": round(net.bytes_sent / 1048576, 1),
        "network_recv_mb": round(net.bytes_recv / 1048576, 1),
        "uptime_seconds": int(psutil.boot_time()),
    }
