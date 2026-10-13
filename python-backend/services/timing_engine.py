"""Platform-adaptive timing engine for warmup sessions."""
from __future__ import annotations

import math
import random

PLATFORM_TIMING = {
    "instagram": {
        "feed_scroll_pause": (5, 12),
        "story_view_time": (3, 15),
        "post_view_time": (4, 10),
        "profile_browse_time": (8, 25),
        "like_probability": 0.45,
        "comment_probability": 0.03,
        "save_probability": 0.08,
        "follow_probability": 0.02,
        "story_reply_probability": 0.04,
        "reels_swipe_pause": (4, 18),
    },
    "tiktok": {
        "feed_scroll_pause": (4, 18),
        "story_view_time": (0, 0),
        "post_view_time": (4, 18),
        "profile_browse_time": (5, 15),
        "like_probability": 0.35,
        "comment_probability": 0.02,
        "save_probability": 0.06,
        "follow_probability": 0.03,
        "story_reply_probability": 0.0,
        "reels_swipe_pause": (4, 18),
    },
    "threads": {
        "feed_scroll_pause": (3, 8),
        "story_view_time": (0, 0),
        "post_view_time": (3, 8),
        "profile_browse_time": (5, 12),
        "like_probability": 0.40,
        "comment_probability": 0.05,
        "save_probability": 0.03,
        "follow_probability": 0.04,
        "story_reply_probability": 0.0,
        "reels_swipe_pause": (0, 0),
    },
    "twitter": {
        "feed_scroll_pause": (3, 8),
        "story_view_time": (0, 0),
        "post_view_time": (3, 7),
        "profile_browse_time": (5, 15),
        "like_probability": 0.30,
        "comment_probability": 0.02,
        "save_probability": 0.05,
        "follow_probability": 0.02,
        "story_reply_probability": 0.0,
        "reels_swipe_pause": (0, 0),
    },
    "facebook": {
        "feed_scroll_pause": (5, 15),
        "story_view_time": (3, 12),
        "post_view_time": (4, 12),
        "profile_browse_time": (6, 20),
        "like_probability": 0.40,
        "comment_probability": 0.03,
        "save_probability": 0.05,
        "follow_probability": 0.01,
        "story_reply_probability": 0.02,
        "reels_swipe_pause": (4, 15),
    },
    "youtube": {
        "feed_scroll_pause": (8, 30),
        "story_view_time": (0, 0),
        "post_view_time": (15, 60),
        "profile_browse_time": (5, 15),
        "like_probability": 0.25,
        "comment_probability": 0.01,
        "save_probability": 0.04,
        "follow_probability": 0.02,
        "story_reply_probability": 0.0,
        "reels_swipe_pause": (5, 20),
    },
    "linkedin": {
        "feed_scroll_pause": (4, 10),
        "story_view_time": (0, 0),
        "post_view_time": (5, 12),
        "profile_browse_time": (8, 25),
        "like_probability": 0.35,
        "comment_probability": 0.02,
        "save_probability": 0.03,
        "follow_probability": 0.03,
        "story_reply_probability": 0.0,
        "reels_swipe_pause": (0, 0),
    },
}


def get_device_profile(screen_w: int, screen_h: int) -> dict:
    """Device-adaptive timing based on screen size."""
    diagonal = math.sqrt(screen_w**2 + screen_h**2)

    if diagonal < 1800:
        return {
            "tap_duration_range": (80, 150),
            "swipe_speed_factor": 1.2,
            "scroll_pause_range": (0.8, 2.0),
            "hot_zone_px": 40,
        }
    elif diagonal < 2600:
        return {
            "tap_duration_range": (90, 180),
            "swipe_speed_factor": 1.0,
            "scroll_pause_range": (1.0, 2.5),
            "hot_zone_px": 50,
        }
    else:
        return {
            "tap_duration_range": (120, 220),
            "swipe_speed_factor": 0.8,
            "scroll_pause_range": (1.2, 3.0),
            "hot_zone_px": 70,
        }


def get_timing(platform: str, key: str) -> float:
    """Get a random value from platform timing range."""
    timing = PLATFORM_TIMING.get(platform, PLATFORM_TIMING["instagram"])
    value = timing.get(key, (1, 3))
    if isinstance(value, tuple) and len(value) == 2:
        if value[0] == 0 and value[1] == 0:
            return 0
        return random.uniform(value[0], value[1])
    return float(value)


def get_probability(platform: str, key: str) -> bool:
    """Roll probability for platform action."""
    timing = PLATFORM_TIMING.get(platform, PLATFORM_TIMING["instagram"])
    prob = timing.get(key, 0.0)
    return random.random() < prob


def human_delay(base: float = 1.5) -> float:
    """Exponential distribution delay (Poisson-like)."""
    delay = random.expovariate(1 / base)
    return max(0.3, min(8.0, delay))


def thinking_pause() -> float:
    """Occasional long pause: human got distracted."""
    if random.random() < 0.12:
        return random.uniform(12, 30)
    elif random.random() < 0.25:
        return random.uniform(5, 12)
    return random.uniform(1, 4)
