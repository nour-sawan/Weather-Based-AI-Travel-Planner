import json
import os
import re

from utils.activity_schema import infer_time_of_day, normalize_activity

FALLBACK_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "city_fallbacks.json")

RAIN_KEYWORDS = ("rain", "drizzle", "storm", "thunder", "shower")
HOT_KEYWORDS = ("hot weather", "heat", "sun exposure", "hot")
CROWD_KEYWORDS = ("crowd", "crowded", "busy", "tourist")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).strip()


def _load_fallback_data() -> dict:
    with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _city_key(city: str) -> str:
    return _normalize(city).replace(" ", "")


def _matches_preference(text: str, items: list) -> bool:
    normalized = _normalize(text)
    for item in items:
        token = _normalize(item)
        if token and token in normalized:
            return True
    return False


def _build_why(activity: dict, profile: dict, weather: dict) -> str:
    likes = ", ".join(profile.get("likes", [])) or "your interests"
    condition = weather.get("condition", weather.get("weather", "current conditions"))
    temp = weather.get("temperature", "N/A")
    return (
        f"Matches {likes} while fitting {condition} weather "
        f"({temp}°C) with a specific local route or venue."
    )


def _enrich_activity(activity: dict, city: str, profile: dict, weather: dict) -> dict | None:
    copy = dict(activity)
    copy.setdefault("location", city)
    copy.setdefault("why", _build_why(copy, profile, weather))
    if not copy.get("time_of_day"):
        copy["time_of_day"] = infer_time_of_day(copy)
    return normalize_activity(copy, city=city)


def _score_activity(activity: dict, profile: dict, weather: dict) -> int:
    score = activity.get("score", 7)
    likes = profile.get("likes", [])
    dislikes = profile.get("dislikes", [])
    name = activity.get("name", "")
    tags = activity.get("tags", [])
    avoid_tags = activity.get("avoid_tags", [])
    activity_type = activity.get("type", "")

    tag_text = " ".join(tags + avoid_tags + [name])

    for like in likes:
        like_norm = _normalize(like)
        if like_norm and (
            like_norm in _normalize(name)
            or any(like_norm in _normalize(tag) for tag in tags)
        ):
            score += 1

    for dislike in dislikes:
        dislike_norm = _normalize(dislike)
        if dislike_norm and (
            dislike_norm in _normalize(name)
            or any(dislike_norm in _normalize(tag) for tag in avoid_tags + tags)
        ):
            score -= 3

    temp = weather.get("temperature")
    condition = _normalize(weather.get("condition", weather.get("weather", "")))

    if temp is not None and temp >= 28:
        if activity_type == "Outdoor" and activity.get("time_of_day") == "afternoon":
            if "shaded" not in _normalize(name):
                score -= 2
        if _matches_preference(tag_text, HOT_KEYWORDS):
            score -= 2

    if any(word in condition for word in RAIN_KEYWORDS):
        if activity_type == "Outdoor" and "rainy" not in tags:
            score -= 2
        if activity_type == "Indoor" or "rainy" in tags:
            score += 1

    if _matches_preference(" ".join(dislikes), CROWD_KEYWORDS):
        if _matches_preference(tag_text, CROWD_KEYWORDS):
            score -= 2

    return max(1, min(10, score))


def _is_weather_compatible(activity: dict, profile: dict, weather: dict) -> bool:
    temp = weather.get("temperature")
    condition = _normalize(weather.get("condition", weather.get("weather", "")))
    activity_type = activity.get("type", "")
    dislikes = profile.get("dislikes", [])
    name = activity.get("name", "")
    time_of_day = activity.get("time_of_day", "")

    if temp is not None and temp >= 28:
        if _matches_preference(" ".join(dislikes), HOT_KEYWORDS):
            if activity_type == "Outdoor" and time_of_day == "afternoon":
                if not any(k in _normalize(name) for k in ("shaded", "covered", "indoor")):
                    return False

    if any(word in condition for word in RAIN_KEYWORDS):
        if activity_type == "Outdoor" and "rainy" not in activity.get("tags", []):
            if not any(
                k in _normalize(name)
                for k in ("market", "covered", "canal", "waterfront", "morning", "evening")
            ):
                return False

    return True


def get_curated_fallback(city: str, profile: dict | None, weather: dict) -> list:
    profile = profile or {"likes": [], "dislikes": []}
    data = _load_fallback_data()
    city_activities = data.get(_city_key(city), [])

    if not city_activities:
        return []

    ranked = []
    for activity in city_activities:
        enriched = _enrich_activity(activity, city, profile, weather)
        if not enriched:
            continue
        if not _is_weather_compatible(enriched, profile, weather):
            continue

        enriched["score"] = _score_activity(enriched, profile, weather)
        enriched["source"] = "curated_fallback"
        ranked.append(enriched)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:10]
