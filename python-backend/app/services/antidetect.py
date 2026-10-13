"""Antidetect — rotating proxies, device fingerprints, captcha solving, human behavior."""

from __future__ import annotations

import asyncio
import math
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models.device import Device
from app.models.proxy import Proxy

# Real OUI prefixes (Samsung / Xiaomi / Google / Huawei / OnePlus).
_VENDOR_OUIS = [
    "00:15:B9",
    "28:6C:07",
    "3C:5A:B4",
    "40:4E:36",
    "50:C7:BF",
    "A0:8D:16",
    "B4:CE:F6",
    "F0:EE:BB",
]

_BUILD_PROP_TEMPLATE = """\
ro.product.manufacturer={manufacturer}
ro.product.brand={brand}
ro.product.model={model}
ro.product.device={device}
ro.build.fingerprint={fingerprint}
ro.build.display.id={display_id}
ro.build.version.release={android_version}
ro.build.version.sdk={sdk}
"""

_DEVICE_PROFILES = [
    {
        "manufacturer": "samsung",
        "brand": "samsung",
        "model": "SM-S911B",
        "device": "dm1q",
        "android_version": "14",
        "sdk": 34,
    },
    {
        "manufacturer": "Google",
        "brand": "google",
        "model": "Pixel 7",
        "device": "panther",
        "android_version": "14",
        "sdk": 34,
    },
    {
        "manufacturer": "Xiaomi",
        "brand": "Xiaomi",
        "model": "23049PCD8G",
        "device": "marble",
        "android_version": "13",
        "sdk": 33,
    },
]


def _luhn_imei() -> str:
    base = [random.randint(0, 9) for _ in range(14)]
    total = 0
    for i, digit in enumerate(base):
        if i % 2 == 1:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += digit
    check = (10 - total % 10) % 10
    return "".join(str(d) for d in base) + str(check)


def _random_mac() -> str:
    oui = random.choice(_VENDOR_OUIS)
    tail = ":".join(f"{random.randint(0, 255):02X}" for _ in range(3))
    return f"{oui}:{tail}"


def _random_android_id() -> str:
    return f"{random.getrandbits(64):016x}"


class ProxyManager:
    async def rotate(self, device_id: str) -> Proxy | None:
        async with SessionLocal() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")

            stmt = select(Proxy).where(
                Proxy.is_active.is_(True),
                Proxy.leak_check_passed.is_(True),
            )
            candidates = [
                p for p in (await session.execute(stmt)).scalars().all()
                if p.id != device.proxy_id
            ]
            if not candidates:
                return None
            chosen = random.choice(candidates)
            device.proxy_id = chosen.id
            await session.commit()
            return chosen

    async def check_proxy(self, proxy_id: str) -> dict[str, Any]:
        async with SessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if proxy is None:
                raise ValueError(f"Proxy {proxy_id} not found")
            url = self._format_url(proxy)

        async with httpx.AsyncClient(timeout=10.0, proxy=url) as client:
            try:
                response = await client.get("https://api.ipify.org?format=json")
                ok = response.status_code == 200
                ip = response.json().get("ip") if ok else None
            except Exception as exc:
                ok = False
                ip = None
                error: str | None = str(exc)
            else:
                error = None

        async with SessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if proxy is not None:
                proxy.leak_check_passed = ok
                proxy.last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()

        return {"proxy_id": proxy_id, "ok": ok, "ip": ip, "error": error}

    async def check_all(self) -> list[dict[str, Any]]:
        async with SessionLocal() as session:
            rows = list(
                (await session.execute(select(Proxy).where(Proxy.is_active.is_(True))))
                .scalars()
                .all()
            )
        results = await asyncio.gather(
            *(self.check_proxy(p.id) for p in rows), return_exceptions=True
        )
        return [r for r in results if isinstance(r, dict)]

    @staticmethod
    def _format_url(proxy: Proxy) -> str:
        auth = ""
        if proxy.username and proxy.password:
            auth = f"{proxy.username}:{proxy.password}@"
        return f"{proxy.protocol}://{auth}{proxy.address}:{proxy.port}"


