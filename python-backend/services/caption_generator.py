"""Caption generator — tone-based captions with hashtag bank."""
from __future__ import annotations

import random

TONES = ["playful", "flirty", "neutral", "professional", "motivational", "funny", "aesthetic"]

SEED_CAPTIONS: dict[str, list[str]] = {
    "playful": [
        "Oops, did I just become your favorite follower?",
        "You know you want to double-tap this",
        "Plot twist: I woke up like this",
        "Not your average scroll-stopper",
        "Warning: may cause double-taps",
        "Living my best life one post at a time",
        "Just posted, no big deal",
        "Swipe right if you agree",
        "Catch flights, not feelings",
        "Too glam to give a damn",
        "Main character energy only",
        "This is your sign to double-tap",
        "POV: you found the best page",
        "Vibes don't lie",
        "Alexa, play my theme song",
        "The algorithm brought you here for a reason",
        "You're welcome for the content",
        "Professional vibe curator",
        "Just out here being iconic",
        "Your daily dose of awesome",
    ],
    "flirty": [
        "Save this for later... you know you want to",
        "Took me 20 tries to get this right, worth it?",
        "Catch me if you can",
        "This one's for the bookmarkers",
        "Slide into my DMs, I dare you",
        "If looks could kill, this post would be a weapon",
        "Heart eyes only please",
        "I know you screenshot this one",
        "Looking like a whole snack",
        "Eyes up here... or not",
        "Don't just stare, double tap",
        "Felt cute, probably won't delete",
        "Who needs a filter when you look this good",
        "Making hearts skip a beat",
        "Your timeline just got an upgrade",
        "Follow for more content you can't resist",
        "Go ahead, take a closer look",
        "The one your feed was missing",
        "Leaving a trail of double-taps",
        "Made you look",
    ],
    "neutral": [
        "Beautiful day in the neighborhood",
        "Just another Tuesday",
        "Good vibes only",
        "Life update: still here",
        "Making memories",
        "New day, new content",
        "Another one for the feed",
        "Appreciate the little things",
        "Stay positive, work hard",
        "Just living",
        "Moments like these",
        "Simple pleasures",
        "One step at a time",
        "Going with the flow",
        "Here and now",
        "Everyday adventures",
        "Keeping it real",
        "No filter needed",
        "Capturing the moment",
        "Today was a good day",
        "Less talk, more action",
        "Enjoying the process",
        "Grateful for today",
        "Weekend state of mind",
        "Good morning, world",
    ],
    "professional": [
        "New project drop. Link in bio.",
        "Behind the scenes at the studio",
        "Fresh work, fresh energy",
        "Creating things that matter",
        "Passion meets purpose",
        "Building something special",
        "Work hard, post harder",
        "From concept to creation",
        "The grind never stops",
        "Making moves in silence",
        "Quality over quantity, always",
        "Latest project just dropped",
        "Crafted with care",
        "Details make the difference",
        "Proud of this one",
        "Another milestone unlocked",
        "Stay hungry, stay focused",
        "The process is the product",
        "Excellence is a habit",
        "Putting in the work",
    ],
    "motivational": [
        "Your only limit is you",
        "Dream it. Do it. Done.",
        "Rise and grind",
        "Success is a journey, not a destination",
        "Be the energy you want to attract",
        "Small steps, big results",
        "Progress, not perfection",
        "You didn't come this far to only come this far",
        "Believe in the process",
        "Make today count",
        "The comeback is always stronger than the setback",
        "Discipline equals freedom",
        "Hustle in silence, let success make the noise",
        "Every day is a new chance",
        "Stay focused, stay blessed",
        "Hard work pays off",
        "You are your own competition",
        "The best time to start is now",
        "Turn your cant's into cans",
        "Greatness takes time",
    ],
    "funny": [
        "My photographer is still accepting payments",
        "Do it for the gram, stay for the likes",
        "Professional overthinker",
        "Currently accepting compliments",
        "I came, I saw, I posted",
        "Reality called, I hung up",
        "My bed is a magical place where I remember everything I forgot to do",
        "Life is short, smile while you still have teeth",
        "I need a six month vacation, twice a year",
        "Running on caffeine and dreams",
        "Adulting is overrated",
        "My hobbies include scrolling and eating",
        "I'm not lazy, I'm on energy saving mode",
        "Sorry I'm late, I didn't want to come",
        "I followed my heart and it led me to the fridge",
        "Out of my mind, back in five minutes",
        "I put the 'pro' in procrastinate",
        "Life's too short for boring content",
        "Just here for the WiFi",
        "That's enough adulting for one day",
    ],
    "aesthetic": [
        "Golden hour hits different",
        "Chasing light and shadows",
        "Muted tones, loud vibes",
        "Somewhere between chaos and calm",
        "Soft mornings and warm light",
        "Details in the silence",
        "Whispers of color",
        "Stillness speaks volumes",
        "Fading into the golden",
        "Light leaks and daydreams",
        "The art of being still",
        "Tones and textures",
        "Delicate chaos",
        "Poetry in pixels",
        "Earth tones and easy mornings",
        "Minimal effort, maximum aesthetic",
        "Quiet luxury vibes",
        "Less is always more",
        "Mood: undefined but beautiful",
        "Curated by accident",
    ],
}

HASHTAG_BANK: dict[str, list[str]] = {
    "general": [
        "#vibes", "#mood", "#aesthetic", "#instagood", "#photooftheday",
        "#instadaily", "#lifestyle", "#explore", "#trending", "#fyp",
        "#content", "#love", "#beautiful", "#happy", "#style",
    ],
    "fitness": ["#fitness", "#gym", "#workout", "#motivation", "#fitfam", "#health", "#training"],
    "travel": ["#travel", "#wanderlust", "#adventure", "#explore", "#vacation", "#travelphotography"],
    "food": ["#food", "#foodie", "#yummy", "#cooking", "#delicious", "#homemade", "#recipe"],
    "fashion": ["#fashion", "#style", "#ootd", "#outfit", "#streetstyle", "#fashionista"],
    "nature": ["#nature", "#landscape", "#sunset", "#outdoors", "#photography", "#earth"],
    "art": ["#art", "#creative", "#design", "#artwork", "#illustration", "#sketch"],
}


async def generate_caption(
    tone: str = "neutral",
    include_hashtags: bool = True,
    hashtag_count: int = 5,
) -> dict:
    captions = SEED_CAPTIONS.get(tone, SEED_CAPTIONS["neutral"])
    caption = random.choice(captions)

    hashtags: list[str] = []
    if include_hashtags:
        all_tags = HASHTAG_BANK["general"].copy()
        category = random.choice(list(HASHTAG_BANK.keys()))
        all_tags.extend(HASHTAG_BANK[category])
        hashtags = random.sample(all_tags, min(hashtag_count, len(all_tags)))

    full_text = caption
    if hashtags:
        full_text += "\n\n" + " ".join(hashtags)

    return {
        "caption": caption,
        "hashtags": hashtags,
        "full_text": full_text,
        "tone": tone,
    }


async def get_random_captions(tone: str = "neutral", count: int = 5) -> list[dict]:
    captions = SEED_CAPTIONS.get(tone, SEED_CAPTIONS["neutral"])
    selected = random.sample(captions, min(count, len(captions)))
    return [{"text": c, "tone": tone} for c in selected]
