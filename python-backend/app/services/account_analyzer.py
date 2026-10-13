"""Analyze a commenter's profile — gender, language, metrics, quality."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    import gender_guesser.detector as gender_guesser  # type: ignore

    _gg_detector = gender_guesser.Detector(case_sensitive=False)
except Exception:  # pragma: no cover - optional dep
    _gg_detector = None

try:
    from langdetect import DetectorFactory, detect  # type: ignore

    DetectorFactory.seed = 0
except Exception:  # pragma: no cover - optional dep
    detect = None  # type: ignore


_MALE_TOKENS = {"male", "mostly_male"}
_FEMALE_TOKENS = {"female", "mostly_female"}


class AccountAnalyzer:
    """Evaluate a commenter's profile and decide whether to store the comment."""

    def analyze(
        self,
        profile_data: dict[str, Any] | None,
        comment_text: str | None,
    ) -> dict[str, Any]:
        profile = profile_data or {}

        gender = self._detect_gender(profile)
        language = self._detect_language(comment_text, profile)
        metrics = self._calculate_metrics(profile)
        quality = self._assess_quality(metrics)

        should_save = gender == "male" and quality == "quality"
        reason = self._reason(gender, quality)

        return {
            "gender": gender,
            "language": language,
            "metrics": metrics,
            "quality": quality,
            "should_save": should_save,
            "reason": reason,
        }

    def _detect_gender(self, profile: dict[str, Any]) -> str:
        name = (profile.get("full_name") or profile.get("name") or "").strip()
        if not name:
            return "unknown"
        first = name.split()[0]
        if _gg_detector is None:
            return "unknown"
        guess = _gg_detector.get_gender(first)
        if guess in _MALE_TOKENS:
            return "male"
        if guess in _FEMALE_TOKENS:
            return "female"
        return "unknown"

    def _detect_language(
        self, comment_text: str | None, profile: dict[str, Any]
    ) -> str | None:
        sample = (comment_text or "").strip()
        if not sample:
            sample = (profile.get("bio") or "").strip()
        if not sample or detect is None:
            return None
        try:
            return detect(sample)
        except Exception:
            return None

    def _calculate_metrics(self, profile: dict[str, Any]) -> dict[str, Any]:
        followers = int(profile.get("followers") or 0)
        following = int(profile.get("following") or 0)
        posts = int(profile.get("posts") or profile.get("media_count") or 0)

        age_days = 0
        created_raw = profile.get("created_at") or profile.get("account_created_at")
        if created_raw:
            created = self._parse_dt(created_raw)
            if created is not None:
                now = datetime.now(timezone.utc)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_days = max(0, (now - created).days)

        ratio = (followers / following) if following > 0 else float(followers)
        has_avatar = bool(profile.get("has_avatar") or profile.get("avatar_url"))
        verified = bool(profile.get("verified") or profile.get("is_verified"))

        return {
            "followers": followers,
            "following": following,
            "posts": posts,
            "account_age_days": age_days,
            "ratio": round(ratio, 4),
            "has_avatar": has_avatar,
            "verified": verified,
        }

    def _assess_quality(self, metrics: dict[str, Any]) -> str:
        followers = metrics["followers"]
        posts = metrics["posts"]
        age_days = metrics["account_age_days"]
        ratio = metrics["ratio"]

        if ratio < 0.05 and followers < 10:
            return "bot"
        if posts == 0:
            return "inactive"
        if age_days < 30 or ratio > 50:
            return "suspicious"
        return "quality"

    def _reason(self, gender: str, quality: str) -> str:
        if gender != "male":
            return f"gender={gender}"
        if quality != "quality":
            return f"quality={quality}"
        return "male+quality"

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except Exception:
                return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None
        return None


account_analyzer = AccountAnalyzer()