class FingerprintManager:
    async def rotate(self, device_id: str) -> dict[str, Any]:
        profile = random.choice(_DEVICE_PROFILES)
        android_id = _random_android_id()
        imei = _luhn_imei()
        mac = _random_mac()
        device_uuid = str(uuid.uuid4())

        fingerprint = (
            f"{profile['brand']}/{profile['device']}/"
            f"{profile['model']}:{profile['android_version']}/"
            f"UP1A.{random.randint(10000, 99999)}.001/"
            f"{random.randint(10000000, 99999999)}:user/release-keys"
        )
        build_prop = _BUILD_PROP_TEMPLATE.format(
            manufacturer=profile["manufacturer"],
            brand=profile["brand"],
            model=profile["model"],
            device=profile["device"],
            fingerprint=fingerprint,
            display_id=f"UP1A.{random.randint(10000, 99999)}.001",
            android_version=profile["android_version"],
            sdk=profile["sdk"],
        )

        async with SessionLocal() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")
            await session.commit()

        return {
            "device_id": device_id,
            "uuid": device_uuid,
            "android_id": android_id,
            "imei": imei,
            "mac": mac,
            "profile": profile,
            "build_prop": build_prop,
        }


class CaptchaSolver:
    """Lightweight 2Captcha API client."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("CHIMERA_2CAPTCHA_KEY") or ""
        self._base = "https://2captcha.com"

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        return await self._solve(
            {"method": "userrecaptcha", "googlekey": site_key, "pageurl": page_url}
        )

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        return await self._solve(
            {"method": "hcaptcha", "sitekey": site_key, "pageurl": page_url}
        )

    async def solve_image(self, image_base64: str) -> str:
        return await self._solve({"method": "base64", "body": image_base64})

    async def _solve(self, params: dict[str, Any]) -> str:
        if not self._api_key:
            raise RuntimeError("2Captcha API key is not configured")

        async with httpx.AsyncClient(timeout=120.0) as client:
            submit = await client.post(
                f"{self._base}/in.php",
                data={"key": self._api_key, "json": 1, **params},
            )
            submit.raise_for_status()
            payload = submit.json()
            if payload.get("status") != 1:
                raise RuntimeError(f"2Captcha submit failed: {payload}")
            request_id = payload["request"]

            for _ in range(30):
                await asyncio.sleep(5.0)
                poll = await client.get(
                    f"{self._base}/res.php",
                    params={
                        "key": self._api_key,
                        "action": "get",
                        "id": request_id,
                        "json": 1,
                    },
                )
                data = poll.json()
                if data.get("status") == 1:
                    return str(data["request"])
                if data.get("request") != "CAPCHA_NOT_READY":
                    raise RuntimeError(f"2Captcha error: {data}")

        raise TimeoutError("Captcha solving timed out")


BehaviorProfile = Literal["calm", "normal", "fast"]


@dataclass(frozen=True)
class CursorWaypoint:
    x: int
    y: int
    t_ms: int  # offset from gesture start


class HumanBehaviorEngine:
    """Pure planner for human-like input. No I/O — consumers execute the plan via adb.

    Randomises tap position, swipe duration, typing cadence, and produces a
    bezier path of cursor waypoints for the frontend overlay so the user sees
    a finger trail that looks like a real person scrolling.
    """

    _PROFILES: dict[str, dict[str, float]] = {
        # tap_jitter_px, dwell seconds (log-uniform), swipe ms-per-pixel,
        # endpoint jitter fraction, typo chance, idle chance
        "calm":   {"tap_jitter": 5.0, "dwell_min": 0.18, "dwell_max": 1.4, "ms_per_px": 1.4, "end_jitter": 0.04, "typo": 0.010, "idle": 0.08},
        "normal": {"tap_jitter": 7.0, "dwell_min": 0.10, "dwell_max": 0.9, "ms_per_px": 1.0, "end_jitter": 0.06, "typo": 0.020, "idle": 0.05},
        "fast":   {"tap_jitter": 9.0, "dwell_min": 0.05, "dwell_max": 0.5, "ms_per_px": 0.7, "end_jitter": 0.08, "typo": 0.030, "idle": 0.02},
    }

    def __init__(self, profile: BehaviorProfile = "normal") -> None:
        self.profile_name: BehaviorProfile = profile if profile in self._PROFILES else "normal"
        self._p = self._PROFILES[self.profile_name]

    # --- Tap ---------------------------------------------------------------

    def jittered_tap(self, x: int, y: int) -> tuple[int, int]:
        sigma = self._p["tap_jitter"] / 2
        return (
            int(x + random.gauss(0, sigma)),
            int(y + random.gauss(0, sigma)),
        )

    def tap_press_ms(self) -> int:
        # realistic finger press window 55-180 ms, log-biased to the short end
        return int(55 + random.expovariate(1 / 45.0))

    # --- Timing ------------------------------------------------------------

    def dwell_seconds(self) -> float:
        a, b = self._p["dwell_min"], self._p["dwell_max"]
        return math.exp(random.uniform(math.log(a), math.log(b)))

    def reading_pause(self, text_len: int) -> float:
        # ~5 cps reading speed, with ±25% variance, plus a base "orient" delay
        return 0.6 + (text_len / 5.0) * random.uniform(0.75, 1.25)

    def should_idle(self) -> bool:
        return random.random() < self._p["idle"]

    def idle_seconds(self) -> float:
        return math.exp(random.uniform(0.0, math.log(15.0)))

    def daytime_factor(self, hour: int | None = None) -> float:
        """Activity multiplier by hour of day. Peak ~20:00, trough ~04:00."""
        if hour is None:
            hour = datetime.now().hour
        phase = (hour - 20) / 24.0 * 2 * math.pi
        return 0.35 + 0.65 * (math.cos(phase) + 1) / 2

    # --- Swipe -------------------------------------------------------------

    def swipe_duration_ms(self, dx: int, dy: int) -> int:
        dist = math.hypot(dx, dy)
        base = dist * self._p["ms_per_px"]
        jittered = base * random.uniform(0.82, 1.22)
        return int(max(180, min(1500, jittered)))

    def humanize_swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> dict[str, Any]:
        """Return an adb-linear-compatible swipe with end jitter + a bezier
        waypoint path for the UI overlay.

        adb `input swipe` is linear, but we jitter the endpoint and add a
        mid-control-point so the rendered cursor curve looks organic.
        """
        end_j = self._p["end_jitter"]
        dist = max(1.0, math.hypot(x2 - x1, y2 - y1))
        ex_x = int(x2 + random.gauss(0, dist * end_j))
        ex_y = int(y2 + random.gauss(0, dist * end_j))
        duration = self.swipe_duration_ms(ex_x - x1, ex_y - y1)

        # Perpendicular control point for the visual bezier (not sent to adb).
        perp_x = -(ex_y - y1) / dist
        perp_y = (ex_x - x1) / dist
        curve = random.uniform(0.04, 0.12) * dist * random.choice([-1, 1])
        ctrl_x = int((x1 + ex_x) / 2 + perp_x * curve)
        ctrl_y = int((y1 + ex_y) / 2 + perp_y * curve)

        waypoints = self._bezier_waypoints(
            (x1, y1), (ctrl_x, ctrl_y), (ex_x, ex_y), duration_ms=duration, steps=18
        )
        return {
            "x1": x1,
            "y1": y1,
            "x2": ex_x,
            "y2": ex_y,
            "duration_ms": duration,
            "waypoints": [w.__dict__ for w in waypoints],
        }

    @staticmethod
    def _bezier_waypoints(
        p0: tuple[int, int],
        p1: tuple[int, int],
        p2: tuple[int, int],
        *,
        duration_ms: int,
        steps: int,
    ) -> list[CursorWaypoint]:
        """Quadratic bezier with an ease-in-out time mapping."""
        pts: list[CursorWaypoint] = []
        for i in range(steps + 1):
            u = i / steps
            # ease-in-out via smoothstep so the finger accelerates then settles
            t = u * u * (3 - 2 * u)
            inv = 1 - t
            x = inv * inv * p0[0] + 2 * inv * t * p1[0] + t * t * p2[0]
            y = inv * inv * p0[1] + 2 * inv * t * p1[1] + t * t * p2[1]
            pts.append(CursorWaypoint(int(x), int(y), int(u * duration_ms)))
        return pts

    # --- Typing ------------------------------------------------------------

    def typing_plan(self, text: str) -> list[tuple[str, float]]:
        """Return (char, post_delay_seconds). Caller sends each via adb input text."""
        plan: list[tuple[str, float]] = []
        for ch in text:
            plan.append((ch, self._char_delay(ch)))
        return plan

    def _char_delay(self, ch: str) -> float:
        base = random.uniform(0.055, 0.14)
        if ch == " ":
            base *= 1.35
        elif ch in ".,!?;:":
            base *= 1.7
        elif ch.isupper():
            base *= 1.15
        if random.random() < 0.035:
            base += random.uniform(0.25, 0.85)  # think-pause
        return base


proxy_manager = ProxyManager()
fingerprint_manager = FingerprintManager()
captcha_solver = CaptchaSolver()
human_behavior = HumanBehaviorEngine("normal")


def set_behavior_profile(profile: BehaviorProfile) -> None:
    """Rebind the module-level engine (called by settings change handler)."""
    global human_behavior
    human_behavior = HumanBehaviorEngine(profile)


def set_captcha_key(api_key: str) -> None:
    """Rotate the 2Captcha key at runtime (settings UI)."""
    global captcha_solver
    captcha_solver = CaptchaSolver(api_key or None)
