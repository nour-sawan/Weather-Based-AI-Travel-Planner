import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from services.fallback_service import get_curated_fallback
from utils.activity_quality import assess_batch_quality, is_generic_activity
from utils.activity_schema import normalize_activities, parse_llm_json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_TYPES = ("Indoor", "Outdoor", "Relax")
VALID_TIMES = ("morning", "afternoon", "evening")


def _build_weather_context(weather_data: dict) -> str:
    if weather_data.get("error"):
        return str(weather_data)

    return (
        f"City: {weather_data.get('city', 'Unknown')}\n"
        f"Temperature: {weather_data.get('temperature')}°C "
        f"(feels like {weather_data.get('feels_like', weather_data.get('temperature'))}°C)\n"
        f"Condition: {weather_data.get('condition', 'unknown')} "
        f"({weather_data.get('weather', 'N/A')})\n"
        f"Humidity: {weather_data.get('humidity')}%\n"
        f"Wind: {weather_data.get('wind_speed')} km/h\n"
        f"Weather guidance: {weather_data.get('guidance', '')}"
    )


def _build_prompt(city: str, weather_data: dict, profile: dict | None, strict: bool = False) -> str:
    likes = profile.get("likes", []) if profile else []
    dislikes = profile.get("dislikes", []) if profile else []
    weather_context = _build_weather_context(weather_data)

    strict_block = ""
    if strict:
        strict_block = """
STRICT RETRY MODE:
- Your previous answer was too generic or low quality.
- Every name MUST include a real neighborhood AND a named venue, route, or landmark.
- time_of_day is REQUIRED for every item (morning, afternoon, or evening only).
- If weather is hot or rainy, do NOT suggest long exposed outdoor walks at midday.
- Reject your own generic phrasing. No one-line vague ideas.
- "location" must be filled in for every item — never leave it blank.
"""

    return f"""
You are a hyper-specific local travel planner for {city}.

{weather_context}

USER PREFERENCES:
Likes: {likes}
Dislikes: {dislikes}

TASK:
Generate exactly 10 personalized activities for {city} today.

CRITICAL RULES:
- Each activity MUST name a real neighborhood AND a specific place, venue, route, or landmark.
- The "location" field MUST always be filled in with a real neighborhood or landmark name — never leave it blank.
- Match weather directly: heat → shade/indoor/evening; rain → covered/indoor plans.
- Treat dislikes as HARD CONSTRAINTS (crowds, heat, nightlife, hiking, etc.).
- Lean into likes with real venues (restaurants, cafés, museums, coastal routes).
- If an activity naturally has two parts (e.g. a museum visit followed by a walk), pick the type of whichever part is the MAIN focus. Do not combine types.
- "type" MUST be exactly one of these three words: Indoor, Outdoor, Relax. Pick ONE. Never write more than one word, never use the word "or", never separate options with "|".
- "time_of_day" MUST be exactly one of these three words: morning, afternoon, evening. Pick ONE. Never write "any time" or combine multiple values. ALWAYS include this field — it is never optional.
- If user likes beaches, include seaside spots but only morning/evening when hot.
- If user dislikes crowds, avoid tourist-heavy areas at peak hours.

GOOD EXAMPLES:
- "Walk from Karaköy to Galata Tower at sunset along the Bosphorus waterfront"
- "Coffee at Mandabatmaz in Beyoğlu, then stroll İstiklal Street after dark"
- "Morning visit to Süleymaniye Mosque terrace overlooking the Golden Horn"

BAD EXAMPLES (NEVER OUTPUT):
- "Go for a walk"
- "Visit a museum"
- "Explore the city"
- "Try local food"

{strict_block}

OUTPUT FORMAT:
Return ONLY a valid JSON array. Each item must look exactly like this shape
(values below are illustrative — replace with your own real, specific content):

[
  {{
    "name": "Coffee at Mandabatmaz in Beyoğlu, then stroll İstiklal Street after dark",
    "type": "Outdoor",
    "location": "Beyoğlu, İstiklal Street",
    "time_of_day": "evening",
    "why": "short reasoning based on preferences + weather",
    "score": 8
  }}
]
"""


def _call_llm(city: str, weather_data: dict, profile: dict | None, strict: bool = False) -> list:
    prompt = _build_prompt(city, weather_data, profile, strict=strict)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.15 if strict else 0.35,
    )

    raw = response.choices[0].message.content or ""
    parsed = parse_llm_json(raw)
    if not isinstance(parsed, list):
        return []
    return normalize_activities(parsed, city=city)


def generate_activities(weather_data, city, profile=None):
    if weather_data.get("error"):
        curated = get_curated_fallback(city, profile, weather_data)
        if not curated:
            return []
        return filter_activities(curated, profile=profile, weather_data=weather_data)

    activities = _call_llm(city, weather_data, profile, strict=False)
    quality = assess_batch_quality(activities)

    if not quality["ok"]:
        activities = _call_llm(city, weather_data, profile, strict=True)
        quality = assess_batch_quality(activities)

    if not quality["ok"]:
        activities = get_curated_fallback(city, profile, weather_data)

    if not activities:
        return []

    return filter_activities(activities, profile=profile, weather_data=weather_data)


