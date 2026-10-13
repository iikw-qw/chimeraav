"""Platform Login — cascade UI element finder + auto-login for social apps.

BUG 1 FIX: replaces fragile resource-id-only lookup with a 3-level cascade:
  1. uiautomator dump + resource-id match
  2. text match (multi-language variants)
  3. class + index fallback (e.g. 2nd EditText = password)

Also adds smart waiting (poll until element appears) instead of fixed sleep.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.api._hub import hub
from app.services import tools as tools_svc
from app.services.antidetect import human_behavior

logger = logging.getLogger("chimera.platform_login")


ELEMENTS: dict[str, dict[str, Any]] = {
    "instagram": {
        "package": "com.instagram.android",
        "username": {
            "resource_ids": [
                "com.instagram.android:id/login_username",
                "com.instagram.android:id/username",
                "com.instagram.android:id/log_in_username",
            ],
            "texts": [
                "Phone number, username, or email",
                "Phone number, username or email address",
                "Username, email, or phone number",
                "Телефон, имя пользователя или эл. адрес",
                "Phone number, username, or email address",
            ],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "resource_ids": [
                "com.instagram.android:id/password",
                "com.instagram.android:id/login_password",
            ],
            "texts": ["Password", "Пароль"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {
            "resource_ids": [
                "com.instagram.android:id/log_in_button",
                "com.instagram.android:id/button_text",
            ],
            "texts": ["Log in", "Log In", "Войти"],
        },
        "dismiss_popups": ["Not Now", "Not now", "Не сейчас", "Skip", "Save Info", "Save"],
        "home_indicators": ["Home", "Главная", "tab_avatar", "feed_tab"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "It's me", "Yes, it's me", "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "tiktok": {
        "package": "com.zhiliaoapp.musically",
        "pre_login": {"texts": ["Use phone / email / username", "Use phone/email/username",
                                "Log in with phone/email/username"]},
        "username": {
            "texts": ["Email or username", "Phone / Email / Username", "Phone or email or username"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "texts": ["Password", "Enter password"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {"texts": ["Log in", "Log In"]},
        "home_indicators": ["Home", "For You", "Following", "tab_home"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "facebook": {
        "package": "com.facebook.katana",
        "username": {
            "resource_ids": [
                "com.facebook.katana:id/login_username",
                "com.facebook.katana:id/m_login_email",
            ],
            "texts": ["Mobile number or email", "Email or phone number",
                      "Email address or phone number", "Номер телефона или эл. адрес"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "resource_ids": [
                "com.facebook.katana:id/login_password",
                "com.facebook.katana:id/m_login_password",
            ],
            "texts": ["Password", "Пароль"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {
            "resource_ids": [
                "com.facebook.katana:id/login_login",
                "com.facebook.katana:id/u_0_5",
            ],
            "texts": ["Log In", "LOG IN", "Войти"],
        },
        "home_indicators": ["News Feed", "What's on your mind", "news_feed"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "It's me", "Yes, it's me", "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "twitter": {
        "package": "com.twitter.android",
        "pre_login": {"texts": ["Sign in", "Log in"]},
        "username": {
            "resource_ids": ["com.twitter.android:id/login_identifier",
                             "com.twitter.android:id/ocfEnterTextTextInput"],
            "texts": ["Phone, email, or username", "Phone, email or username"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "next_button": {"texts": ["Next", "Далее"]},
        "password": {
            "texts": ["Password", "Пароль"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "login_button": {"texts": ["Log in", "Log In", "Войти"]},
        "home_indicators": ["Home", "What's happening", "home_timeline"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "linkedin": {
        "package": "com.linkedin.android",
        "username": {
            "texts": ["Email or phone", "Email or Phone"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "texts": ["Password"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {"texts": ["Sign in", "Sign In"]},
        "home_indicators": ["Home", "Feed"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "vk": {
        "package": "com.vkontakte.android",
        "username": {
            "texts": ["Телефон или почта", "Phone or email"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "texts": ["Пароль", "Password"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {"texts": ["Войти", "Sign in"]},
        "home_indicators": ["Новости", "News"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
    "reddit": {
        "package": "com.reddit.frontpage",
        "pre_login": {"texts": ["Log In", "Log in"]},
        "username": {
            "texts": ["Username", "Email"],
            "class_fallback": ("android.widget.EditText", 0),
        },
        "password": {
            "texts": ["Password"],
            "class_fallback": ("android.widget.EditText", 1),
        },
        "login_button": {"texts": ["Log In", "Continue"]},
        "home_indicators": ["Home", "Popular"],
        "confirm_code": {
            "texts": ["Confirm", "Continue", "Submit", "Next", "Verify", "Done",
                      "Подтвердить", "Продолжить", "Далее", "Войти", "Готово",
                      "Send code", "Отправить код"],
        },
        "code_input": {
            "class_fallback": ("android.widget.EditText", 0),
            "texts": ["Enter code", "Verification code", "Security code",
                      "Введите код", "Код подтверждения"],
        },
    },
}


async def _run(cmd: list[str], timeout: float = 10.0) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found"
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timeout"
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


class PlatformLogin:
    """Cascade login orchestrator for Android social apps."""

    def __init__(self, serial: str):
        self.serial = serial
        self._adb_path: str | None = None
        self._ui_finder: Any = None

    def _get_ui_finder(self) -> Any:
        if self._ui_finder is None:
            from app.services.ui_finder import UIFinder
            self._ui_finder = UIFinder(self.serial, self.adb)
        return self._ui_finder

    @property
    def adb(self) -> str:
        if self._adb_path is None:
            self._adb_path = tools_svc.resolve("adb") or "adb"
        return self._adb_path

    async def _adb_shell(self, cmd: str) -> str:
        code, out = await _run(
            [self.adb, "-s", self.serial, "shell", cmd], timeout=10.0,
        )
        return out

    async def _ui_dump(self) -> str:
        await _run(
            [self.adb, "-s", self.serial, "shell",
             "uiautomator", "dump", "/sdcard/ui.xml"],
            timeout=10.0,
        )
        code, xml = await _run(
            [self.adb, "-s", self.serial, "shell", "cat", "/sdcard/ui.xml"],
            timeout=5.0,
        )
        return xml if code == 0 else ""

    @staticmethod
    def _config_to_candidates(element_config: dict) -> list[dict]:
        """Convert element config dict into UIFinder candidates list."""
        candidates: list[dict] = []
        for rid in element_config.get("resource_ids", []):
            candidates.append({"resource_id": rid})
        for txt in element_config.get("texts", []):
            candidates.append({"text": txt})
        for txt in element_config.get("texts", []):
            candidates.append({"content_desc": txt})
        for txt in element_config.get("texts", []):
            candidates.append({"text_contains": txt})
        fb = element_config.get("class_fallback")
        if fb:
            candidates.append({"class_name": fb[0], "index": fb[1]})
        return candidates

    async def _find_element_ui(self, element_config: dict) -> dict | None:
        """Find element using UIFinder cascade."""
        ui = self._get_ui_finder()
        candidates = self._config_to_candidates(element_config)
        return await ui.find_any(candidates)

    async def _wait_for_element(self, element_config: dict,
                                timeout: float = 15.0) -> dict | None:
        ui = self._get_ui_finder()
        candidates = self._config_to_candidates(element_config)
        return await ui.wait_find(candidates, timeout=timeout)

    async def _type_text(self, text: str) -> None:
        plan = human_behavior.typing_plan(text)
        for ch, delay in plan:
            if ch == " ":
                safe = "%s"
            elif ch in ("'", '"', "\\", "`", "&", ";", "<", ">", "|", "$"):
                safe = f"\\{ch}"
            else:
                safe = ch
            await _run(
                [self.adb, "-s", self.serial, "shell", "input", "text", safe],
                timeout=4.0,
            )
            await asyncio.sleep(delay)

    async def _tap(self, x: int, y: int, *, device_id: str | None = None) -> None:
        jx, jy = human_behavior.jittered_tap(x, y)
        press = human_behavior.tap_press_ms()
        if device_id:
            try:
                await hub.broadcast("cursor", {
                    "device_id": device_id, "kind": "tap",
                    "x": jx, "y": jy, "duration_ms": press,
                })
            except Exception:
                pass
        await _run(
            [self.adb, "-s", self.serial, "shell", "input", "swipe",
             str(jx), str(jy), str(jx), str(jy), str(press)],
            timeout=6.0,
        )

    async def login(self, platform: str, username: str, password: str,
                    *, device_id: str | None = None,
                    account_id: str | None = None,
                    account_email: str | None = None,
                    account_email_password: str | None = None) -> dict:
        config = ELEMENTS.get(platform.lower())
        if not config:
            return {"success": False, "error": f"Платформа {platform} не поддерживается"}

        package = config["package"]

        await self._adb_shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        await asyncio.sleep(4)

        ui = self._get_ui_finder()
        if await ui.has_text(config.get("home_indicators", [])):
            await self._notify(device_id, account_id, True,
                               f"Уже залогинен в {platform}")
            return {"success": True, "method": "already_logged"}

        if "pre_login" in config:
            node = await self._find_element_ui(config["pre_login"])
            if node:
                await self._tap(node["x"], node["y"], device_id=device_id)
                await asyncio.sleep(2)

        el = await self._wait_for_element(config["username"], timeout=15)
        if not el:
            msg = "Поле username не найдено после 15 секунд ожидания"
            await self._notify(device_id, account_id, False, msg)
            return {"success": False, "error": msg}
        await self._tap(el["x"], el["y"], device_id=device_id)
        await asyncio.sleep(0.3)
        await self._type_text(username)
        await asyncio.sleep(0.5)

        if "next_button" in config:
            node = await self._find_element_ui(config["next_button"])
            if node:
                await self._tap(node["x"], node["y"], device_id=device_id)
                await asyncio.sleep(2)

        el = await self._wait_for_element(config["password"], timeout=10)
        if not el:
            msg = "Поле пароля не найдено"
            await self._notify(device_id, account_id, False, msg)
            return {"success": False, "error": msg}
        await self._tap(el["x"], el["y"], device_id=device_id)
        await asyncio.sleep(0.3)
        await self._type_text(password)
        await asyncio.sleep(0.5)

        el = await self._wait_for_element(config.get("login_button", {}), timeout=10)
        if el:
            await self._tap(el["x"], el["y"], device_id=device_id)
        else:
            await self._adb_shell("input keyevent 66")
        await asyncio.sleep(6)

        screen_text = (await ui.get_all_text()).lower()
        code_keywords = [
            "confirm", "verification", "code", "verify", "подтвердите",
            "we sent", "enter the code", "введите код", "check your email",
        ]
        if any(w in screen_text for w in code_keywords):
            if account_email and account_email_password:
                from app.services.email_sync import EmailSync

                logger.info("Verification screen detected — fetching code from %s", account_email)
                sync = EmailSync()
                code = await sync.fetch_auth_code(
                    account_email, account_email_password, platform, timeout=120,
                )
                if code:
                    code_cfg = config.get("code_input", {
                        "class_fallback": ("android.widget.EditText", 0),
                    })
                    code_field = await self._wait_for_element(code_cfg, timeout=10)
                    if code_field:
                        await self._tap(code_field["x"], code_field["y"], device_id=device_id)
                        await asyncio.sleep(0.3)
                        await self._type_text(code)
                        await asyncio.sleep(0.5)

                        confirm_cfg = config.get("confirm_code", {})
                        ui = self._get_ui_finder()
                        confirm = await ui.wait_find(
                            self._config_to_candidates(confirm_cfg), timeout=10
                        ) if confirm_cfg else None
                        if confirm:
                            await self._tap(confirm["x"], confirm["y"], device_id=device_id)
                        else:
                            await self._adb_shell("input keyevent 66")
                        await asyncio.sleep(5)
                        xml = await self._ui_dump()

        ui = self._get_ui_finder()
        for popup_text in config.get("dismiss_popups", []):
            node = await ui.find(text=popup_text)
            if node:
                await self._tap(node["x"], node["y"], device_id=device_id)
                await asyncio.sleep(1)

        if await ui.has_text(config.get("home_indicators", [])):
            msg = f"Вошёл в @{username} на {platform}"
            await self._notify(device_id, account_id, True, msg)
            return {"success": True, "method": "ui_automation"}

        screen_text = (await ui.get_all_text()).lower()
        if any(w in screen_text for w in
               ["captcha", "verify", "confirm", "security", "challenge"]):
            msg = "Капча/верификация — нужен 2Captcha или ручной ввод"
            await self._notify(device_id, account_id, False, msg)
            return {"success": False, "error": msg}
        if any(w in screen_text for w in
               ["incorrect", "wrong", "invalid", "ошибка"]):
            msg = "Неверный логин или пароль"
            await self._notify(device_id, account_id, False, msg)
            return {"success": False, "error": msg}

        msg = "Не удалось подтвердить вход"
        await self._notify(device_id, account_id, False, msg)
        return {"success": False, "error": msg}

    async def _notify(self, device_id: str | None, account_id: str | None,
                      success: bool, message: str) -> None:
        try:
            await hub.broadcast("notifications", {
                "level": "success" if success else "danger",
                "title": "Авто-вход" if success else "Ошибка авто-входа",
                "message": message,
                "device_id": device_id,
                "account_id": account_id,
            })
        except Exception:
            pass
