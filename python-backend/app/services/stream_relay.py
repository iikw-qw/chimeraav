"""H.264 NAL-unit relay logic.

The Android agent sends one NAL unit per WebSocket binary frame. Each frame
on the wire is the raw NAL payload with its 4-byte Annex-B start code
(0x00 00 00 01) prepended — same format the WebCodecs VideoDecoder expects.

This module handles three things:

1. NAL-type detection (so we know whether to update SPS/PPS, and whether
   a frame is an I-frame for backpressure recovery).
2. Fan-out: copy each frame into every viewer's queue without blocking the
   producer. If a viewer is too slow we drop P-frames and resume on the next
   I-frame; the viewer's decoder is then re-seeded with SPS+PPS.
3. Bookkeeping: update StreamStats on every frame so the REST API can
   report fps/bitrate/resolution/viewers in real time.

NB: we deliberately do NOT decode on the server. Zero-copy fan-out is what
keeps end-to-end latency under 150 ms.
"""

from __future__ import annotations

import asyncio
import logging

from .stream_manager import ActiveStream, ViewerQueue

logger = logging.getLogger("chimera.stream_relay")

# NAL unit types (H.264 spec, table 7-1)
NAL_TYPE_SPS = 7
NAL_TYPE_PPS = 8
NAL_TYPE_IDR = 5  # I-frame (Instantaneous Decoder Refresh)


def _nal_type(frame: bytes) -> int:
    """Return the NAL unit type of an Annex-B-prefixed frame.

    Frame layout: [0x00 0x00 0x00 0x01 | nal_header | payload]
    nal_header byte: forbidden_zero_bit(1) | nal_ref_idc(2) | nal_unit_type(5)
    """
    if len(frame) < 5:
        return -1
    # locate start code (3 or 4 bytes)
    start = 4 if frame[:4] == b"\x00\x00\x00\x01" else (
        3 if frame[:3] == b"\x00\x00\x01" else 0
    )
    if start >= len(frame):
        return -1
    return frame[start] & 0x1F


def is_keyframe(frame: bytes) -> bool:
    return _nal_type(frame) in (NAL_TYPE_IDR, NAL_TYPE_SPS, NAL_TYPE_PPS)


async def handle_producer_frame(stream: ActiveStream, frame: bytes) -> None:
    """Called by the producer-side WS handler for every binary frame received
    from the Android agent."""
    if not frame:
        return

    nt = _nal_type(frame)
    if nt == NAL_TYPE_SPS:
        stream.sps = frame
    elif nt == NAL_TYPE_PPS:
        stream.pps = frame

    is_idr = nt in (NAL_TYPE_IDR, NAL_TYPE_SPS, NAL_TYPE_PPS)
    stream.record_frame(frame, is_keyframe=is_idr)

    # Fan-out — never await on a single viewer. If a viewer's queue is full,
    # mark it `needs_keyframe` and drop the frame for that viewer.
    for viewer in list(stream.viewers):
        await _push_to_viewer(viewer, frame, is_idr)


async def _push_to_viewer(viewer: ViewerQueue, frame: bytes, is_idr: bool) -> None:
    if viewer.needs_keyframe:
        if not is_idr:
            return  # wait for the next I-frame to re-sync
        viewer.needs_keyframe = False
    try:
        viewer.queue.put_nowait(frame)
    except asyncio.QueueFull:
        viewer.dropped_frames += 1
        viewer.needs_keyframe = True  # drain at next I-frame


async def prime_new_viewer(stream: ActiveStream, viewer: ViewerQueue) -> None:
    """When a new viewer joins, send them SPS+PPS first so their decoder can
    initialise — they then wait for the next I-frame (existing logic in
    `_push_to_viewer` thanks to `needs_keyframe=True`)."""
    if stream.sps is not None:
        await viewer.queue.put(stream.sps)
    if stream.pps is not None:
        await viewer.queue.put(stream.pps)
