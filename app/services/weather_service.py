import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

RAIN_KEYWORDS = ("rain", "drizzle", "storm", "thunder", "shower")
SNOW_KEYWORDS = ("snow", "sleet", "blizzard")
CLOUD_KEYWORDS = ("cloud", "overcast", "mist", "fog", "haze")


def _normalize_condition(description: str) -> str:
    text = (description or "").lower()

    if any(word in text for word in RAIN_KEYWORDS):
        return "rainy"
    if any(word in text for word in SNOW_KEYWORDS):
        return "snowy"
    if "clear" in text or "sun" in text:
        return "sunny"
    if any(word in text for word in CLOUD_KEYWORDS):
        return "cloudy"

    return text or "unknown"


def _weather_guidance(temp: float, condition: str) -> str:
    guidance = []

    if temp >= 32:
        guidance.append("Very hot: prioritize shaded routes, indoor venues, and evening plans.")
    elif temp >= 28:
        guidance.append("Hot: avoid long midday outdoor walks; prefer morning/evening outdoor time.")
    elif temp <= 5:
        guidance.append("Cold: favor heated indoor venues and shorter outdoor segments.")
    elif 15 <= temp <= 24:
        guidance.append("Comfortable: good window for neighborhood walks and mixed indoor/outdoor plans.")

    if condition == "rainy":
        guidance.append("Rain expected: prefer covered markets, museums, cafés, and indoor experiences.")
    elif condition == "snowy":
        guidance.append("Snow expected: keep outdoor exposure short and choose warm indoor backups.")
    elif condition == "sunny" and temp >= 24:
        guidance.append("Bright sun: schedule open-air walks early or late in the day.")

    return " ".join(guidance)


def get_weather(city: str, country_code: str | None = None):
    if not API_KEY:
        return {"error": "Missing OPENWEATHER_API_KEY in environment."}

    query = f"{city},{country_code}" if country_code else city
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={query}&appid={API_KEY}&units=metric"
    )

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return {"error": "Could not reach weather service."}

    if response.status_code != 200:
        return {"error": "Could not fetch weather data for the selected city."}

    data = response.json()
    description = data["weather"][0]["description"]
    temp = round(data["main"]["temp"], 1)
    condition = _normalize_condition(description)

    weather_data = {
        "city": data["name"],
        "country": data.get("sys", {}).get("country"),
        "temperature": temp,
        "feels_like": round(data["main"].get("feels_like", temp), 1),
        "humidity": data["main"]["humidity"],
        "weather": description,
        "condition": condition,
        "wind_speed": round(data["wind"]["speed"] * 3.6, 1),
        "guidance": _weather_guidance(temp, condition),
    }

    return weather_data
