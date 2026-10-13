import asyncio
import os

from utils.adb_utils import adb_cmd, find_adb


class Poster:
    def __init__(self, serial):
        self.serial = serial

    def _sh(self, c):
        adb_cmd(self.serial, ["shell"] + c.split(), timeout=15)

    def _host(self, c):
        adb_cmd(self.serial, c.split(), timeout=60)

    async def post(self, photos, caption, platform="instagram"):
        for p in photos:
            n = os.path.basename(p)
            self._host(f"push {p} /sdcard/DCIM/Camera/{n}")
            self._sh(f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file:///sdcard/DCIM/Camera/{n}"')
            await asyncio.sleep(1)
        await asyncio.sleep(2)
        pkg = {
            "instagram": "com.instagram.android",
            "tiktok": "com.zhiliaoapp.musically",
            "facebook": "com.facebook.katana",
            "twitter": "com.twitter.android",
        }.get(platform, "com.instagram.android")
        self._sh(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        await asyncio.sleep(4)
        btn = await self.ui.wait(
            [{"content_desc": "New post"}, {"text": "New post"}, {"resource_id": "com.instagram.android:id/creation_tab"}],
            10,
        )
        if btn:
            self.cursor.tap(btn["x"], btn["y"])
        else:
            return {"ok": False, "err": "New Post button not found"}
        await asyncio.sleep(3)
        self.cursor.tap(200, 600)
        await asyncio.sleep(2)
        nx = await self.ui.wait([{"text": "Next"}, {"text": "Далее"}], 8)
        if nx:
            self.cursor.tap(nx["x"], nx["y"])
            await asyncio.sleep(3)
        nx2 = await self.ui.wait([{"text": "Next"}, {"text": "Далее"}], 5)
        if nx2:
            self.cursor.tap(nx2["x"], nx2["y"])
            await asyncio.sleep(3)
        cap = await self.ui.wait([{"text_contains": "caption"}, {"text": "Write a caption..."}], 8)
        if cap:
            self.cursor.tap(cap["x"], cap["y"])
            await asyncio.sleep(0.3)
            self.cursor.type_text(caption)
        await asyncio.sleep(1)
        sh = await self.ui.wait([{"text": "Share"}, {"text": "Опубликовать"}], 8)
        if sh:
            self.cursor.tap(sh["x"], sh["y"])
        await asyncio.sleep(8)
        return {"ok": True}
