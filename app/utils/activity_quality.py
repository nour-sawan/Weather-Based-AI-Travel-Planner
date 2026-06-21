import re

GENERIC_PATTERNS = [
    r"\bgo for a walk\b",
    r"\btake a walk\b",
    r"\bvisit a museum\b",
    r"\bvisit the museum\b",
    r"\bvisit museum\b",
    r"\bexplore the city\b",
    r"\bexplore the area\b",
    r"\bexplore city\b",
    r"\bwalk around\b",
    r"\bwalk in the city\b",
    r"\bwalk in city\b",
    r"\bhave fun\b",
    r"\blocal café\b",
    r"\blocal cafe\b",
    r"\bunknown activity\b",
    r"\brandom\b",
    r"\bsee the sights\b",
    r"\bsightseeing\b",
    r"\bdiscover the city\b",
    r"\bcheck out the city\b",
    r"\bvisit attractions\b",
    r"\bvisit local\b",
    r"\btry local food\b",
    r"\benjoy the city\b",
    r"\bspend time outdoors\b",
    r"\bspend time in the city\b",
]

MIN_NAME_LENGTH = 18
MIN_SPECIFIC_WORDS = 2
VALID_TIMES = {"morning", "afternoon", "evening"}


def is_generic_activity(name: str) -> bool:
    if not name or not isinstance(name, str):
        return True

    normalized = " ".join(name.lower().split())

    if len(normalized) < MIN_NAME_LENGTH:
        return True

    for pattern in GENERIC_PATTERNS:
        if re.search(pattern, normalized):
            return True

    words = re.findall(r"[a-zA-ZÀ-ÿ']+", normalized)
    if len(words) < MIN_SPECIFIC_WORDS:
        return True

    return False


def assess_batch_quality(activities: list) -> dict:
    if not activities:
        return {
            "ok": False,
            "reason": "empty",
            "generic_ratio": 1.0,
            "valid_count": 0,
        }

    valid = []
    generic_count = 0

    for activity in activities:
        if not isinstance(activity, dict):
            continue

        name = activity.get("name", "")
        activity_type = activity.get("type", "")
        time_of_day = (activity.get("time_of_day") or "").lower()

        if not name or not activity_type or time_of_day not in VALID_TIMES:
            continue

        valid.append(activity)
        if is_generic_activity(name):
            generic_count += 1

    if len(valid) < 5:
        return {
            "ok": False,
            "reason": "too_few",
            "generic_ratio": generic_count / max(len(valid), 1),
            "valid_count": len(valid),
        }

    generic_ratio = generic_count / len(valid)
    if generic_ratio > 0.3:
        return {
            "ok": False,
            "reason": "too_generic",
            "generic_ratio": generic_ratio,
            "valid_count": len(valid),
        }

    return {
        "ok": True,
        "reason": "ok",
        "generic_ratio": generic_ratio,
        "valid_count": len(valid),
    }
