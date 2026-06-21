import json
import re

VALID_TYPES = {"Indoor", "Outdoor", "Relax"}
VALID_TIMES = {"morning", "afternoon", "evening"}

DISLIKE_ALIASES = {
    "crowd": ("crowd", "crowded", "busy", "tourist"),
    "hot": ("hot weather", "heat", "hot", "sun exposure", "sun"),
    "nightlife": ("nightlife", "bars", "clubs", "party"),
    "hiking": ("hiking", "hike", "trek", "trekking"),
    "rain": ("rain", "wet weather"),
}

TIME_HINTS = {
    "morning": ("morning", "sunrise", "breakfast", "early", "dawn"),
    "afternoon": ("afternoon", "lunch", "midday"),
    "evening": ("evening", "sunset", "night", "after dark", "golden hour", "dinner"),
}


def parse_llm_json(raw: str) -> dict | list | None:
    if not raw:
        return None

    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if isinstance(raw, str):
            match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    return None
    return None


def _normalize_type(value: str) -> str | None:
    if not value:
        return None
    cleaned = value.strip().title()
    if cleaned.lower() == "outdoor":
        return "Outdoor"
    if cleaned.lower() == "indoor":
        return "Indoor"
    if cleaned.lower() == "relax":
        return "Relax"
    return cleaned if cleaned in VALID_TYPES else None


def infer_time_of_day(activity: dict) -> str | None:
    explicit = (activity.get("time_of_day") or "").strip().lower()
    if explicit in VALID_TIMES:
        return explicit

    text = " ".join(
        [
            activity.get("name", ""),
            activity.get("location", ""),
            " ".join(activity.get("tags", [])),
        ]
    ).lower()

    for slot, hints in TIME_HINTS.items():
        if any(hint in text for hint in hints):
            return slot
    return None


def _extract_location(name: str, city: str = "") -> str:
    if not name:
        return city or "City center"
    if " in " in name.lower():
        tail = re.split(r"\s+in\s+", name, flags=re.IGNORECASE)[-1]
        return tail.split(",")[0].strip()
    if " at " in name.lower():
        tail = re.split(r"\s+at\s+", name, flags=re.IGNORECASE)[-1]
        return tail.split(",")[0].strip()
    return city or "City center"


def normalize_activity(activity: dict, city: str = "") -> dict | None:
    if not isinstance(activity, dict):
        return None

    name = (
        activity.get("name")
        or activity.get("title")
        or activity.get("activity")
        or ""
    ).strip()

    activity_type = _normalize_type(activity.get("type", ""))
    if not name or not activity_type:
        return None

    time_of_day = infer_time_of_day(activity)
    if not time_of_day:
        return None

    location = (activity.get("location") or "").strip() or _extract_location(name, city)
    why = (activity.get("why") or activity.get("reasoning") or "").strip()

    score = activity.get("score", activity.get("final_score", 7))
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 7
    score = max(1, min(10, score))

    normalized = {
        "name": name,
        "type": activity_type,
        "location": location,
        "time_of_day": time_of_day,
        "why": why,
        "score": score,
    }

    if activity.get("tags"):
        normalized["tags"] = activity["tags"]
    if activity.get("avoid_tags"):
        normalized["avoid_tags"] = activity["avoid_tags"]
    if activity.get("source"):
        normalized["source"] = activity["source"]

    return normalized


def normalize_activities(activities: list, city: str = "") -> list:
    normalized = []
    for activity in activities or []:
        item = normalize_activity(activity, city=city)
        if item:
            normalized.append(item)
    return normalized


def _dislike_categories(dislikes: list) -> set[str]:
    categories = set()
    blob = " ".join(dislikes or []).lower()
    for category, aliases in DISLIKE_ALIASES.items():
        if any(alias in blob for alias in aliases):
            categories.add(category)
    return categories


def _activity_text(activity: dict) -> str:
    return " ".join(
        [
            activity.get("name", ""),
            activity.get("location", ""),
            activity.get("type", ""),
            " ".join(activity.get("tags", [])),
            " ".join(activity.get("avoid_tags", [])),
        ]
    ).lower()


def violates_hard_constraints(activity: dict, profile: dict, weather: dict) -> tuple[bool, str]:
    dislikes = profile.get("dislikes", [])
    categories = _dislike_categories(dislikes)
    text = _activity_text(activity)
    activity_type = activity.get("type", "")
    temp = weather.get("temperature")
    condition = (weather.get("condition") or weather.get("weather") or "").lower()
    time_of_day = activity.get("time_of_day", "")

    if "crowd" in categories:
        crowd_markers = ("istiklal", "grand bazaar", "times square", "peak hour", "tour group")
        if any(marker in text for marker in crowd_markers):
            if time_of_day == "afternoon":
                return True, "Conflicts with crowd avoidance at peak hours."

    if "hot" in categories and temp is not None and temp >= 28:
        if activity_type == "Outdoor" and time_of_day == "afternoon":
            sheltered = any(
                word in text
                for word in ("shaded", "sunset", "evening", "morning", "early", "covered")
            )
            if not sheltered:
                return True, "Midday outdoor exposure conflicts with heat dislike."

    if "nightlife" in categories:
        if any(word in text for word in ("bar", "club", "nightlife", "after dark", "pub crawl")):
            return True, "Conflicts with nightlife dislike."

    if "hiking" in categories:
        if any(word in text for word in ("hike", "hiking", "trek", "trail")):
            return True, "Conflicts with hiking dislike."

    if "rain" in categories and any(w in condition for w in ("rain", "drizzle", "storm", "shower")):
        if activity_type == "Outdoor" and "covered" not in text and "indoor" not in text:
            return True, "Outdoor plan is risky in rainy conditions with rain dislike."

    for dislike in dislikes:
        token = dislike.strip().lower()
        if len(token) >= 4 and token in text:
            return True, f"Activity mentions excluded preference: {dislike}."

    return False, ""
