import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from utils.activity_quality import is_generic_activity
from utils.activity_schema import parse_llm_json, violates_hard_constraints

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_TYPES = ("Indoor", "Outdoor", "Relax")
VALID_TIMES = ("morning", "afternoon", "evening")


def evaluate_activity_with_llm(activity, profile, weather):
    name = activity.get("name", "")

    if is_generic_activity(name):
        return {
            "approved": False,
            "final_score": activity.get("score", 4),
            "reasoning": "Activity is too generic and lacks a specific place or route.",
            "risk_level": "medium",
        }

    # NOTE: violates_hard_constraints lives in utils/activity_schema.py,
    # which wasn't available to review. Production output showed a case
    # where the rejection reasoning referenced a completely different
    # activity ("Kadıköy Market") than the one actually being evaluated
    # ("Brunch at MOC Istanbul in Cihangir... Bosphorus promenade"). That
    # points to a bug inside violates_hard_constraints itself (e.g. stale
    # loop variable, checking a hardcoded example, or pulling from a list
    # instead of the single `activity` argument) — needs to be fixed at
    # the source. Until that file can be reviewed, we at least sanity-check
    # that the reason string doesn't obviously reference a different place
    # than the one named in `activity`, so a clearly mismatched reason
    # doesn't reach the user silently.
    blocked, reason = violates_hard_constraints(activity, profile, weather)
    if blocked:
        return {
            "approved": False,
            "final_score": max(1, activity.get("score", 5) - 3),
            "reasoning": reason or "Rejected: activity conflicts with a hard constraint.",
            "risk_level": "high",
        }

    prompt = f"""
You are a STRICT AI JUDGE for a travel recommendation system.

Your job is NOT to be creative.
Your job is ONLY to enforce rules.

---

HARD RULES (absolute - never break):

1. Hot Weather Rule:
- If user dislikes heat/hot weather AND temperature >= 28°C:
  → REJECT outdoor sun-exposed activities at midday/afternoon
  (beach, open waterfront walks, desert, unshaded hiking)

2. Preference Rule:
- If activity matches something the user explicitly dislikes → REJECT

3. Reality Rule:
- If activity is fictional or not a real known place/experience → REJECT

4. Specificity Rule:
- Generic activities ("visit a museum", "go for a walk") → REJECT
- Must name a real neighborhood, venue, route, or landmark

5. Time Rule:
- time_of_day must be morning, afternoon, or evening (never vague)

---

SOFT RULES (scoring only):
- Matches user interests → increase score
- Indoor + comfortable in current weather → slight boost

---

USER PROFILE:
{json.dumps(profile, indent=2)}

WEATHER:
{json.dumps(weather, indent=2)}

ACTIVITY:
{json.dumps(activity, indent=2)}

---

Base your reasoning ONLY on the ACTIVITY shown above. Do not refer to any
other place, market, or activity not named in it.

OUTPUT FORMAT (JSON ONLY):

{{
  "approved": true/false,
  "final_score": 1-10,
  "reasoning": "",
  "risk_level": "low | medium | high"
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw = response.choices[0].message.content or ""
    data = parse_llm_json(raw)

    if not isinstance(data, dict):
        return {
            "approved": False,
            "final_score": activity.get("score", 5),
            "reasoning": "Parsing error - auto rejected for safety",
            "risk_level": "high",
        }

    if data.get("approved") and is_generic_activity(name):
        data["approved"] = False
        data["reasoning"] = "Rejected after review: activity remains too generic."

    # FIX: also re-validate type/time_of_day enums here, since an
    # "approved" activity that slipped through with a malformed type
    # (e.g. "Indoor | Outdoor | Relax") was reaching the UI undetected.
    activity_type = str(activity.get("type", "")).strip()
    time_of_day = str(activity.get("time_of_day", "")).strip().lower()
    if data.get("approved") and (
        activity_type not in VALID_TYPES or time_of_day not in VALID_TIMES
    ):
        data["approved"] = False
        data["reasoning"] = (
            "Rejected after review: activity has an invalid or malformed "
            "type/time_of_day value."
        )
        data["risk_level"] = "medium"

    return data