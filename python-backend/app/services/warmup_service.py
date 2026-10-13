"""Warmup service — runs human-like activity sessions on an account.

A warmup session cycles through randomised actions (feed scroll, profile
visit, like, follow) sized to the device screen, with natural pauses and
the full HumanBehaviorEngine treatment. Likes/follows/comments/reposts/
reading pauses are weighted so that on average a session looks like a
person scrolling their feed for a few minutes.

The service delegates every input to the backend's `/human_*` endpoints
(via direct adb here, to avoid a network round-trip), so every action
goes through jitter + bezier cursor broadcast and is visible on the
device if native pointer overlay is enabled.

Captcha detection hook: if the caller (or UI analyzer) reports a captcha
screen, `CaptchaSolver` from antidetect.py handles reCAPTCHA/hCaptcha.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

from app.api._hub import hub
from app.database import SessionLocal
from app.models.action_log import ActionLog
from app.models.comment import Comment
from app.models.device import Device
from app.services import tools as tools_svc
from app.services.antidetect import captcha_solver, human_behavior

try:  # gender inference is best-effort; module is optional
    import gender_guesser.detector as _gg_module  # type: ignore

    _GENDER_DETECTOR = _gg_module.Detector(case_sensitive=False)
except Exception:  # pragma: no cover
    _GENDER_DETECTOR = None

_MALE_TOKENS = {"male", "mostly_male"}


def _infer_gender(username: str | None) -> str:
    """Best-effort gender inference. Returns 'male' / 'female' / 'unknown'."""
    if not username or _GENDER_DETECTOR is None:
        return "unknown"
    clean = "".join(ch if ch.isalpha() else " " for ch in username).strip()
    if not clean:
        return "unknown"
    first = clean.split()[0]
    if len(first) < 2:
        return "unknown"
    g = _GENDER_DETECTOR.get_gender(first.capitalize())
    if g in _MALE_TOKENS:
        return "male"
    if g in {"female", "mostly_female"}:
        return "female"
    return "unknown"


@dataclass
class WarmupConfig:
    duration_seconds: int = 300            # total budget
    scroll_weight: int = 60                # % probability of a feed scroll
    profile_visit_weight: int = 15         # tap random avatar
    like_weight: int = 15                  # double-tap center
    follow_weight: int = 5                 # tap follow button area
    random_tap_weight: int = 5             # "distracted" tap
    repost_weight: int = 0                 # share button area
    like_unlike_weight: int = 5            # like then unlike (mistaken-tap)
    view_story_weight: int = 10            # watch stories
    comment_weight: int = 5                # leave short comment
    big_pause_weight: int = 15             # simulate user distraction
    follow_ta_weight: int = 10             # follow target audience by hashtag
    surf_weight: int = 15                  # pure feed surfing with random likes
    max_actions: int = 200                 # hard cap
    min_idle_between: float = 0.8          # seconds
    hashtags: list[str] = field(default_factory=list)


@dataclass
class WarmupReport:
    device_id: str
    started_at: float
    ended_at: float = 0.0
    actions: dict[str, int] = field(default_factory=dict)
    captchas_solved: int = 0
    errors: list[str] = field(default_factory=list)

    def bump(self, key: str) -> None:
        self.actions[key] = self.actions.get(key, 0) + 1


async def _run_adb(cmd: list[str], timeout: float = 8.0) -> tuple[int, str]:
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
    return proc.returncode or 0, (stdout + stderr).decode("utf-8", errors="replace")


async def _screen_size(adb: str, serial: str) -> tuple[int, int]:
    code, out = await _run_adb([adb, "-s", serial, "shell", "wm", "size"], timeout=5.0)
    if code == 0:
        for line in out.splitlines():
            if "Physical size:" in line or "Override size:" in line:
                try:
                    _, dims = line.split(":", 1)
                    w_s, h_s = dims.strip().split("x", 1)
                    return int(w_s), int(h_s)
                except ValueError:
                    continue
    return 1080, 1920  # sane fallback


async def _broadcast_cursor(
    device_id: str, kind: str, *, x: int | None = None, y: int | None = None,
    waypoints: list[dict] | None = None, duration_ms: int | None = None,
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
        pass


async def _human_tap(adb: str, serial: str, device_id: str, x: int, y: int) -> None:
    jx, jy = human_behavior.jittered_tap(x, y)
    press = human_behavior.tap_press_ms()
    await _broadcast_cursor(device_id, "tap", x=jx, y=jy, duration_ms=press)
    await _run_adb(
        [adb, "-s", serial, "shell", "input", "swipe",
         str(jx), str(jy), str(jx), str(jy), str(press)],
        timeout=5.0,
    )


async def _human_swipe(
    adb: str, serial: str, device_id: str,
    x1: int, y1: int, x2: int, y2: int,
) -> None:
    plan = human_behavior.humanize_swipe(x1, y1, x2, y2)
    await _broadcast_cursor(
        device_id, "swipe",
        waypoints=plan["waypoints"], duration_ms=plan["duration_ms"],
    )
    await _run_adb(
        [adb, "-s", serial, "shell", "input", "swipe",
         str(plan["x1"]), str(plan["y1"]),
         str(plan["x2"]), str(plan["y2"]),
         str(plan["duration_ms"])],
        timeout=max(6.0, plan["duration_ms"] / 1000 + 3),
    )


class WarmupService:
    """Run warmup sessions for one device/account at a time."""

    async def run(
        self,
        device_id: str,
        *,
        account_id: str | None = None,
        config: WarmupConfig | None = None,
    ) -> WarmupReport:
        cfg = config or WarmupConfig()
        report = WarmupReport(device_id=device_id, started_at=time.time())

        async with SessionLocal() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")
            if device.platform != "android":
                raise ValueError("warmup is Android-only")
            serial = device.serial or device.id

        adb = tools_svc.resolve("adb")
        if adb is None:
            raise RuntimeError("adb unavailable")

        w, h = await _screen_size(adb, serial)
        deadline = report.started_at + cfg.duration_seconds
        actions_performed = 0

        await hub.broadcast(
            "warmup",
            {"event": "started", "device_id": device_id, "account_id": account_id, "config": {
                "duration_seconds": cfg.duration_seconds, "screen": [w, h],
            }},
        )
        await hub.broadcast(
            "notifications",
            {
                "level": "info",
                "title": "Прогрев",
                "message": f"Запущен прогрев на {cfg.duration_seconds // 60} мин",
                "device_id": device_id,
                "account_id": account_id,
            },
        )

        # daytime factor: at night scale everything down; during the day,
        # stay at ~1.0. This avoids "robotic 24/7" signatures.
        day_factor = human_behavior.daytime_factor()
        scaled_max = max(10, int(cfg.max_actions * day_factor))

        while time.time() < deadline and actions_performed < scaled_max:
            action = self._pick_action(cfg)
            try:
                if action == "scroll":
                    await self._feed_scroll(adb, serial, device_id, w, h)
                elif action == "profile":
                    await self._profile_visit(
                        adb, serial, device_id, w, h, account_id=account_id,
                    )
                elif action == "like":
                    await self._double_tap_like(adb, serial, device_id, w, h)
                elif action == "follow":
                    await self._tap_follow(adb, serial, device_id, w, h)
                elif action == "random_tap":
                    await self._random_tap(adb, serial, device_id, w, h)
                elif action == "like_unlike":
                    await self._like_then_unlike(adb, serial, device_id, w, h)
                elif action == "repost":
                    await self._tap_repost(adb, serial, device_id, w, h)
                elif action == "view_story":
                    await self._view_story(adb, serial, device_id, w, h)
                elif action == "comment":
                    await self._leave_comment(adb, serial, device_id, w, h)
                elif action == "follow_ta":
                    await self._follow_target_audience(
                        adb, serial, device_id, w, h,
                        hashtags=cfg.hashtags or ["travel", "food", "fitness"],
                    )
                elif action == "surf":
                    await self._surf_feed(adb, serial, device_id, w, h)
                elif action == "big_pause":
                    pause = random.uniform(10, 45)
                    await asyncio.sleep(pause)
                report.bump(action)
                actions_performed += 1
                await self._log_action(device_id, account_id, action)
            except Exception as exc:
                report.errors.append(f"{action}: {exc!r}")

            # Poisson-style pause between actions (λ=1.5, range 0.5-4s)
            poisson_delay = min(4.0, max(0.5, random.expovariate(1.5)))
            pause = poisson_delay + cfg.min_idle_between
            if human_behavior.should_idle():
                pause += human_behavior.idle_seconds()
            await asyncio.sleep(pause)

            if actions_performed % 10 == 0:
                await hub.broadcast(
                    "warmup",
                    {"event": "progress", "device_id": device_id,
                     "actions": actions_performed, "counts": report.actions},
                )

        report.ended_at = time.time()
        await hub.broadcast(
            "warmup",
            {"event": "finished", "device_id": device_id, "account_id": account_id,
             "counts": report.actions, "errors": report.errors,
             "duration_s": int(report.ended_at - report.started_at)},
        )
        total_actions = sum(report.actions.values())
        await hub.broadcast(
            "notifications",
            {
                "level": "danger" if report.errors else "success",
                "title": "Прогрев завершён",
                "message": (
                    f"Действий: {total_actions}, ошибок: {len(report.errors)}"
                    if report.errors
                    else f"Прогрев успешно завершён, действий: {total_actions}"
                ),
                "device_id": device_id,
                "account_id": account_id,
            },
        )
        return report

    async def solve_captcha_if_needed(
        self,
        *,
        site_key: str,
        page_url: str,
        provider: str = "recaptcha",
    ) -> str | None:
        """Call 2Captcha. Caller decides when to invoke (after detecting a
        challenge via UI analyzer). Returns the solved token or None."""
        try:
            if provider == "hcaptcha":
                return await captcha_solver.solve_hcaptcha(site_key, page_url)
            return await captcha_solver.solve_recaptcha(site_key, page_url)
        except Exception:
            return None

    # --- Action primitives ---------------------------------------------------

    @staticmethod
    def _pick_action(cfg: WarmupConfig) -> str:
        bag = (
            ["scroll"] * cfg.scroll_weight
            + ["profile"] * cfg.profile_visit_weight
            + ["like"] * cfg.like_weight
            + ["follow"] * cfg.follow_weight
            + ["random_tap"] * cfg.random_tap_weight
            + ["like_unlike"] * cfg.like_unlike_weight
            + ["repost"] * cfg.repost_weight
            + ["view_story"] * cfg.view_story_weight
            + ["comment"] * cfg.comment_weight
            + ["big_pause"] * cfg.big_pause_weight
            + ["follow_ta"] * cfg.follow_ta_weight
            + ["surf"] * cfg.surf_weight
        )
        return random.choice(bag) if bag else "scroll"

    async def _feed_scroll(self, adb: str, serial: str, device_id: str, w: int, h: int) -> None:
        # upward flick from ~70% to ~25% screen height, slight x variance
        cx = w // 2 + random.randint(-w // 8, w // 8)
        y1 = int(h * random.uniform(0.62, 0.78))
        y2 = int(h * random.uniform(0.20, 0.32))
        await _human_swipe(adb, serial, device_id, cx, y1, cx + random.randint(-20, 20), y2)

    async def _profile_visit(
        self,
        adb: str,
        serial: str,
        device_id: str,
        w: int,
        h: int,
        *,
        account_id: str | None = None,
    ) -> None:
        # Tap on a random avatar area (top-left of a post card).
        # Cards start at ~12% height; avatar is ~6-8% wide, ~10% from left.
        avatar_x = int(w * random.uniform(0.06, 0.14))
        avatar_y = int(h * random.uniform(0.15, 0.55))
        await _human_tap(adb, serial, device_id, avatar_x, avatar_y)
        # "read" profile + first post — gives time for any UI analyzer hook to run
        await asyncio.sleep(human_behavior.reading_pause(180))
        # tap into the first post for a closer look
        post_x = int(w * random.uniform(0.15, 0.35))
        post_y = int(h * random.uniform(0.30, 0.45))
        await _human_tap(adb, serial, device_id, post_x, post_y)
        await asyncio.sleep(human_behavior.reading_pause(220))

        # Record the visit + best-effort gender so the user pool fills up.
        # Username here is a synthetic placeholder until a UI analyzer feeds
        # us the real handle; the schema still flows.
        synthetic_username = f"user_{random.randint(10_000, 999_999)}"
        await self._record_observed_user(
            account_id=account_id,
            username=synthetic_username,
            note="warmup.profile_visit",
        )

        # back to profile, then back to feed
        await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)
        await asyncio.sleep(random.uniform(0.4, 1.1))
        await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)

    async def _double_tap_like(self, adb: str, serial: str, device_id: str, w: int, h: int) -> None:
        cx = w // 2 + random.randint(-20, 20)
        cy = int(h * random.uniform(0.40, 0.55))
        await _human_tap(adb, serial, device_id, cx, cy)
        await asyncio.sleep(random.uniform(0.08, 0.18))
        await _human_tap(adb, serial, device_id, cx, cy)

    async def _tap_follow(self, adb: str, serial: str, device_id: str, w: int, h: int) -> None:
        # This only works when a profile is actually open. Use after
        # profile_visit for a natural sequence.
        bx = int(w * random.uniform(0.65, 0.85))
        by = int(h * random.uniform(0.18, 0.24))
        await _human_tap(adb, serial, device_id, bx, by)

    async def _random_tap(self, adb: str, serial: str, device_id: str, w: int, h: int) -> None:
        # Distracted poke somewhere safe — small area near the top bar.
        rx = random.randint(int(w * 0.2), int(w * 0.8))
        ry = random.randint(int(h * 0.05), int(h * 0.1))
        await _human_tap(adb, serial, device_id, rx, ry)

    async def _like_then_unlike(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
    ) -> None:
        """Mistaken double-tap: like, then immediately unlike. Looks like
        a real-user 'oops' moment and avoids over-liking."""
        await self._double_tap_like(adb, serial, device_id, w, h)
        await asyncio.sleep(random.uniform(0.6, 1.4))
        # tap the heart icon (typically bottom-left of post, ~10% from left,
        # ~70% down) to toggle off
        hx = int(w * random.uniform(0.07, 0.12))
        hy = int(h * random.uniform(0.66, 0.74))
        await _human_tap(adb, serial, device_id, hx, hy)

    async def _tap_repost(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
    ) -> None:
        """Open the share sheet and back out — counts as a repost intent."""
        sx = int(w * random.uniform(0.32, 0.42))
        sy = int(h * random.uniform(0.66, 0.74))
        await _human_tap(adb, serial, device_id, sx, sy)
        await asyncio.sleep(random.uniform(0.7, 1.3))
        await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)

    async def _view_story(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
    ) -> None:
        """Tap a story circle at the top of the feed, watch, then return."""
        story_x = random.randint(int(w * 0.05), int(w * 0.25))
        story_y = random.randint(int(h * 0.04), int(h * 0.09))
        await _human_tap(adb, serial, device_id, story_x, story_y)
        await asyncio.sleep(random.uniform(3, 8))
        await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _leave_comment(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
    ) -> None:
        """Leave a short emoji comment on the current post (rare action)."""
        if random.random() > 0.3:
            return
        _COMMENTS = ["🔥", "👏", "❤️", "Nice!", "Wow", "Cool!", "Amazing!", "Great post!", "Love it"]
        comment_btn_x = int(w * random.uniform(0.12, 0.18))
        comment_btn_y = int(h * random.uniform(0.66, 0.74))
        await _human_tap(adb, serial, device_id, comment_btn_x, comment_btn_y)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        comment = random.choice(_COMMENTS)
        plan = human_behavior.typing_plan(comment)
        for ch, delay in plan:
            if ch == " ":
                safe = "%s"
            elif ch in ("'", '"', "\\", "`", "&", ";"):
                safe = f"\\{ch}"
            else:
                safe = ch
            await _run_adb(
                [adb, "-s", serial, "shell", "input", "text", safe], timeout=4.0,
            )
            await asyncio.sleep(delay)
        await asyncio.sleep(0.5)
        await _run_adb(
            [adb, "-s", serial, "shell", "input", "keyevent", "66"], timeout=3.0,
        )
        await asyncio.sleep(random.uniform(1.0, 2.0))

    async def _follow_target_audience(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
        *, hashtags: list[str], max_follows: int = 3,
    ) -> int:
        from app.services.ui_finder import UIFinder

        ui = UIFinder(serial, adb)
        follows = 0
        tag = random.choice(hashtags) if hashtags else "explore"

        search = await ui.wait_find([
            {"content_desc": "Search"},
            {"text": "Search"},
            {"content_desc": "Explore"},
        ], timeout=5)
        if search:
            await _human_tap(adb, serial, device_id, search["x"], search["y"])
            await asyncio.sleep(1.5)

            plan = human_behavior.typing_plan(f"#{tag}")
            for ch, delay in plan:
                safe = "%s" if ch == " " else ch
                await _run_adb(
                    [adb, "-s", serial, "shell", "input", "text", safe], timeout=4.0,
                )
                await asyncio.sleep(delay)
            await asyncio.sleep(2)

            await _human_tap(adb, serial, device_id, w // 2, 300)
            await asyncio.sleep(2)

            for _ in range(random.randint(2, 4)):
                if follows >= max_follows:
                    break
                await _human_tap(
                    adb, serial, device_id,
                    random.randint(100, w - 100),
                    random.randint(300, 700),
                )
                await asyncio.sleep(2)

                await _human_tap(adb, serial, device_id, 50, random.randint(200, 400))
                await asyncio.sleep(2)

                follow_btn = await ui.wait_find([
                    {"text": "Follow"},
                    {"text": "Подписаться"},
                ], timeout=5)
                if follow_btn:
                    await _human_tap(adb, serial, device_id, follow_btn["x"], follow_btn["y"])
                    follows += 1
                    await asyncio.sleep(random.uniform(1, 3))

                await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)
                await asyncio.sleep(1)
                await _run_adb([adb, "-s", serial, "shell", "input", "keyevent", "4"], timeout=3.0)
                await asyncio.sleep(1)

        return follows

    async def _surf_feed(
        self, adb: str, serial: str, device_id: str, w: int, h: int,
        duration_s: int = 30,
    ) -> None:
        end = time.time() + duration_s
        while time.time() < end:
            await self._feed_scroll(adb, serial, device_id, w, h)
            pause = min(4.0, max(0.5, random.expovariate(1.5)))
            await asyncio.sleep(pause)
            if random.random() < 0.25:
                cx = w // 2 + random.randint(-50, 50)
                cy = int(h * random.uniform(0.35, 0.55))
                await _human_tap(adb, serial, device_id, cx, cy)
                await asyncio.sleep(0.15)
                await _human_tap(adb, serial, device_id, cx, cy)
                await asyncio.sleep(random.uniform(1, 3))

    @staticmethod
    async def _record_observed_user(
        *,
        account_id: str | None,
        username: str | None,
        note: str,
    ) -> None:
        """Persist an observed user (liker / commenter / profile visit) into
        the comments table so the unified /users-pool picks them up. Gender
        is inferred from the handle — only confident males flow downstream."""
        if not account_id or not username:
            return
        gender = _infer_gender(username)
        try:
            async with SessionLocal() as session:
                session.add(
                    Comment(
                        account_id=account_id,
                        platform="warmup",
                        commenter_username=username,
                        commenter_gender=gender,
                        comment_text=note,
                        commenter_metrics={"source": note},
                    )
                )
                await session.commit()
        except Exception:
            pass

    @staticmethod
    async def _log_action(device_id: str, account_id: str | None, action: str) -> None:
        try:
            async with SessionLocal() as session:
                session.add(ActionLog(
                    device_id=device_id,
                    action_type=f"warmup.{action}",
                    details={"account_id": account_id} if account_id else None,
                ))
                await session.commit()
        except Exception:
            pass


warmup_service = WarmupService()
