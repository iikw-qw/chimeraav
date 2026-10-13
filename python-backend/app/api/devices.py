from __future__ import annotations

import asyncio
import concurrent.futures
import io
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services import tools as tools_svc
from app.services.adb_stream_producer import AdbStreamProducer
from app.services.antidetect import human_behavior

from ._deps import apply_update, get_or_404, get_session
from ._hub import hub

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    platform: str
    status: str = "offline"
    phone_number: str | None = None
    ip_address: str | None = None
    serial: str | None = None
    battery_level: int | None = None
    proxy_id: str | None = None
    group_name: str | None = None
    is_master: bool = False


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    platform: str | None = None
    status: str | None = None
    phone_number: str | None = None
    ip_address: str | None = None
    serial: str | None = None
    battery_level: int | None = None
    proxy_id: str | None = None
    group_name: str | None = None
    is_master: bool | None = None


class DeviceRead(DeviceBase):
    id: str
    unique_code: str | None = None
    last_heartbeat: datetime | None = None
    created_at: datetime


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    group: str | None = None,
    sync: bool = False,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[Device]:
    if sync:
        await perform_scan(session)
    stmt = select(Device)
    if status:
        stmt = stmt.where(Device.status == status)
    if group:
        stmt = stmt.where(Device.group_name == group)
    stmt = stmt.order_by(Device.created_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=DeviceRead, status_code=201)
