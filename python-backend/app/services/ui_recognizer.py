"""Multi-level UI element recognizer for social media automation.

Cascade: Accessibility → Resource ID → OCR+Template → YOLOv8
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models.ui_elements_cache import UIElementsCache

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None  # type: ignore

try:
    from ultralytics import YOLO  # type: ignore
except Exception:
    YOLO = None  # type: ignore

logger = logging.getLogger("chimera.ui_recognizer")

PLATFORM_ELEMENTS: dict[str, dict[str, dict[str, dict]]] = {
    "instagram": {
        "login": {
            "email_field": {"resource_id": "login_username", "fallback_text": ["Phone number, username, or email"]},
            "password_field": {"resource_id": "password", "fallback_text": ["Password"]},
            "login_button": {"resource_id": "log_in_button", "fallback_text": ["Log in", "Log In"]},
            "signup_link": {"resource_id": "sign_up_with_email_or_phone", "fallback_text": ["Sign up", "Sign Up"]},
        },
        "register": {
            "email_field": {"resource_id": "email_field", "fallback_text": ["Email", "Phone number"]},
            "next_button": {"resource_id": "next_button", "fallback_text": ["Next"]},
            "fullname_field": {"resource_id": "full_name", "fallback_text": ["Full Name"]},
            "password_field": {"resource_id": "password", "fallback_text": ["Password"]},
            "username_field": {"resource_id": "username", "fallback_text": ["Username"]},
        },
        "post": {
            "new_post_button": {"content_desc": "New post", "fallback_ocr": "+"},
            "gallery_grid": {"resource_id": "gallery_grid"},
            "next_button": {"resource_id": "next_button_textview", "fallback_text": ["Next"]},
            "caption_field": {"resource_id": "caption_text_view", "fallback_text": ["Write a caption..."]},
            "share_button": {"resource_id": "share_button", "fallback_text": ["Share"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like", "resource_id": "row_feed_button_like"},
            "comment_button": {"content_desc": "Comment", "resource_id": "row_feed_button_comment"},
            "follow_button": {"resource_id": "button", "fallback_text": ["Follow"]},
            "home_tab": {"content_desc": "Home"},
            "search_tab": {"content_desc": "Search and explore"},
            "profile_tab": {"content_desc": "Profile"},
        },
    },
    "tiktok": {
        "login": {
            "email_field": {"fallback_text": ["Phone / Email / Username", "Email or username"]},
            "password_field": {"fallback_text": ["Password"]},
            "login_button": {"fallback_text": ["Log in", "Log In"]},
            "signup_link": {"fallback_text": ["Sign up", "Sign Up"]},
        },
        "register": {
            "email_field": {"fallback_text": ["Email", "Phone"]},
            "next_button": {"fallback_text": ["Next"]},
            "password_field": {"fallback_text": ["Password"]},
            "username_field": {"fallback_text": ["Username"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like"},
            "comment_button": {"content_desc": "Comments"},
            "follow_button": {"fallback_text": ["Follow"]},
            "home_tab": {"content_desc": "Home"},
            "discover_tab": {"content_desc": "Discover"},
            "profile_tab": {"content_desc": "Profile"},
        },
    },
    "facebook": {
        "login": {
            "email_field": {"resource_id": "m_login_email", "fallback_text": ["Email or phone number"]},
            "password_field": {"resource_id": "m_login_password", "fallback_text": ["Password"]},
            "login_button": {"resource_id": "login_button", "fallback_text": ["Log In", "Log in"]},
        },
        "register": {
            "first_name": {"fallback_text": ["First name"]},
            "last_name": {"fallback_text": ["Last name", "Surname"]},
            "email_field": {"fallback_text": ["Mobile number or email"]},
            "password_field": {"fallback_text": ["New password"]},
            "signup_button": {"fallback_text": ["Sign Up", "Create Account"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like"},
            "comment_button": {"content_desc": "Comment"},
            "share_button": {"content_desc": "Share"},
        },
    },
    "twitter": {
        "login": {
            "email_field": {"fallback_text": ["Phone, email, or username"]},
            "password_field": {"fallback_text": ["Password"]},
            "login_button": {"fallback_text": ["Log in", "Next"]},
        },
        "register": {
            "name_field": {"fallback_text": ["Name"]},
            "email_field": {"fallback_text": ["Phone number or email address"]},
            "next_button": {"fallback_text": ["Next"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like"},
            "retweet_button": {"content_desc": "Repost"},
            "reply_button": {"content_desc": "Reply"},
        },
    },
    "telegram": {
        "login": {
            "phone_field": {"fallback_text": ["Your Phone Number"]},
            "next_button": {"fallback_text": ["Next", "Continue"]},
            "code_field": {"fallback_text": ["Code"]},
        },
    },
    "linkedin": {
        "login": {
            "email_field": {"fallback_text": ["Email or phone"]},
            "password_field": {"fallback_text": ["Password"]},
            "login_button": {"fallback_text": ["Sign in"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like"},
            "comment_button": {"content_desc": "Comment"},
        },
    },
    "vk": {
        "login": {
            "email_field": {"fallback_text": ["Phone or email", "Телефон или email"]},
            "password_field": {"fallback_text": ["Password", "Пароль"]},
            "login_button": {"fallback_text": ["Sign in", "Войти"]},
        },
    },
    "youtube": {
        "feed": {
            "like_button": {"content_desc": "Like this video"},
            "dislike_button": {"content_desc": "Dislike this video"},
            "subscribe_button": {"fallback_text": ["Subscribe"]},
        },
    },
    "reddit": {
        "login": {
            "username_field": {"fallback_text": ["Username"]},
            "password_field": {"fallback_text": ["Password"]},
            "login_button": {"fallback_text": ["Log In"]},
        },
    },
    "threads": {
        "login": {
            "login_button": {"fallback_text": ["Log in with Instagram"]},
        },
        "feed": {
            "like_button": {"content_desc": "Like"},
            "reply_button": {"content_desc": "Reply"},
        },
    },
}


class UIRecognizer:
    """Multi-level cascade UI element recognizer."""

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or "models/social_ui_detector.pt"
        self._yolo: Any = None

    def _load_yolo(self) -> Any:
        if self._yolo is None and YOLO is not None:
            model_file = Path(self._model_path)
            if model_file.exists():
                try:
                    self._yolo = YOLO(str(model_file))
                except Exception:
                    self._yolo = None
        return self._yolo

    async def find_element(
        self,
        platform: str,
        action: str,
        element_name: str,
        screenshot_bytes: bytes | None = None,
        device_serial: str | None = None,
        os_type: str = "android",
        os_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a UI element using the 4-level cascade."""

        platform_map = PLATFORM_ELEMENTS.get(platform, {})
        action_map = platform_map.get(action, {})
        element_def = action_map.get(element_name, {})

        if not element_def:
            logger.warning("No element definition for %s/%s/%s", platform, action, element_name)
            return None

        cached = await self._check_cache(platform, action, os_type, os_version)
        if cached and element_name in cached:
            return cached[element_name]

        # Level 1: Accessibility API (via ADB)
        if device_serial and os_type == "android":
            result = await self._find_via_accessibility(device_serial, element_def)
            if result:
                await self._update_cache(platform, action, os_type, os_version, element_name, result)
                return result

        # Level 2: Resource ID
        if device_serial and os_type == "android":
            resource_id = element_def.get("resource_id")
            if resource_id:
                result = await self._find_via_resource_id(device_serial, resource_id, platform)
                if result:
                    await self._update_cache(platform, action, os_type, os_version, element_name, result)
                    return result

        # Level 3: OCR + Template Matching
        if screenshot_bytes and cv2 is not None:
            result = await self._find_via_ocr(screenshot_bytes, element_def)
            if result:
                await self._update_cache(platform, action, os_type, os_version, element_name, result)
                return result

        # Level 4: YOLOv8
        if screenshot_bytes:
            result = await self._find_via_yolo(screenshot_bytes, element_name)
            if result:
                await self._update_cache(platform, action, os_type, os_version, element_name, result)
                return result

        logger.warning("Could not find element %s/%s/%s", platform, action, element_name)
        return None

    async def find_all_elements(
        self,
        platform: str,
        action: str,
        screenshot_bytes: bytes | None = None,
        device_serial: str | None = None,
        os_type: str = "android",
        os_version: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Find all elements for a given platform action."""
        platform_map = PLATFORM_ELEMENTS.get(platform, {})
        action_map = platform_map.get(action, {})

        results: dict[str, dict[str, Any]] = {}
        for element_name in action_map:
            result = await self.find_element(
                platform, action, element_name,
                screenshot_bytes, device_serial, os_type, os_version,
            )
            if result:
                results[element_name] = result
        return results

    async def _find_via_accessibility(
        self, device_serial: str, element_def: dict
    ) -> dict[str, Any] | None:
        fallback_texts = element_def.get("fallback_text", [])
        content_desc = element_def.get("content_desc", "")
        try:
            from utils.adb_utils import find_adb
            adb = find_adb()
            cmd_parts = [adb, "-s", device_serial, "shell", "uiautomator", "dump", "/dev/tty"]
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            xml_dump = stdout.decode("utf-8", errors="replace")

            for text in fallback_texts:
                if text.lower() in xml_dump.lower():
                    bounds = self._extract_bounds_from_dump(xml_dump, text)
                    if bounds:
                        return {"method": "accessibility", "text": text, "bounds": bounds, "confidence": 0.9}

            if content_desc and content_desc.lower() in xml_dump.lower():
                bounds = self._extract_bounds_from_dump(xml_dump, content_desc, attr="content-desc")
                if bounds:
                    return {"method": "accessibility", "content_desc": content_desc, "bounds": bounds, "confidence": 0.85}

        except Exception as e:
            logger.debug("Accessibility lookup failed: %s", e)
        return None

    async def _find_via_resource_id(
        self, device_serial: str, resource_id: str, platform: str
    ) -> dict[str, Any] | None:
        full_id = resource_id if ":" in resource_id else f"com.{platform}.android:id/{resource_id}"
        try:
            from utils.adb_utils import find_adb
            adb = find_adb()
            cmd_parts = [adb, "-s", device_serial, "shell", "uiautomator", "dump", "/dev/tty"]
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            xml_dump = stdout.decode("utf-8", errors="replace")

            if full_id in xml_dump:
                bounds = self._extract_bounds_from_dump(xml_dump, full_id, attr="resource-id")
                if bounds:
                    return {"method": "resource_id", "resource_id": full_id, "bounds": bounds, "confidence": 0.95}
        except Exception as e:
            logger.debug("Resource ID lookup failed: %s", e)
        return None

    async def _find_via_ocr(
        self, screenshot_bytes: bytes, element_def: dict
    ) -> dict[str, Any] | None:
        if cv2 is None or pytesseract is None:
            return None
        fallback_texts = element_def.get("fallback_text", [])
        fallback_ocr = element_def.get("fallback_ocr", "")

        try:
            import numpy as np
            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return None

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

            search_texts = fallback_texts + ([fallback_ocr] if fallback_ocr else [])
            for target in search_texts:
                for i, word in enumerate(data.get("text", [])):
                    if not word or not word.strip():
                        continue
                    if target.lower() in word.lower() or word.lower() in target.lower():
                        conf = float(data["conf"][i] or 0) / 100.0
                        if conf < 0.3:
                            continue
                        x = data["left"][i]
                        y = data["top"][i]
                        w = data["width"][i]
                        h = data["height"][i]
                        return {
                            "method": "ocr",
                            "text": word,
                            "bounds": {"x": x, "y": y, "w": w, "h": h},
                            "center": {"x": x + w // 2, "y": y + h // 2},
                            "confidence": conf,
                        }
        except Exception as e:
            logger.debug("OCR lookup failed: %s", e)
        return None

    async def _find_via_yolo(
        self, screenshot_bytes: bytes, element_name: str
    ) -> dict[str, Any] | None:
        yolo = self._load_yolo()
        if yolo is None:
            return None
        try:
            import numpy as np
            nparr = np.frombuffer(screenshot_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return None

            results = await asyncio.to_thread(yolo.predict, image, conf=0.7, verbose=False)
            for r in results:
                for box in getattr(r, "boxes", []) or []:
                    cls_name = r.names[int(box.cls.cpu().numpy().tolist()[0])]
                    if element_name.lower() in cls_name.lower():
                        xyxy = box.xyxy.cpu().numpy().tolist()[0]
                        conf = float(box.conf.cpu().numpy().tolist()[0])
                        cx = (xyxy[0] + xyxy[2]) / 2
                        cy = (xyxy[1] + xyxy[3]) / 2
                        return {
                            "method": "yolo",
                            "class": cls_name,
                            "bounds": {"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]},
                            "center": {"x": int(cx), "y": int(cy)},
                            "confidence": conf,
                        }
        except Exception as e:
            logger.debug("YOLO lookup failed: %s", e)
        return None

    def _extract_bounds_from_dump(
        self, xml_dump: str, search_value: str, attr: str = "text"
    ) -> dict[str, int] | None:
        import re
        pattern = rf'{attr}="[^"]*{re.escape(search_value)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        match = re.search(pattern, xml_dump, re.IGNORECASE)
        if match:
            x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "cx": (x1 + x2) // 2, "cy": (y1 + y2) // 2}
        return None

    async def _check_cache(
        self, platform: str, action: str, os_type: str, os_version: str | None
    ) -> dict[str, dict] | None:
        try:
            async with SessionLocal() as session:
                stmt = select(UIElementsCache).where(
                    UIElementsCache.platform == platform,
                    UIElementsCache.action == action,
                    UIElementsCache.os_type == os_type,
                )
                if os_version:
                    major = os_version.split(".")[0]
                    stmt = stmt.where(UIElementsCache.os_version == major)
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row and row.confidence > 0.5:
                    return json.loads(row.locators)
        except Exception:
            pass
        return None

    async def _update_cache(
        self,
        platform: str,
        action: str,
        os_type: str,
        os_version: str | None,
        element_name: str,
        result: dict,
    ) -> None:
        try:
            major = os_version.split(".")[0] if os_version else None
            async with SessionLocal() as session:
                stmt = select(UIElementsCache).where(
                    UIElementsCache.platform == platform,
                    UIElementsCache.action == action,
                    UIElementsCache.os_type == os_type,
                )
                if major:
                    stmt = stmt.where(UIElementsCache.os_version == major)
                row = (await session.execute(stmt)).scalar_one_or_none()

                locators = {}
                if row:
                    try:
                        locators = json.loads(row.locators)
                    except Exception:
                        pass
                    locators[element_name] = result
                    row.locators = json.dumps(locators)
                    row.confidence = result.get("confidence", 0.5)
                    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    locators[element_name] = result
                    entry = UIElementsCache(
                        platform=platform,
                        action=action,
                        os_type=os_type,
                        os_version=major,
                        locators=json.dumps(locators),
                        confidence=result.get("confidence", 0.5),
                    )
                    session.add(entry)
                await session.commit()
        except Exception as e:
            logger.debug("Cache update failed: %s", e)

    def get_platform_elements(self, platform: str) -> dict:
        return PLATFORM_ELEMENTS.get(platform, {})


ui_recognizer = UIRecognizer()
