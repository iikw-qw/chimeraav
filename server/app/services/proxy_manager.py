"""
Прокси-менеджер: ротация, проверка, интеграция с провайдерами.
Зависит от: config, redis_client, httpx
"""

import asyncio
import random
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
import structlog

from app.config import settings
from app.services.redis_client import redis_client

logger = structlog.get_logger()


class ProxyManager:

    async def check_proxy(self, proxy_url: str) -> Dict[str, Any]:
        """Проверка работоспособности прокси"""
        result = {
            "url": proxy_url,
            "working": False,
            "response_time_ms": 0,
            "external_ip": None,
            "dns_leak": False,
            "webrtc_leak": False,
        }

        try:
            start = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
                response = await client.get("https://api.ipify.org?format=json")
                elapsed = (asyncio.get_event_loop().time() - start) * 1000

                if response.status_code == 200:
                    result["working"] = True
                    result["response_time_ms"] = int(elapsed)
                    result["external_ip"] = response.json().get("ip")

            # Проверка DNS утечки
            result["dns_leak"] = await self._check_dns_leak(proxy_url)

            logger.info("proxy.checked", url=proxy_url, working=result["working"], ip=result["external_ip"])
        except Exception as e:
            logger.warning("proxy.check_failed", url=proxy_url, error=str(e))

        return result

    async def _check_dns_leak(self, proxy_url: str) -> bool:
        """Проверка DNS утечки через прокси"""
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
                # Запрос к сервису проверки DNS
                response = await client.get("https://dnsleaktest.com/")
                return response.status_code != 200
        except Exception:
            return True

    async def get_proxy_for_device(self, device_id: str) -> Optional[str]:
        """Получить назначенный прокси для устройства"""
        return await redis_client.hget("chimera:device_proxies", device_id)

    async def assign_proxy(self, device_id: str, proxy_url: str):
        """Назначить прокси устройству"""
        await redis_client.hset("chimera:device_proxies", device_id, proxy_url)
        logger.info("proxy.assigned", device_id=device_id, proxy_url=proxy_url)

    async def rotate_proxy(self, device_id: str, proxy_list: List[str]) -> Optional[str]:
        """Ротация прокси для устройства из списка"""
        if not proxy_list:
            return None

        current = await self.get_proxy_for_device(device_id)
        available = [p for p in proxy_list if p != current]
        if not available:
            available = proxy_list

        new_proxy = random.choice(available)

        # Проверяем работоспособность перед назначением
        check = await self.check_proxy(new_proxy)
        if check["working"]:
            await self.assign_proxy(device_id, new_proxy)
            logger.info("proxy.rotated", device_id=device_id, new_proxy=new_proxy, ip=check["external_ip"])
            return new_proxy

        # Если первый не работает, пробуем остальные
        for proxy in available:
            check = await self.check_proxy(proxy)
            if check["working"]:
                await self.assign_proxy(device_id, proxy)
                return proxy

        logger.error("proxy.no_working", device_id=device_id, tried=len(available))
        return None

    async def get_all_proxies(self) -> Dict[str, str]:
        """Получить все назначенные прокси"""
        return await redis_client.hgetall("chimera:device_proxies")

    async def remove_proxy(self, device_id: str):
        """Удалить прокси с устройства"""
        await redis_client.hdel("chimera:device_proxies", device_id)

    async def batch_check(self, proxy_list: List[str]) -> List[Dict[str, Any]]:
        """Массовая проверка списка прокси"""
        tasks = [self.check_proxy(url) for url in proxy_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def generate_iptables_rules(self, device_ip: str, proxy_ip: str, proxy_port: int) -> str:
        """Генерация iptables правил для прокси на роутере (iOS)"""
        rules = f"""# Proxy rules for iOS device {device_ip}
iptables -t nat -A PREROUTING -s {device_ip} -p tcp --dport 80 -j DNAT --to-destination {proxy_ip}:{proxy_port}
iptables -t nat -A PREROUTING -s {device_ip} -p tcp --dport 443 -j DNAT --to-destination {proxy_ip}:{proxy_port}
iptables -t nat -A POSTROUTING -j MASQUERADE"""
        return rules


proxy_manager = ProxyManager()