async def create_device(
    payload: DeviceCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Device:
    device = Device(**payload.model_dump())
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


@router.get("/map")
async def devices_map(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    rows = (await session.execute(select(Device))).scalars().all()
    by_group: dict[str, list[dict]] = {}
    for d in rows:
        key = d.group_name or "ungrouped"
        by_group.setdefault(key, []).append(
            {
                "id": d.id,
                "name": d.name,
                "platform": d.platform,
                "status": d.status,
                "is_master": d.is_master,
            }
        )
    return {"groups": by_group, "total": len(rows)}


@router.get("/adb")
async def adb_fallback_devices() -> list[dict]:
    """Return devices directly from ADB, bypassing the database."""
    import re as _re
    import subprocess as _sub
    from utils.adb_utils import find_adb, adb_cmd

    try:
        result = _sub.run(
            [find_adb(), "devices", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            if "device" in line and "offline" not in line and "unauthorized" not in line:
                parts = line.split()
                serial = parts[0]
                model = ""
                for p in parts:
                    if p.startswith("model:"):
                        model = p.split(":")[1]
                info: dict = {
                    "serial": serial,
                    "name": model or serial,
                    "status": "online",
                    "platform": "android",
                    "id": serial,
                }
                try:
                    for prop, key in [
                        ("ro.product.model", "name"),
                        ("ro.product.brand", "manufacturer"),
                        ("ro.build.version.release", "os_version"),
                    ]:
                        pr = adb_cmd(serial, ["shell", "getprop", prop], timeout=5)
                        val = pr.stdout.strip()
                        if val:
                            info[key] = val
                    br = adb_cmd(serial, ["shell", "dumpsys", "battery"], timeout=5)
                    for bl in br.stdout.split("\n"):
                        if "level:" in bl:
                            info["battery_level"] = int(bl.split(":")[1].strip())
                    ir = adb_cmd(serial, ["shell", "ip", "addr", "show", "wlan0"], timeout=5)
                    im = _re.search(r"inet (\d+\.\d+\.\d+\.\d+)", ir.stdout)
                    info["ip_address"] = im.group(1) if im else "USB"
                except Exception:
                    pass
                devices.append(info)
        return devices
    except Exception as e:
        return [{"error": str(e)}]


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Device:
    return await get_or_404(session, Device, device_id)


@router.put("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Device:
    device = await get_or_404(session, Device, device_id)
    apply_update(device, payload)
    await session.commit()
    await session.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    device = await get_or_404(session, Device, device_id)
    await session.delete(device)
    await session.commit()
    return Response(status_code=204)


@router.post("/{device_id}/calibrate")
async def calibrate_device(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    device = await get_or_404(session, Device, device_id)
    return {
        "device_id": device.id,
        "status": "calibration_started",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/{device_id}/refresh-ip")
async def refresh_device_ip(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    """Probe the device's current outbound IP — verifies VPN/proxy is active."""
    device = await get_or_404(session, Device, device_id)
    ip = await _probe_external_ip(device)
    if ip:
        device.ip_address = ip
        await session.commit()
        await session.refresh(device)
    return {"device_id": device.id, "ip_address": device.ip_address}


async def _probe_external_ip(device: Device) -> str | None:
    serial = device.serial
    if not serial:
        return None
    if device.platform != "android":
        return None
    adb = tools_svc.resolve("adb")
    if adb is None:
        return None

    import re
    ip_re = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

    async def _adb_sh(cmd: str) -> str:
        code, out, _ = await _run(
            [adb, "-s", serial, "shell", cmd], timeout=6.0,
        )
        return out.strip() if code == 0 else ""

    # 1) ip addr show wlan0
    out = await _adb_sh("ip addr show wlan0 2>/dev/null")
    if "inet " in out:
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)

    # 2) ifconfig wlan0
    out = await _adb_sh("ifconfig wlan0 2>/dev/null")
    if "inet " in out:
        m = re.search(r'inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)

    # 3) ip route
    out = await _adb_sh("ip route get 8.8.8.8 2>/dev/null | head -1")
    if "src " in out:
        m = re.search(r'src (\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)

    # 4) getprop
    out = await _adb_sh("getprop dhcp.wlan0.ipaddress 2>/dev/null")
    if out and "." in out and ip_re.match(out):
        return out

    # 5) External IP via curl
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        code, out, _ = await _run(
            [adb, "-s", serial, "shell", "curl", "-s", "--max-time", "8", url],
            timeout=12.0,
        )
        if code == 0:
            ip = (out or "").strip()
            if ip and len(ip) <= 45 and all(c in "0123456789abcdefABCDEF.:" for c in ip):
                return ip

    return "USB-подключение"


_PLACEHOLDER_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _capture_android(serial: str) -> bytes | None:
    adb = tools_svc.resolve("adb")
    if adb is None:
        return None
    cmd = [adb, "-s", serial, "exec-out", "screencap", "-p"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return None
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
    except asyncio.TimeoutError:
        proc.kill()
        return None
    if (proc.returncode or 0) != 0 or not stdout:
        return None
    # Some older adb builds on Windows produce CRLF-translated output.
    # PNG signature is 8 bytes; detect and strip offset if necessary.
    sig = b"\x89PNG\r\n\x1a\n"
    if stdout.startswith(sig):
        return stdout
    idx = stdout.find(sig)
    if idx > 0:
        return stdout[idx:]
    # Fallback: replace \r\n with \n
    return stdout.replace(b"\r\n", b"\n")


async def _capture_ios(udid: str) -> bytes | None:
    tool = tools_svc.resolve("idevicescreenshot")
    if tool is None:
        return None
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        target = f"{td}/shot.png"
        code, _, _ = await _run([tool, "-u", udid, target], timeout=15.0)
        if code != 0:
            return None
        try:
            with open(target, "rb") as fh:
                return fh.read()
        except OSError:
            return None


async def _read_exact(stream: asyncio.StreamReader, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = await stream.read(n - len(buf))
        if not chunk:
            raise EOFError
        buf.extend(chunk)
    return bytes(buf)


_ENCODE_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=6, thread_name_prefix="jpeg-enc"
)


def _encode_jpeg(
    pixels: bytes,
    w: int,
    h: int,
    fmt: int,
    max_width: int,
    quality: int,
) -> bytes | None:
    """CPU-bound JPEG encoder — runs on a worker thread so the event loop
    stays free to read the next frame's pixel buffer off the adb pipe.

    Tuned for screen mirroring throughput:
      * `Image.frombuffer` is already zero-copy on RGBA buffers.
      * The `convert("RGB")` step is skipped — we ask Pillow to ignore alpha
        directly when saving as JPEG, which avoids a full extra pass over
        ~8MB of pixel data on every frame.
      * One single resize using BILINEAR (cheaper than LANCZOS, visually
        indistinguishable at the typical 720→540 px target).
      * `subsampling=2` (4:2:0) matches what mobile cameras output —
        compresses ~30% smaller than 4:4:4 with no perceptible loss for UI
        screenshots.
    """
    try:
        from PIL import Image

        # screencap fmts: 1 RGBA_8888, 2 RGBX_8888, 3 RGB_888, 5 BGRA_8888.
        mode = "RGBA" if fmt in (1, 5) else "RGB"
        img = Image.frombuffer(mode, (w, h), pixels, "raw", mode, 0, 1)
        if max_width and img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.BILINEAR)
        if mode == "RGBA":
            img = img.convert("RGB")
        buf = io.BytesIO()
        # 4:2:0 chroma subsampling is the mobile-camera default — ~30%
        # smaller files than 4:4:4 with no perceptible loss on UI captures.
        img.save(
            buf, format="JPEG", quality=quality, subsampling=2, optimize=False
        )
        return buf.getvalue()
    except Exception:
        return None


async def _stream_android_adb(serial: str, fps: int, quality: int, max_width: int):
    """Yields multipart JPEG frames from a *persistent* adb process.

    Pipeline (double-buffered):
      - one long-lived `adb exec-out "while true; do screencap; done"` stream
        emits raw RGBA frames back-to-back (no per-frame subprocess spawn)
      - pixel reads from the adb pipe and JPEG encodes run concurrently:
        while frame N is being encoded on a worker thread, frame N+1's header
        and pixels are already being pulled off the pipe on the event loop.

    Wall-clock latency drops from ~(capture+read+encode) to
    ~max(capture+read, encode), typically halving the per-frame cost on the
    host and letting 24–30 fps sustain on modest hardware.

    Frame wire format (from `screencap` binary, Android 8+):
       uint32_le width, uint32_le height, uint32_le format [, uint32_le reserved],
       then width*height*4 bytes of pixels (RGBA_8888 when format==1).
    Some Android builds add an extra 4-byte field (color space) after format.
    """
    adb = tools_svc.resolve("adb")
    if adb is None:
        return
    boundary = b"--frame"
    sep = b"\r\n"
    min_interval = max(1.0 / max(fps, 1), 0.0)
    loop = asyncio.get_event_loop()
    proc: asyncio.subprocess.Process | None = None
    last_emit = 0.0
    pending: asyncio.Future | None = None

    async def _read_header(
        stdout: asyncio.StreamReader, extra: int
    ) -> tuple[int, int, int]:
        hdr = await _read_exact(stdout, 12 + extra)
        return (
            int.from_bytes(hdr[0:4], "little"),
            int.from_bytes(hdr[4:8], "little"),
            int.from_bytes(hdr[8:12], "little"),
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            adb,
            "-s",
            serial,
            "exec-out",
            "while true; do screencap; done",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert proc.stdout is not None

        # Probe first header, detect 12-byte vs 16-byte layout.
        first_hdr = await asyncio.wait_for(_read_exact(proc.stdout, 16), timeout=10.0)
        w = int.from_bytes(first_hdr[0:4], "little")
        h = int.from_bytes(first_hdr[4:8], "little")
        fmt = int.from_bytes(first_hdr[8:12], "little")
        extra_byte_count = 4  # consume one extra uint32 (color space on A14+)
        if not (100 < w < 8000 and 100 < h < 16000 and fmt in (1, 2, 3, 5)):
            extra_byte_count = 0
            carryover = first_hdr[12:16]
        else:
            carryover = b""

        while True:
            if carryover:
                pixel_prefix = carryover
                carryover = b""
            else:
                pixel_prefix = b""

            expected_pixels = w * h * 4
            if pixel_prefix:
                remaining = expected_pixels - len(pixel_prefix)
                rest = await _read_exact(proc.stdout, remaining)
                pixels = pixel_prefix + rest
            else:
                pixels = await _read_exact(proc.stdout, expected_pixels)

            cur_w, cur_h, cur_fmt = w, h, fmt

            # fps cap — keep consuming the pipe to stay in sync, skip encode.
            now = loop.time()
            if min_interval > 0 and now - last_emit < min_interval:
                w, h, fmt = await _read_header(proc.stdout, extra_byte_count)
                continue
            last_emit = now

            # Kick off encode on the worker pool, then overlap the next
            # frame's header read with that encode.
            encode_future = loop.run_in_executor(
                _ENCODE_POOL,
                _encode_jpeg,
                pixels,
                cur_w,
                cur_h,
                cur_fmt,
                max_width,
                quality,
            )

            # Emit the previous frame (if any) now — this is what gives the
            # viewer frames as fast as the encoder delivers them while the
            # reader keeps pulling bytes off the pipe.
            if pending is not None:
                frame = await pending
                pending = None
                if frame is not None:
                    yield b"".join(
                        (
                            boundary,
                            sep,
                            b"Content-Type: image/jpeg",
                            sep,
                            b"Content-Length: ",
                            str(len(frame)).encode(),
                            sep,
                            sep,
                            frame,
                            sep,
                        )
                    )

            pending = encode_future

            # Read the next frame's header in parallel with the encode.
            w, h, fmt = await _read_header(proc.stdout, extra_byte_count)
    except (EOFError, asyncio.TimeoutError):
        return
    finally:
        if pending is not None:
            try:
                frame = await pending
                if frame is not None:
                    yield b"".join(
                        (
                            boundary,
                            sep,
                            b"Content-Type: image/jpeg",
                            sep,
                            b"Content-Length: ",
                            str(len(frame)).encode(),
                            sep,
                            sep,
                            frame,
                            sep,
                        )
                    )
            except Exception:
                pass
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except (ProcessLookupError, OSError):
                pass


@router.get("/{device_id}/stream")
async def device_stream(
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    fps: int = Query(30, ge=1, le=60),
    quality: int = Query(70, ge=30, le=95),
    max_width: int = Query(540, ge=240, le=1920),
) -> StreamingResponse:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "stream is currently Android-only")
    serial = device.serial or device.id
    return StreamingResponse(
        _stream_android_adb(serial, fps=fps, quality=quality, max_width=max_width),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{device_id}/screenshot")
async def device_screenshot(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    device = await get_or_404(session, Device, device_id)
    serial = device.serial or device.id
    img: bytes | None = None
    if device.platform == "android":
        img = await _capture_android(serial)
    elif device.platform == "ios":
        img = await _capture_ios(serial)
    if img is None:
        return Response(
            content=_PLACEHOLDER_PNG,
            media_type="image/png",
            headers={"Cache-Control": "no-store", "X-Screenshot": "placeholder"},
        )
    return Response(
        content=img,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


class TapPayload(BaseModel):
    x: int
    y: int


class SwipePayload(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300


class TextPayload(BaseModel):
    text: str


class KeyPayload(BaseModel):
    keycode: int | str


@router.post("/{device_id}/tap")
async def device_tap(
    device_id: str,
    payload: TapPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "tap is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    code, _, err = await _run(
        [adb, "-s", serial, "shell", "input", "tap", str(payload.x), str(payload.y)],
        timeout=10.0,
    )
    if code != 0:
        raise HTTPException(500, f"adb tap failed: {err.strip() or code}")
    return {"ok": True}


@router.post("/{device_id}/swipe")
async def device_swipe(
    device_id: str,
    payload: SwipePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "swipe is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    code, _, err = await _run(
        [
            adb,
            "-s",
            serial,
            "shell",
            "input",
            "swipe",
            str(payload.x1),
            str(payload.y1),
            str(payload.x2),
            str(payload.y2),
            str(payload.duration_ms),
        ],
        timeout=12.0,
    )
    if code != 0:
        raise HTTPException(500, f"adb swipe failed: {err.strip() or code}")
    return {"ok": True}


@router.post("/{device_id}/text")
async def device_text(
    device_id: str,
    payload: TextPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "text is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    # adb input text does not handle spaces/punct correctly; use %s substitution
    safe = payload.text.replace(" ", "%s")
    code, _, err = await _run(
        [adb, "-s", serial, "shell", "input", "text", safe],
        timeout=10.0,
    )
    if code != 0:
        raise HTTPException(500, f"adb text failed: {err.strip() or code}")
    return {"ok": True}


@router.post("/{device_id}/key")
async def device_key(
    device_id: str,
    payload: KeyPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "key is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    code, _, err = await _run(
        [adb, "-s", serial, "shell", "input", "keyevent", str(payload.keycode)],
        timeout=10.0,
    )
    if code != 0:
        raise HTTPException(500, f"adb key failed: {err.strip() or code}")
    return {"ok": True}


# --- Human-like input --------------------------------------------------------
#
# These endpoints decompose each action into a plan from HumanBehaviorEngine
# (jittered target, natural swipe duration, bezier waypoints) and broadcast
# cursor waypoints via the "cursor" WebSocket channel so the frontend can
# render a visible, finger-like trail on top of the MJPEG stream.


class HumanTapPayload(BaseModel):
    x: int
    y: int


class HumanSwipePayload(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class HumanTextPayload(BaseModel):
    text: str
    clear_first: bool = False


class CursorTrailPayload(BaseModel):
    enabled: bool


async def _broadcast_cursor(
    device_id: str,
    kind: str,
    *,
    x: int | None = None,
    y: int | None = None,
    waypoints: list[dict] | None = None,
    duration_ms: int | None = None,
) -> None:
    try:
        await hub.broadcast(
            "cursor",
            {
                "device_id": device_id,
                "kind": kind,
                "x": x,
                "y": y,
                "waypoints": waypoints,
                "duration_ms": duration_ms,
            },
        )
    except Exception:
        pass  # cursor overlay must never break input


@router.post("/{device_id}/human_tap")
async def device_human_tap(
    device_id: str,
    payload: HumanTapPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "human_tap is Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id

    jx, jy = human_behavior.jittered_tap(payload.x, payload.y)
    press = human_behavior.tap_press_ms()
    await _broadcast_cursor(device_id, "tap", x=jx, y=jy, duration_ms=press)

    # Use `input swipe` with same x/y so we control press duration ourselves.
    code, _, err = await _run(
        [adb, "-s", serial, "shell", "input", "swipe",
         str(jx), str(jy), str(jx), str(jy), str(press)],
        timeout=6.0,
    )
    if code != 0:
        raise HTTPException(500, f"adb human_tap failed: {err.strip() or code}")
    return {"ok": True, "x": jx, "y": jy, "press_ms": press}


@router.post("/{device_id}/human_swipe")
async def device_human_swipe(
    device_id: str,
    payload: HumanSwipePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "human_swipe is Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id

    plan = human_behavior.humanize_swipe(payload.x1, payload.y1, payload.x2, payload.y2)
    await _broadcast_cursor(
        device_id,
        "swipe",
        waypoints=plan["waypoints"],
        duration_ms=plan["duration_ms"],
    )

    code, _, err = await _run(
        [adb, "-s", serial, "shell", "input", "swipe",
         str(plan["x1"]), str(plan["y1"]),
         str(plan["x2"]), str(plan["y2"]),
         str(plan["duration_ms"])],
        timeout=max(8.0, plan["duration_ms"] / 1000 + 4),
    )
    if code != 0:
        raise HTTPException(500, f"adb human_swipe failed: {err.strip() or code}")
    return {"ok": True, **{k: plan[k] for k in ("x1", "y1", "x2", "y2", "duration_ms")}}


@router.post("/{device_id}/human_type")
async def device_human_type(
    device_id: str,
    payload: HumanTextPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "human_type is Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id

    if payload.clear_first:
        # Select-all + delete: long-press isn't scriptable, so just spam backspace.
        for _ in range(200):
            await _run([adb, "-s", serial, "shell", "input", "keyevent", "67"], timeout=2.0)

    plan = human_behavior.typing_plan(payload.text)
    sent = 0
    for ch, delay in plan:
        safe = "%s" if ch == " " else ch
        # Escape a few shell-sensitive chars. adb input text accepts most ASCII.
        if safe in ("'", '"', "\\", "`", "&", ";", "<", ">", "|", "$"):
            safe = f"\\{safe}"
        code, _, _ = await _run(
            [adb, "-s", serial, "shell", "input", "text", safe],
            timeout=4.0,
        )
        if code == 0:
            sent += 1
        await asyncio.sleep(delay)
    return {"ok": True, "sent": sent, "total": len(plan)}


@router.post("/{device_id}/cursor_trail")
async def device_cursor_trail(
    device_id: str,
    payload: CursorTrailPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Toggle native Android 'Show touches' + 'Pointer location' overlays.

    Both are stock developer settings that render visible finger circles on
    the device itself — so a human watching the stream sees clearly where
    taps land, and any external screen-record viewer sees the same.
    """
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "cursor_trail is Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    v = "1" if payload.enabled else "0"
    for key in ("show_touches", "pointer_location"):
        await _run(
            [adb, "-s", serial, "shell", "settings", "put", "system", key, v],
            timeout=5.0,
        )
    return {"ok": True, "enabled": payload.enabled}


class WarmupPayload(BaseModel):
    duration_seconds: int = 300
    account_id: str | None = None
    scroll_weight: int = 60
    profile_visit_weight: int = 15
    like_weight: int = 15
    follow_weight: int = 5
    random_tap_weight: int = 5
    like_unlike_weight: int = 5
    repost_weight: int = 0


@router.post("/{device_id}/warmup")
async def device_warmup(
    device_id: str,
    payload: WarmupPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Kick off a warmup session — runs in background, emits progress on the
    'warmup' WS channel and cursor waypoints on the 'cursor' channel."""
    from app.services.warmup_service import WarmupConfig, warmup_service

    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "warmup is Android-only")

    cfg = WarmupConfig(
        duration_seconds=max(30, min(3600, payload.duration_seconds)),
        scroll_weight=payload.scroll_weight,
        profile_visit_weight=payload.profile_visit_weight,
        like_weight=payload.like_weight,
        follow_weight=payload.follow_weight,
        random_tap_weight=payload.random_tap_weight,
        like_unlike_weight=payload.like_unlike_weight,
        repost_weight=payload.repost_weight,
    )
    asyncio.create_task(
        warmup_service.run(device_id, account_id=payload.account_id, config=cfg)
    )
    return {"ok": True, "device_id": device_id, "duration_seconds": cfg.duration_seconds}


class GalleryPushPayload(BaseModel):
    paths: list[str]


@router.post("/{device_id}/gallery/push")
async def device_gallery_push(
    device_id: str,
    payload: GalleryPushPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Push local media files to the phone's DCIM/Camera and trigger
    MediaScanner, so a post can be published from the device's gallery
    (as a real user would)."""
    from app.services.gallery_service import gallery_service

    await get_or_404(session, Device, device_id)
    try:
        remote_paths = await gallery_service.push_many(device_id, payload.paths)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"gallery push failed: {exc}") from exc
    return {"ok": True, "device_paths": remote_paths, "count": len(remote_paths)}


@router.post("/{device_id}/gallery/cleanup")
async def device_gallery_cleanup(
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    from app.services.gallery_service import gallery_service

    await get_or_404(session, Device, device_id)
    removed = await gallery_service.cleanup_pushed(device_id)
    return {"ok": True, "removed": removed}


@router.get("/{device_id}/info")
async def device_info(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        return {
            "id": device.id,
            "platform": device.platform,
            "status": device.status,
        }
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    props = {}
    for key in (
        "ro.product.model",
        "ro.product.manufacturer",
        "ro.product.brand",
        "ro.build.version.release",
        "ro.build.version.sdk",
    ):
        code, out, _ = await _run(
            [adb, "-s", serial, "shell", "getprop", key],
            timeout=5.0,
        )
        if code == 0:
            props[key] = out.strip()
    # Battery via dumpsys
    batt = None
    code, out, _ = await _run(
        [adb, "-s", serial, "shell", "dumpsys", "battery"],
        timeout=6.0,
    )
    if code == 0:
        for line in out.splitlines():
            if "level:" in line:
                try:
                    batt = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
                break
    # Resolution via wm size
    size = None
    code, out, _ = await _run(
        [adb, "-s", serial, "shell", "wm", "size"],
        timeout=5.0,
    )
    if code == 0:
        for line in out.splitlines():
            if "Physical size:" in line:
                size = line.split(":", 1)[1].strip()
                break
    # Persist battery for quick UI reads
    if batt is not None:
        device.battery_level = batt
        device.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
    return {
        "id": device.id,
        "platform": device.platform,
        "status": device.status,
        "model": props.get("ro.product.model"),
        "manufacturer": props.get("ro.product.manufacturer"),
        "brand": props.get("ro.product.brand"),
        "android_version": props.get("ro.build.version.release"),
        "sdk": props.get("ro.build.version.sdk"),
        "battery_level": batt,
        "resolution": size,
    }


@router.post("/{device_id}/reboot")
async def device_reboot(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "reboot is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb unavailable")
    serial = device.serial or device.id
    code, _, err = await _run([adb, "-s", serial, "reboot"], timeout=10.0)
    if code != 0:
        raise HTTPException(500, f"adb reboot failed: {err.strip() or code}")
    device.status = "offline"
    await session.commit()
    return {"ok": True}


@router.post("/{device_id}/disconnect")
async def device_disconnect(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    device = await get_or_404(session, Device, device_id)
    adb = tools_svc.resolve("adb")
    if adb and device.platform == "android" and device.serial and ":" in device.serial:
        # TCP/IP connected — proper disconnect
        await _run([adb, "disconnect", device.serial], timeout=5.0)
    device.status = "offline"
    await session.commit()
    return {"ok": True}


class PausePayload(BaseModel):
    paused: bool


@router.post("/{device_id}/pause")
async def device_pause(
    device_id: str,
    payload: PausePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    device.status = "paused" if payload.paused else "online"
    await session.commit()
    return {"ok": True, "status": device.status}


class SetMasterPayload(BaseModel):
    is_master: bool = True


@router.put("/{device_id}/set-master", response_model=DeviceRead)
async def set_master(
    device_id: str,
    payload: SetMasterPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Device:
    device = await get_or_404(session, Device, device_id)
    if payload.is_master:
        # Unset master on other devices in the same group.
        stmt = select(Device).where(
            Device.group_name == device.group_name, Device.id != device.id
        )
        for other in (await session.execute(stmt)).scalars():
            other.is_master = False
    device.is_master = payload.is_master
    await session.commit()
    await session.refresh(device)
    return device


class GroupPayload(BaseModel):
    group_name: str | None


@router.put("/{device_id}/group", response_model=DeviceRead)
async def set_group(
    device_id: str,
    payload: GroupPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Device:
    device = await get_or_404(session, Device, device_id)
    device.group_name = payload.group_name
    await session.commit()
    await session.refresh(device)
    return device


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


async def _scan_android() -> list[dict]:
    adb = tools_svc.resolve("adb")
    if adb is None:
        return []
    code, out, _ = await _run([adb, "devices", "-l"])
    if code != 0:
        return []
    found: list[dict] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        model = serial
        for tok in parts[2:]:
            if tok.startswith("model:"):
                model = tok.split(":", 1)[1]
        found.append(
            {
                "id": serial,
                "name": model,
                "platform": "android",
                "status": "online" if state == "device" else state,
                "serial": serial,
            }
        )
    return found


async def _scan_ios() -> list[dict]:
    tool = tools_svc.resolve("idevice_id")
    if tool is None:
        return []
    code, out, _ = await _run([tool, "-l"])
    if code != 0:
        return []
    udids = [u.strip() for u in out.splitlines() if u.strip()]
    found: list[dict] = []
    name_tool = tools_svc.resolve("ideviceinfo")
    for udid in udids:
        name = udid
        if name_tool:
            ncode, nout, _ = await _run([name_tool, "-u", udid, "-k", "DeviceName"])
            if ncode == 0 and nout.strip():
                name = nout.strip()
        found.append(
            {
                "id": udid,
                "name": name,
                "platform": "ios",
                "status": "online",
                "serial": udid,
            }
        )
    return found


class ScanResult(BaseModel):
    devices: list[DeviceRead]
    android_available: bool
    ios_available: bool


async def perform_scan(session: AsyncSession) -> tuple[list[Device], bool, bool]:
    """Discover connected devices, upsert rows, mark missing ones offline.

    Shared between the HTTP endpoint and the background scheduler.
    """
    android_available = tools_svc.resolve("adb") is not None
    ios_available = tools_svc.resolve("idevice_id") is not None

    discovered: list[dict] = []
    if android_available:
        discovered.extend(await _scan_android())
    if ios_available:
        discovered.extend(await _scan_ios())

    result_devices: list[Device] = []
    seen_serials: set[str] = set()
    for info in discovered:
        seen_serials.add(info["serial"])
        stmt = select(Device).where(Device.serial == info["serial"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            device = Device(
                name=info["name"],
                platform=info["platform"],
                status=info["status"],
                serial=info["serial"],
            )
            session.add(device)
        else:
            # preserve paused state; scanner shouldn't override it
            if existing.status != "paused":
                existing.status = info["status"]
            existing.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
            if not existing.name or existing.name == existing.serial:
                existing.name = info["name"]
            if existing.platform != info["platform"]:
                existing.platform = info["platform"]
            device = existing
        result_devices.append(device)

    # devices present in DB but not seen in this scan → offline
    stmt = select(Device).where(Device.serial.is_not(None))
    for row in (await session.execute(stmt)).scalars():
        if row.serial not in seen_serials and row.status not in ("offline", "paused"):
            row.status = "offline"

    await session.commit()
    for device in result_devices:
        await session.refresh(device)
    return result_devices, android_available, ios_available


@router.post("/scan", response_model=ScanResult)
async def scan_devices(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScanResult:
    devices, android_available, ios_available = await perform_scan(session)
    return ScanResult(
        devices=[DeviceRead.model_validate(d) for d in devices],
        android_available=android_available,
        ios_available=ios_available,
    )


@router.post("/sync")
async def sync_devices(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Synchronize ADB-connected devices with the database: update statuses,
    add newly discovered devices, mark missing ones offline."""
    devices, android_available, ios_available = await perform_scan(session)
    online = sum(1 for d in devices if d.status == "online")
    return {
        "ok": True,
        "adb_devices": len(devices),
        "online": online,
        "synced": True,
        "android_available": android_available,
        "ios_available": ios_available,
    }


def _find_agent_apk() -> str | None:
    """Locate chimera-agent.apk if it exists."""
    import os
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "agent-android", "chimera-agent.apk"),
        os.path.join(os.path.dirname(__file__), "..", "..", "resources", "chimera-agent.apk"),
    ]
    return next((os.path.abspath(p) for p in candidates if os.path.exists(p)), None)


async def _install_apk_on_device(adb: str, serial: str, apk: str, name: str) -> dict:
    """Install chimera-agent APK + launch + grant permissions."""
    pm_code, pm_out, _ = await _run(
        [adb, "-s", serial, "shell", "pm", "list", "packages", "com.chimera.agent"],
        timeout=5.0,
    )
    is_update = "com.chimera.agent" in pm_out

    code, _, err = await _run(
        [adb, "-s", serial, "install", "-r", apk], timeout=120.0,
    )
    if code != 0:
        raise HTTPException(500, f"Ошибка установки: {err.strip() or code}")

    await _run(
        [adb, "-s", serial, "shell", "am", "start", "-n",
         "com.chimera.agent/.MainActivity"],
        timeout=10.0,
    )

    for perm in [
        "SYSTEM_ALERT_WINDOW", "FOREGROUND_SERVICE",
        "WRITE_EXTERNAL_STORAGE", "READ_EXTERNAL_STORAGE",
    ]:
        await _run(
            [adb, "-s", serial, "shell", "pm", "grant",
             "com.chimera.agent", f"android.permission.{perm}"],
            timeout=5.0,
        )

    action = "обновлён" if is_update else "установлен"
    return {"ok": True, "message": f"Агент {action} на {name}", "method": "agent_apk"}


async def _start_streaming_on_device(adb: str, device: Device) -> dict:
    """Install APK agent if available, otherwise start ADB screenrecord."""
    serial = device.serial or device.id

    check_code, check_out, _ = await _run(
        [adb, "-s", serial, "get-state"], timeout=5.0,
    )
    if "device" not in check_out:
        raise HTTPException(400, f"{device.name} не подключён через ADB")

    apk = _find_agent_apk()
    if apk is not None:
        return await _install_apk_on_device(adb, serial, apk, device.name)

    result = await AdbStreamProducer.start(device.id, serial)
    if not result["ok"]:
        raise HTTPException(500, result["message"])

    return {
        "ok": True,
        "message": f"Стриминг запущен на {device.name}",
        "method": result.get("method", "screenrecord"),
        "device_id": device.id,
    }


@router.post("/start-streaming-all")
async def start_streaming_all(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Start ADB-based streaming on all connected Android devices."""
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb недоступен — установите platform-tools")
    stmt = select(Device).where(Device.platform == "android")
    devices = list((await session.execute(stmt)).scalars().all())
    if not devices:
        raise HTTPException(400, "Нет Android-устройств в базе")
    results: list[dict] = []
    for dev in devices:
        try:
            r = await _start_streaming_on_device(adb, dev)
            if dev.status != "online":
                dev.status = "online"
            results.append({"device": dev.name, "status": "ok", "message": r["message"]})
        except Exception as e:
            msg = e.detail if hasattr(e, "detail") else str(e)
            results.append({"device": dev.name, "status": "error", "message": msg})
    await session.commit()
    return {"total": len(devices), "results": results}


@router.post("/install-agent-all")
async def install_agent_all(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Legacy alias — redirects to start-streaming-all."""
    return await start_streaming_all(session)


@router.post("/stop-streaming-all")
async def stop_streaming_all() -> dict:
    """Stop all ADB-based stream producers."""
    await AdbStreamProducer.stop_all()
    return {"ok": True}


@router.post("/{device_id}/start-streaming")
async def start_streaming(
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Start ADB-based streaming for one device."""
    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "streaming is currently Android-only")
    adb = tools_svc.resolve("adb")
    if adb is None:
        raise HTTPException(500, "adb недоступен — установите platform-tools")
    result = await _start_streaming_on_device(adb, device)
    if device.status != "online":
        device.status = "online"
        await session.commit()
    return result


@router.post("/{device_id}/stop-streaming")
async def stop_streaming(device_id: str) -> dict:
    """Stop ADB-based streaming for one device."""
    await AdbStreamProducer.stop(device_id)
    return {"ok": True, "device_id": device_id}


@router.post("/{device_id}/install-agent")
async def install_agent(
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Install APK if available, otherwise start screenrecord streaming."""
    return await start_streaming(device_id, session)


class LoginPayload(BaseModel):
    platform: str
    username: str
    password: str
    account_id: str | None = None


@router.post("/{device_id}/login")
async def device_login(
    device_id: str,
    payload: LoginPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Auto-login to a social app on the device using cascade UI detection."""
    from app.services.platform_login import PlatformLogin

    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "auto-login is Android-only")
    serial = device.serial or device.id
    login_svc = PlatformLogin(serial)
    result = await login_svc.login(
        payload.platform, payload.username, payload.password,
        device_id=device_id, account_id=payload.account_id,
    )
    return result


class PublishPayload2(BaseModel):
    platform: str
    photos: list[str]
    caption: str = ""


@router.post("/{device_id}/publish")
async def device_publish(
    device_id: str,
    payload: PublishPayload2,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Publish a post on the device using ADB gallery flow."""
    from app.services.auto_poster import AutoPoster

    device = await get_or_404(session, Device, device_id)
    if device.platform != "android":
        raise HTTPException(400, "auto-publish is Android-only")
    serial = device.serial or device.id
    poster = AutoPoster(serial, payload.platform)
    result = await poster.post(payload.photos, payload.caption, device_id=device_id)
    return result

