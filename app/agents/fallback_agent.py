import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from services.fallback_service import get_curated_fallback
from utils.activity_schema import normalize_activity, parse_llm_json

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_TYPES = ("Indoor", "Outdoor", "Relax")
VALID_TIMES = ("morning", "afternoon", "evening")


def _is_well_formed(activity: dict) -> bool:
    """Defensive check run on whatever normalize_activity() returns,
    since we don't control / can't fully verify its internals here.
    Catches the exact failure mode seen in production: type coming
    back as the literal enum hint string "Indoor | Outdoor | Relax"
    instead of a single resolved value, and blank/missing fields.
    """
    if not isinstance(activity, dict):
        return False

    name = str(activity.get("name", "")).strip()
    activity_type = str(activity.get("type", "")).strip()
    time_of_day = str(activity.get("time_of_day", "")).strip().lower()
    location = str(activity.get("location", "")).strip()

    if not name or not activity_type or not time_of_day or not location:
        return False

    if activity_type not in VALID_TYPES:
        return False

    if time_of_day not in VALID_TIMES:
        return False

    return True


def generate_fallback(activity, profile, weather, city=None):
    city_name = city or weather.get("city", "Unknown")

    # NOTE: previously the OUTPUT block showed "type": "Indoor | Outdoor | Relax"
    # as a literal example value, and the model sometimes echoed it verbatim
    # (confirmed in production: a card rendered with
    # "Type: Indoor | Outdoor | Relax"). Fixed the same way as activity_agent.py
    # — one concrete example per field instead of a pipe-separated enum hint.
    prompt = f"""
You are a fallback system for rejected travel activities.

Convert the REJECTED activity into a SAFE, SPECIFIC alternative in {city_name}.

RULES:
- Keep the user's intent from likes: {profile.get("likes", [])}
- Respect dislikes as HARD constraints: {profile.get("dislikes", [])}
- Respect weather: {json.dumps(weather, indent=2)}
- Avoid hot outdoor exposure if temperature >= 28°C and user dislikes heat
- Name a real neighborhood AND a specific venue, route, or landmark
- The "location" field MUST always be filled in — never leave it blank
- Do NOT repeat the rejected activity
- NEVER output generic phrases like "visit a museum" or "explore the city"
- "type" MUST be exactly ONE of these words: Indoor, Outdoor, Relax. Never combine options, never use "or", never use "|".
- "time_of_day" MUST be exactly ONE of these words: morning, afternoon, evening. Never combine options.

REJECTED ACTIVITY:
{json.dumps(activity, indent=2)}

OUTPUT (JSON ONLY). Values below are illustrative — replace with your own
real, specific content, but keep "type" and "time_of_day" as single words
chosen from the allowed lists above:
{{
  "name": "specific neighborhood-based alternative",
  "type": "Indoor",
  "location": "neighborhood or landmark",
  "time_of_day": "morning",
  "why": "why this fits user preferences and weather",
  "score": 6
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content or "{}"
    parsed = parse_llm_json(raw)

    if isinstance(parsed, dict):
        normalized = normalize_activity(parsed, city=city_name)
        # FIX: don't just check truthiness — verify the normalized result
        # actually has clean enum values and non-empty required fields
        # before trusting it. This is what was missing: normalize_activity
        # was letting "Indoor | Outdoor | Relax" pass through as a "type".
        if _is_well_formed(normalized):
            normalized["source"] = "llm_fallback"
            return normalized

    curated = get_curated_fallback(city_name, profile, weather)
    if curated and _is_well_formed(curated[0]):
        return curated[0]

    return {
        "name": f"Morning coffee at a neighborhood café in {city_name}, then a short shaded walk",
        "type": "Relax",
        "location": city_name,
        "time_of_day": "morning",
        "why": "Indoor start with limited outdoor exposure fits weather and safety constraints.",
        "score": 6,
        "source": "static_fallback",
    }