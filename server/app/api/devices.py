"""
CRUD API для устройств + agent install + proxy setup + antidetect.
Зависит от: models/device, schemas/device, deps, adb_proxy, proxy_setup
"""

import os
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Device).where(Device.user_id == current_user.id)
    if device_type:
        query = query.where(Device.device_type == device_type)
    if status:
        query = query.where(Device.status == status)
    query = query.order_by(Device.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [DeviceResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/count")
async def count_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Device.id)).where(Device.user_id == current_user.id)
    )
    total = result.scalar()
    online = await db.execute(
        select(func.count(Device.id)).where(Device.user_id == current_user.id, Device.status == "online")
    )
    return {"total": total, "online": online.scalar()}


@router.post("", response_model=DeviceResponse, status_code=201)
async def create_device(
    data: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    device = Device(user_id=current_user.id, **data.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.get("/discover")
async def discover_devices(current_user: User = Depends(get_current_user)):
    return {"devices": [], "message": "Scanning network for devices..."}


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse.model_validate(device)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(device, field, value)

    await db.flush()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.delete("/{device_id}")
async def delete_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    return {"message": "Device deleted"}


@router.post("/{device_id}/command")
async def send_device_command(
    device_id: UUID,
    command: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from app.services.redis_client import redis_client
    await redis_client.publish(f"device:{device_id}:commands", command)
    return {"message": "Command sent", "device_id": str(device_id)}


@router.post("/{device_id}/install-agent")
async def install_agent(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not device.serial_number:
        raise HTTPException(status_code=400, detail="Device has no serial number")

    jar = os.path.join(os.path.dirname(__file__), "..", "..", "agent-android", "scrcpy-server.jar")
    if not os.path.exists(jar):
        raise HTTPException(status_code=404, detail="scrcpy-server.jar not found")

    from app.services.adb_proxy import adb_push
    ok = await adb_push(device.serial_number, jar, "/data/local/tmp/scrcpy-server.jar")
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to push agent to device")
    return {"ok": True, "message": f"Agent installed on {device.name}"}


@router.post("/install-agent-all")
async def install_agent_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.user_id == current_user.id, Device.status == "online")
    )
    devices = result.scalars().all()

    jar = os.path.join(os.path.dirname(__file__), "..", "..", "agent-android", "scrcpy-server.jar")
    if not os.path.exists(jar):
        raise HTTPException(status_code=404, detail="scrcpy-server.jar not found")

    from app.services.adb_proxy import adb_push
    results = []
    for d in devices:
        if not d.serial_number:
            results.append({"device": d.name, "status": "skipped", "msg": "no serial"})
            continue
        ok = await adb_push(d.serial_number, jar, "/data/local/tmp/scrcpy-server.jar")
        results.append({"device": d.name, "status": "ok" if ok else "error"})
    return {"total": len(devices), "results": results}


@router.post("/{device_id}/set-proxy")
async def set_device_proxy(
    device_id: UUID,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device or not device.serial_number:
        raise HTTPException(status_code=404, detail="Device not found or no serial")

    from app.services.proxy_setup import ProxySetup
    ps = ProxySetup(device.serial_number)
    host = data.get("host", "")
    port = int(data.get("port", 0))
    if host and port:
        return ps.set_wifi_proxy(host, port)
    return ps.clear_proxy()


@router.get("/{device_id}/check-ip")
async def check_device_ip(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device or not device.serial_number:
        raise HTTPException(status_code=404, detail="Device not found or no serial")

    from app.services.proxy_setup import ProxySetup
    ps = ProxySetup(device.serial_number)
    return ps.get_proxy_status()


@router.get("/{device_id}/fingerprint")
async def get_device_fingerprint(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device or not device.serial_number:
        raise HTTPException(status_code=404, detail="Device not found or no serial")

    from app.services.adb_proxy import adb_shell
    serial = device.serial_number
    fp = {
        "android_id": await adb_shell(serial, "settings get secure android_id"),
        "serial": await adb_shell(serial, "getprop ro.serialno"),
        "model": await adb_shell(serial, "getprop ro.product.model"),
        "brand": await adb_shell(serial, "getprop ro.product.brand"),
        "mac": await adb_shell(serial, "cat /sys/class/net/wlan0/address 2>/dev/null"),
    }
    results = {}
    for k, v in fp.items():
        results[k] = {"value": v, "status": "ok" if v else "empty"}
    return results