_DISLIKE_KEYWORD_HINTS = {
    "crowds": ["crowded", "busy market", "bazaar", "tourist-packed", "peak hour"],
    "crowd": ["crowded", "busy market", "bazaar", "tourist-packed", "peak hour"],
    "nightlife": ["nightclub", "club", "bar crawl", "late-night party"],
    "hiking": ["hike", "hiking", "trek", "trail climb"],
    "heat": ["midday sun", "exposed walk", "long walk in the sun"],
}

_HOT_THRESHOLD_C = 32


def _violates_dislikes(activity: dict, dislikes: list[str]) -> bool:
    if not dislikes:
        return False

    haystack = " ".join(
        str(activity.get(field, "")) for field in ("name", "why", "location")
    ).lower()

    for dislike in dislikes:
        key = dislike.strip().lower()
        if not key:
            continue
        if key in haystack:
            return True
        for hint in _DISLIKE_KEYWORD_HINTS.get(key, []):
            if hint in haystack:
                return True

    return False


def _violates_weather(activity: dict, weather_data: dict) -> bool:
    if not weather_data or weather_data.get("error"):
        return False

    temp = weather_data.get("temperature")
    condition = str(weather_data.get("condition", "")).lower()
    is_hot = isinstance(temp, (int, float)) and temp >= _HOT_THRESHOLD_C
    is_rainy = "rain" in condition or "storm" in condition

    if not (is_hot or is_rainy):
        return False

    activity_type = str(activity.get("type", "")).lower()
    time_of_day = str(activity.get("time_of_day", "")).lower()

    return activity_type == "outdoor" and time_of_day == "afternoon"


# Words too common/short to be useful as a "venue fingerprint" when checking
# for duplicates — skipping these avoids false-positive merges (e.g. two
# unrelated activities both containing the word "the" or "park").
_DEDUPE_STOPWORDS = {
    "the", "a", "an", "of", "in", "at", "and", "to", "for", "with", "on",
    "visit", "explore", "walk", "stroll", "morning", "afternoon", "evening",
}


def _venue_fingerprint(name: str) -> str:
    """Extract a normalized 'core venue' signature from an activity name,
    so that 'Visit the Palau de la Música Catalana' and 'Palau de la
    Música Catalana in El Born' are recognized as the same place despite
    different surrounding wording.
    """
    words = re.findall(r"[a-zA-ZÀ-ÿ']+", name.lower())
    significant = [w for w in words if w not in _DEDUPE_STOPWORDS and len(w) > 2]
    return " ".join(significant)


def _is_duplicate_venue(fingerprint: str, seen_fingerprints: list[str]) -> bool:
    if not fingerprint:
        return False
    for seen in seen_fingerprints:
        # Loose match: if a meaningful chunk of one fingerprint appears
        # inside the other, treat them as the same venue. Catches cases
        # like "Palau de la Música Catalana" appearing in 3 differently
        # worded activity names.
        if fingerprint in seen or seen in fingerprint:
            return True
    return False


def filter_activities(activities, profile: dict | None = None, weather_data: dict | None = None):
    dislikes = profile.get("dislikes", []) if profile else []
    filtered = []
    seen_fingerprints: list[str] = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        name = activity.get("name", "")
        activity_type = str(activity.get("type", "")).strip()
        time_of_day = str(activity.get("time_of_day", "")).strip().lower()
        location = str(activity.get("location", "")).strip()

        if not name or not activity_type or not time_of_day or not location:
            continue

        type_match = next(
            (t for t in VALID_TYPES if t.lower() == activity_type.lower()), None
        )
        if not type_match:
            continue
        activity["type"] = type_match

        if time_of_day not in VALID_TIMES:
            continue
        activity["time_of_day"] = time_of_day

        if activity.get("score", 0) < 4:
            continue

        if is_generic_activity(name):
            continue

        lowered = name.lower()
        if "unknown" in lowered or "random" in lowered:
            continue

        if _violates_dislikes(activity, dislikes):
            continue

        if _violates_weather(activity, weather_data or {}):
            continue

        # FIX: de-duplicate near-identical venues. Production output
        # showed "Palau de la Música Catalana" recommended 3 separate
        # times with slightly different wording/location text, which
        # wasted slots in the final top-10 list on repeats instead of
        # genuinely distinct experiences. Keep the first (highest-ranked,
        # since input is processed in the order the LLM/curated source
        # returned it) occurrence of each venue.
        fingerprint = _venue_fingerprint(name)
        if _is_duplicate_venue(fingerprint, seen_fingerprints):
            continue
        seen_fingerprints.append(fingerprint)

        filtered.append(activity)

    return filtered