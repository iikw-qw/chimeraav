"""Autonomous app launch + login orchestrator.

Per-platform recipe:

  1. Resolve the package name from the account.platform.
  2. Launch the app via `adb shell monkey -p <pkg> 1` (cold start cleanly).
  3. Poll `uiautomator dump` to find login fields.
  4. Type credentials via `adb shell input text` (humanised through
     `humanTypeDevice` from devices.py when available).
  5. If a captcha screen is detected, capture the screenshot, hand it to
     `CaptchaSolver.solve_image`, then enter the answer back.
  6. Wait for the post-login indicator (timeline / home tab) to appear,
     emit a notification on the `notifications` channel.

The selectors live in PLATFORM_RECIPES so they can be tuned per app
without touching the orchestrator.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import random
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.api._hub import hub
from app.services import tools as tools_svc
from app.services.antidetect import captcha_solver, human_behavior


def _human_pause(a: float, b: float) -> float:
    """Bounded uniform jitter for inter-action pauses. Replaces a non-existent
    `human_behavior.delay_seconds` that earlier code referenced."""
    return random.uniform(a, b)

logger = logging.getLogger("chimera.auto_login")


PACKAGE_BY_PLATFORM: dict[str, str] = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "facebook": "com.facebook.katana",
    "youtube": "com.google.android.youtube",
    "threads": "com.instagram.barcelona",
    "telegram": "org.telegram.messenger",
    "reddit": "com.reddit.frontpage",
}


@dataclass(frozen=True)
class Recipe:
    """Per-platform UI selectors. resource-id substrings to match."""
    username_field: tuple[str, ...]
    password_field: tuple[str, ...]
    submit_button: tuple[str, ...]
    captcha_marker: tuple[str, ...]
    home_marker: tuple[str, ...]


PLATFORM_RECIPES: dict[str, Recipe] = {
    "instagram": Recipe(
        username_field=("login_username", "username", "log_in_username"),
        password_field=("password", "login_password"),
        submit_button=("button_text", "log_in_button", "Log in"),
        captcha_marker=("recaptcha", "challenge", "checkpoint"),
        home_marker=("tab_avatar", "feed_tab", "home_tab", "action_bar_search"),
    ),
    "tiktok": Recipe(
        username_field=("email_phone", "username_or_email"),
        password_field=("password", "passwordEditText"),
        submit_button=("login_button", "Log in"),
        captcha_marker=("captcha", "verify"),
        home_marker=("tab_home", "feed", "for_you"),
    ),
    "twitter": Recipe(
        username_field=("ocfEnterTextTextInput", "username_or_email"),
        password_field=("password", "passwordEditText"),
        submit_button=("login", "log_in"),
        captcha_marker=("arkose", "verify"),
        home_marker=("home_timeline", "tabHost"),
    ),
    "facebook": Recipe(
        username_field=("m_login_email", "username"),
        password_field=("m_login_password", "password"),
        submit_button=("login_button", "u_0_5"),
        captcha_marker=("captcha",),
        home_marker=("feed", "news_feed", "stream"),
    ),
    "youtube": Recipe(
        username_field=("identifierId",),
        password_field=("password",),
        submit_button=("identifierNext", "passwordNext"),
        captcha_marker=("captcha",),
        home_marker=("home_tab", "shorts_tab"),
    ),
    "threads": Recipe(
        username_field=("username",),
        password_field=("password",),
        submit_button=("log_in",),
        captcha_marker=("checkpoint",),
        home_marker=("feed",),
    ),
}


@dataclass
class AutoLoginResult:
    ok: bool
    stage: str
    message: str
    captcha_solved: bool = False
    duration_seconds: float = 0.0


async def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found"
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def _emit(
    *,
    account_id: str,
    device_id: str,
    stage: str,
    ok: bool | None,
    message: str,
) -> None:
    await hub.broadcast(
        "auto_login",
        {
            "account_id": account_id,
            "device_id": device_id,
            "stage": stage,
            "ok": ok,
            "message": message,
        },
    )
    if ok is True or ok is False:
        await hub.broadcast(
            "notifications",
            {
                "level": "success" if ok else "danger",
                "title": "Авто-вход" if ok else "Авто-вход не удался",
                "message": message,
                "account_id": account_id,
                "device_id": device_id,
            },
        )


async def _resolve_package(adb: str, serial: str, platform: str) -> str | None:
    base = PACKAGE_BY_PLATFORM.get(platform.lower())
    if not base:
        return None
    code, out, _ = await _run(
        [adb, "-s", serial, "shell", "pm", "list", "packages", base],
        timeout=6.0,
    )
    if code == 0 and base in out:
        return base
    return None


async def _launch(adb: str, serial: str, package: str) -> bool:
    code, _, _ = await _run(
        [adb, "-s", serial, "shell", "monkey", "-p", package, "-c",
         "android.intent.category.LAUNCHER", "1"],
        timeout=10.0,
    )
    return code == 0


async def _ui_dump(adb: str, serial: str) -> str:
    code, _, _ = await _run(
        [adb, "-s", serial, "shell", "uiautomator", "dump", "/sdcard/ui.xml"],
        timeout=10.0,
    )
    if code != 0:
        return ""
    code, out, _ = await _run(
        [adb, "-s", serial, "shell", "cat", "/sdcard/ui.xml"], timeout=5.0,
    )
    return out if code == 0 else ""


async def _find_node_bounds_ui(
    adb: str, serial: str, hints: tuple[str, ...],
) -> tuple[int, int] | None:
    """Find element via UIFinder cascade — replaces regex-based search."""
    from app.services.ui_finder import UIFinder
    ui = UIFinder(serial, adb)
    candidates: list[dict] = []
    for h in hints:
        candidates.append({"resource_id": h})
        candidates.append({"text": h})
        candidates.append({"text_contains": h})
        candidates.append({"content_desc": h})
    result = await ui.find_any(candidates)
    if result:
        return result["x"], result["y"]
    return None


async def _find_edittext_by_index_ui(
    adb: str, serial: str, index: int,
) -> tuple[int, int] | None:
    """Fallback: find the N-th EditText on screen."""
    from app.services.ui_finder import UIFinder
    ui = UIFinder(serial, adb)
    result = await ui.find(class_name="android.widget.EditText", index=index)
    if result:
        return result["x"], result["y"]
    return None


async def _tap(adb: str, serial: str, x: int, y: int, *, device_id: str | None = None) -> None:
    """Human-jittered tap that also emits cursor waypoints on the `cursor`
    WebSocket channel so the on-screen overlay shows finger movement during
    auto-login (same overlay used by warmup)."""
    jx, jy = human_behavior.jittered_tap(x, y)
    press = human_behavior.tap_press_ms()
    if device_id:
        try:
            await hub.broadcast(
                "cursor",
                {
                    "device_id": device_id,
                    "kind": "tap",
                    "x": jx,
                    "y": jy,
                    "duration_ms": press,
                },
            )
        except Exception:
            pass  # cursor overlay must never break auto-login
    # `input swipe` with same start/end gives us controlled press duration —
    # closer to a real fingertap than the binary `input tap`.
    await _run(
        [adb, "-s", serial, "shell", "input", "swipe",
         str(jx), str(jy), str(jx), str(jy), str(press)],
        timeout=6.0,
    )


async def _type(adb: str, serial: str, text: str) -> None:
    """Per-char typing with realistic delays via `typing_plan`."""
    plan = human_behavior.typing_plan(text)
    for ch, delay in plan:
        if ch == " ":
            safe = "%s"
        elif ch in ("'", '"', "\\", "`", "&", ";", "<", ">", "|", "$"):
            safe = f"\\{ch}"
        else:
            safe = ch
        await _run(
            [adb, "-s", serial, "shell", "input", "text", safe],
            timeout=4.0,
        )
        await asyncio.sleep(delay)


async def _screenshot_b64(adb: str, serial: str) -> str | None:
    code, out, _ = await _run(
        [adb, "-s", serial, "exec-out", "screencap", "-p"], timeout=8.0,
    )
    if code != 0 or not out:
        return None
    # exec-out returns raw bytes; we received them decoded — re-encode.
    return base64.b64encode(out.encode("latin-1")).decode("ascii")


async def perform_auto_login(
    *,
    account_id: str,
    device_id: str,
    serial: str,
    platform: str,
    username: str,
    password: str,
    device_platform: str = "android",
    on_log: Callable[[str], Awaitable[None]] | None = None,
    account_email: str | None = None,
    account_email_password: str | None = None,
) -> AutoLoginResult:
    if device_platform.lower() == "ios":
        return await _perform_auto_login_ios(
            account_id=account_id,
            device_id=device_id,
            udid=serial,
            platform=platform,
            username=username,
            password=password,
        )
    started = asyncio.get_event_loop().time()
    adb = tools_svc.resolve("adb")
    if adb is None:
        msg = "ADB не установлен — нечем управлять телефоном"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    recipe = PLATFORM_RECIPES.get(platform.lower())
    if not recipe:
        msg = f"Платформа {platform} пока не поддерживается авто-входом"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    package = await _resolve_package(adb, serial, platform)
    if not package:
        msg = f"Приложение {platform} не установлено на телефоне"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    await _emit(account_id=account_id, device_id=device_id,
                stage="launch", ok=None,
                message=f"Запускаю {package}…")
    if not await _launch(adb, serial, package):
        msg = "Не удалось запустить приложение"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="launch", ok=False, message=msg)
        return AutoLoginResult(False, "launch", msg)

    # Wait for the login screen to settle, with a humanised pause.
    await asyncio.sleep(_human_pause(2.5, 4.0))

    # Find username field — retry while the app boots (cascade: resource-id → text → EditText[0]).
    user_xy: tuple[int, int] | None = None
    for _ in range(12):
        user_xy = await _find_node_bounds_ui(adb, serial, recipe.username_field)
        if not user_xy:
            user_xy = await _find_edittext_by_index_ui(adb, serial, 0)
        if user_xy:
            break
        await asyncio.sleep(1.0)
    if not user_xy:
        msg = "Не нашёл поле логина — возможно нужен ручной вход"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="username_field", ok=False, message=msg)
        return AutoLoginResult(False, "username_field", msg)

    await _tap(adb, serial, *user_xy, device_id=device_id)
    await asyncio.sleep(_human_pause(0.5, 1.1))
    await _type(adb, serial, username)

    pass_xy = await _find_node_bounds_ui(adb, serial, recipe.password_field)
    if not pass_xy:
        pass_xy = await _find_edittext_by_index_ui(adb, serial, 1)
    if not pass_xy:
        msg = "Не нашёл поле пароля"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="password_field", ok=False, message=msg)
        return AutoLoginResult(False, "password_field", msg)
    await _tap(adb, serial, *pass_xy, device_id=device_id)
    await asyncio.sleep(_human_pause(0.4, 1.0))
    await _type(adb, serial, password)

    submit_xy = await _find_node_bounds_ui(adb, serial, recipe.submit_button)
    if not submit_xy:
        # Fallback: press Enter key
        await _run(
            [adb, "-s", serial, "shell", "input", "keyevent", "66"], timeout=5.0,
        )
    else:
        await _tap(adb, serial, *submit_xy, device_id=device_id)

    await _emit(account_id=account_id, device_id=device_id,
                stage="submitted", ok=None,
                message="Учётные данные отправлены, ждём ответа…")

    captcha_solved = False

    # Poll for either success indicator, captcha screen, or timeout.
    deadline = asyncio.get_event_loop().time() + 60.0
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(2.5)
        home_xy = await _find_node_bounds_ui(adb, serial, recipe.home_marker)
        if home_xy:
            duration = asyncio.get_event_loop().time() - started
            msg = f"Вошёл в @{username} на {platform}"
            await _emit(account_id=account_id, device_id=device_id,
                        stage="success", ok=True, message=msg)
            return AutoLoginResult(True, "success", msg, captcha_solved, duration)
        captcha_xy = await _find_node_bounds_ui(adb, serial, recipe.captcha_marker)
        if captcha_xy and not captcha_solved:
            await _emit(account_id=account_id, device_id=device_id,
                        stage="captcha", ok=None,
                        message="Обнаружена капча — отправляю в 2Captcha…")
            shot_b64 = await _screenshot_b64(adb, serial)
            if shot_b64:
                try:
                    answer = await captcha_solver.solve_image(shot_b64)
                    captcha_solved = True
                    if user_xy:
                        await _tap(adb, serial, *user_xy, device_id=device_id)
                        await asyncio.sleep(0.4)
                    await _type(adb, serial, answer)
                    if submit_xy:
                        await _tap(adb, serial, *submit_xy, device_id=device_id)
                    await _emit(account_id=account_id, device_id=device_id,
                                stage="captcha_solved", ok=None,
                                message="Капча решена, ждём вход…")
                except Exception as exc:  # pragma: no cover - network path
                    logger.warning("captcha solving failed: %s", exc)
                    msg = f"Не смог решить капчу: {exc}"
                    await _emit(account_id=account_id, device_id=device_id,
                                stage="captcha_failed", ok=False, message=msg)
                    return AutoLoginResult(False, "captcha_failed", msg, captcha_solved)

    msg = "Таймаут ожидания подтверждения входа"
    await _emit(account_id=account_id, device_id=device_id,
                stage="timeout", ok=False, message=msg)
    return AutoLoginResult(False, "timeout", msg, captcha_solved)


# --- iOS path ---------------------------------------------------------------

# WebDriverAgent uses the iOS accessibility tree (XCUIElementType*), not
# Android resource-ids. Hint matching falls back to the element label/name.
_IOS_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "instagram": {
        "username": ("Username", "Phone number, username", "Email"),
        "password": ("Password",),
        "submit": ("Log in", "Log In"),
        "home": ("Home", "Search", "Profile"),
    },
    "tiktok": {
        "username": ("Email or username", "Phone or email"),
        "password": ("Password",),
        "submit": ("Log in",),
        "home": ("Home", "For You"),
    },
    "twitter": {
        "username": ("Phone, email or username",),
        "password": ("Password",),
        "submit": ("Log in", "Next"),
        "home": ("Home", "For you"),
    },
    "x": {
        "username": ("Phone, email or username",),
        "password": ("Password",),
        "submit": ("Log in", "Next"),
        "home": ("Home", "For you"),
    },
    "facebook": {
        "username": ("Email address or phone number", "Email"),
        "password": ("Password",),
        "submit": ("Log in",),
        "home": ("News Feed", "Feed"),
    },
    "youtube": {
        "username": ("Email or phone",),
        "password": ("Enter your password",),
        "submit": ("Next",),
        "home": ("Home", "Shorts"),
    },
    "threads": {
        "username": ("Username",),
        "password": ("Password",),
        "submit": ("Log in",),
        "home": ("Home",),
    },
}


def _find_ios_node(source: str, hints: tuple[str, ...]) -> tuple[int, int] | None:
    """Find an XCUIElement by label/name/value substring, return tap-center.

    WDA's `/source` returns XML where each element has attributes like:
      name="Log in" label="Log in" value="" x="..." y="..." width="..." height="..."
    """
    if not source:
        return None
    pattern = re.compile(
        r'<XCUIElement[^>]*?(?:name|label|value)="([^"]+)"[^>]*?'
        r'x="(\d+)"\s+y="(\d+)"\s+width="(\d+)"\s+height="(\d+)"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(source):
        marker = match.group(1)
        if not any(h.lower() in marker.lower() for h in hints):
            continue
        x, y, w, h = map(int, match.group(2, 3, 4, 5))
        return x + w // 2, y + h // 2
    return None


async def _perform_auto_login_ios(
    *,
    account_id: str,
    device_id: str,
    udid: str,
    platform: str,
    username: str,
    password: str,
) -> AutoLoginResult:
    from app.services import ios_control

    started = asyncio.get_event_loop().time()

    if not await ios_control.available():
        msg = "WebDriverAgent не отвечает. Установите WDA по гайду в Настройки → Гайд → iOS."
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    bundle_id = ios_control.IOS_BUNDLE_BY_PLATFORM.get(platform.lower())
    if not bundle_id:
        msg = f"Платформа {platform} не поддерживается на iOS"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    hints = _IOS_HINTS.get(platform.lower())
    if not hints:
        msg = f"Подсказки UI для {platform} (iOS) ещё не заданы"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="resolve", ok=False, message=msg)
        return AutoLoginResult(False, "resolve", msg)

    await _emit(account_id=account_id, device_id=device_id,
                stage="launch", ok=None,
                message=f"Запускаю {bundle_id} через WDA…")
    res = await ios_control.open_app(udid, bundle_id)
    if not res.ok:
        await _emit(account_id=account_id, device_id=device_id,
                    stage="launch", ok=False, message=res.detail)
        return AutoLoginResult(False, "launch", res.detail)

    await asyncio.sleep(_human_pause(2.5, 4.0))

    src = await ios_control.page_source(udid)
    user_xy = _find_ios_node(src or "", hints["username"])
    if not user_xy:
        msg = "Не нашёл поле логина (iOS)"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="username_field", ok=False, message=msg)
        return AutoLoginResult(False, "username_field", msg)
    await ios_control.tap(udid, *user_xy)
    try:
        await hub.broadcast(
            "cursor",
            {"device_id": device_id, "kind": "tap",
             "x": user_xy[0], "y": user_xy[1], "duration_ms": 90},
        )
    except Exception:
        pass
    await asyncio.sleep(_human_pause(0.5, 1.1))
    await ios_control.type_text(udid, username)

    src = await ios_control.page_source(udid)
    pass_xy = _find_ios_node(src or "", hints["password"])
    if not pass_xy:
        msg = "Не нашёл поле пароля (iOS)"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="password_field", ok=False, message=msg)
        return AutoLoginResult(False, "password_field", msg)
    await ios_control.tap(udid, *pass_xy)
    await asyncio.sleep(_human_pause(0.4, 1.0))
    await ios_control.type_text(udid, password)

    submit_xy = _find_ios_node(src or "", hints["submit"])
    if not submit_xy:
        msg = "Не нашёл кнопку входа (iOS)"
        await _emit(account_id=account_id, device_id=device_id,
                    stage="submit_button", ok=False, message=msg)
        return AutoLoginResult(False, "submit_button", msg)
    await ios_control.tap(udid, *submit_xy)

    await _emit(account_id=account_id, device_id=device_id,
                stage="submitted", ok=None,
                message="Учётные данные отправлены, ждём ответа…")

    captcha_solved = False
    deadline = asyncio.get_event_loop().time() + 60.0
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(2.5)
        src = await ios_control.page_source(udid)
        if _find_ios_node(src or "", hints["home"]):
            duration = asyncio.get_event_loop().time() - started
            msg = f"Вошёл в @{username} на {platform} (iOS)"
            await _emit(account_id=account_id, device_id=device_id,
                        stage="success", ok=True, message=msg)
            return AutoLoginResult(True, "success", msg, captcha_solved, duration)

    msg = "Таймаут ожидания подтверждения входа (iOS)"
    await _emit(account_id=account_id, device_id=device_id,
                stage="timeout", ok=False, message=msg)
    return AutoLoginResult(False, "timeout", msg, captcha_solved)
