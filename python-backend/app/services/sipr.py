"""SIPR — Smart Image Pool Rotator. Select least-worn photos from a dataset.

Supports a *mixing* strategy: successive posts pull different index permutations
(e.g. 1,3,5 then 2,4,6 then 2,3,1) so the material is stretched further.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import desc, select

from app.database import SessionLocal
from app.models.dataset import Dataset
from app.models.post import Post

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}

MixStrategy = Literal["wear", "interleave", "random_offset", "stride", "cross", "smart"]


class SIPRManager:
    """Rotate photos by wear count, avoiding the most recently published ones.

    Mix strategies (tracked per-dataset in wear_map['__cycle__']):
      wear           — classic: least-worn first (default)
      interleave     — odd indices one post, even the next, then shifted mixes
      random_offset  — random starting offset + stride, rotates across posts
      stride         — fixed stride 2 with a rotating offset (exact "1,3,5 / 2,4,6" pattern)
      cross          — rotating offset window, stretches material maximally
                       (post 1 -> 1,3,5; post 2 -> 2,4,6; post 3 -> 2,3,1; then shifts)
      smart          — cross + wear-weighted tiebreak; best material longevity
    """

    def __init__(self, dataset_id: str, *, account_id: str | None = None) -> None:
        self.dataset_id = dataset_id
        self.account_id = account_id

    async def select_photos(
        self,
        count: int = 3,
        *,
        strategy: MixStrategy = "wear",
        media_kind: Literal["photo", "video", "any"] = "photo",
    ) -> list[str]:
        async with SessionLocal() as session:
            dataset = await session.get(Dataset, self.dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset {self.dataset_id} not found")

            all_files = self._list_media(dataset.path, media_kind)
            if not all_files:
                return []

            wear_map: dict[str, int] = dict(dataset.wear_map or {})
            for f in all_files:
                wear_map.setdefault(f, 0)

            # Cycle counter is per-account when account_id is supplied, so two
            # accounts sharing a dataset get their own rotation phase and do
            # not collide on the same indices. Falls back to a global cycle
            # for backwards compatibility.
            cycle_key = (
                f"__cycle__:{self.account_id}" if self.account_id else "__cycle__"
            )
            cycle = int(wear_map.get(cycle_key, 0))

            recent_stmt = (
                select(Post.photos)
                .where(Post.sipr_dataset_id == self.dataset_id)
                .order_by(desc(Post.published_at))
                .limit(3)
            )
            recent_rows = (await session.execute(recent_stmt)).scalars().all()
            recent: set[str] = set()
            for row in recent_rows:
                if isinstance(row, list):
                    recent.update(str(p) for p in row)

            chosen = self._pick(
                all_files, wear_map, recent, count, strategy, cycle
            )

            for f in chosen:
                wear_map[f] = wear_map.get(f, 0) + 1
            wear_map[cycle_key] = cycle + 1

            dataset.wear_map = wear_map
            await session.commit()
            return chosen

    @staticmethod
    def _pick(
        files: list[str],
        wear_map: dict[str, int],
        recent: set[str],
        count: int,
        strategy: MixStrategy,
        cycle: int,
    ) -> list[str]:
        n = len(files)
        if n == 0:
            return []

        if strategy == "stride":
            # "1,3,5 -> 2,4,6 -> 2,3,1" — alternate start, stride of 2,
            # then collapse stride on the third cycle for variety.
            start = cycle % 2
            stride = 2 if cycle % 3 != 2 else 1
            indices: list[int] = []
            i = start
            while len(indices) < count and i < n:
                indices.append(i)
                i += stride
            # wrap-around if underfilled
            i = 0
            while len(indices) < count and i < n:
                if i not in indices:
                    indices.append(i)
                i += 1
            return [files[k] for k in indices[:count]]

        if strategy in ("cross", "smart"):
            # Deterministic rotating window that stretches N files across
            # many posts. For count=3:
            #   post 0 -> 0,2,4   (1,3,5 in 1-based)
            #   post 1 -> 1,3,5   (2,4,6 in 1-based)
            #   post 2 -> 1,2,0   (2,3,1 in 1-based)
            #   post 3 -> 3,0,2   (then rotates)
            # Each cycle picks a different stride and offset so the same 3
            # files don't co-occur in consecutive posts.
            stride = (cycle % 3) + 1         # 1, 2, 3, 1, 2, 3, ...
            offset = (cycle * 2) % max(1, n) # drift across dataset
            raw = [(offset + k * stride) % n for k in range(count)]
            # dedupe preserving order
            seen: set[int] = set()
            uniq: list[int] = []
            for k in raw:
                if k not in seen:
                    seen.add(k)
                    uniq.append(k)
            # top up from least-worn not-in-recent
            if len(uniq) < count:
                fill = sorted(
                    (i for i in range(n) if i not in seen and files[i] not in recent),
                    key=lambda i: wear_map.get(files[i], 0),
                )
                for i in fill:
                    uniq.append(i)
                    if len(uniq) >= count:
                        break
            if strategy == "smart":
                # swap any index whose file is in `recent` for the least-worn
                # eligible one, so never-worn material gets prioritised while
                # keeping the deterministic rotation pattern.
                eligible_sorted = sorted(
                    range(n), key=lambda i: wear_map.get(files[i], 0)
                )
                for pos, i in enumerate(list(uniq)):
                    if files[i] in recent:
                        for alt in eligible_sorted:
                            if alt not in uniq and files[alt] not in recent:
                                uniq[pos] = alt
                                break
            return [files[k] for k in uniq[:count]]

        if strategy == "interleave":
            evens = [f for idx, f in enumerate(files) if idx % 2 == (cycle % 2)]
            odds = [f for idx, f in enumerate(files) if idx % 2 != (cycle % 2)]
            pool = (evens + odds) if cycle % 3 != 2 else (odds + evens[::-1])
            pool = [p for p in pool if p not in recent] or pool
            return pool[:count]

        if strategy == "random_offset":
            offset = random.randint(0, max(0, n - 1))
            stride = random.choice([1, 2, 3])
            indices = [(offset + k * stride) % n for k in range(count)]
            # dedupe while preserving order
            seen: set[int] = set()
            uniq = [i for i in indices if not (i in seen or seen.add(i))]
            while len(uniq) < count and len(uniq) < n:
                uniq.append((uniq[-1] + 1) % n)
            return [files[k] for k in uniq[:count]]

        # default: wear-based rotation
        eligible = [f for f in files if f not in recent] or list(files)
        eligible.sort(key=lambda p: wear_map.get(p, 0))
        top_n = max(count, int(len(eligible) * 0.3))
        pool = eligible[:top_n]
        random.shuffle(pool)
        return pool[: min(count, len(pool))]

    async def get_stats(self) -> dict[str, Any]:
        async with SessionLocal() as session:
            dataset = await session.get(Dataset, self.dataset_id)
            if dataset is None:
                raise ValueError(f"Dataset {self.dataset_id} not found")

            photos = self._list_media(dataset.path, "photo")
            wear_map: dict[str, int] = dict(dataset.wear_map or {})
            wear_map.pop("__cycle__", None)
            used = [wear_map.get(p, 0) for p in photos]
            total = len(photos)
            touched = sum(1 for v in used if v > 0)

            return {
                "dataset_id": self.dataset_id,
                "photo_count": total,
                "used_count": touched,
                "max_wear": max(used) if used else 0,
                "avg_wear": (sum(used) / total) if total else 0,
            }

    async def reset_wear(self) -> None:
        async with SessionLocal() as session:
            dataset = await session.get(Dataset, self.dataset_id)
            if dataset is None:
                return
            dataset.wear_map = {}
            await session.commit()

    @staticmethod
    def _list_media(
        path: str, kind: Literal["photo", "video", "any"]
    ) -> list[str]:
        root = Path(path)
        if not root.exists():
            return []
        if kind == "video":
            exts = _VIDEO_EXTS
        elif kind == "any":
            exts = _IMAGE_EXTS | _VIDEO_EXTS
        else:
            exts = _IMAGE_EXTS
        return sorted(
            str(p)
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in exts
        )
