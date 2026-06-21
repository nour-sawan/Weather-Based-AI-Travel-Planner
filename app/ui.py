import html
import os
import sys
import time

import geonamescache
import plotly.graph_objects as go
import streamlit as st

from agents.activity_agent import (
    _is_duplicate_venue,
    _venue_fingerprint,
    generate_activities,
)
from agents.evaluator_agent import evaluate_activity_with_llm
from agents.fallback_agent import generate_fallback
from services.weather_service import get_weather
from styles import APP_STYLES
from utils.user_profile import load_profile, save_profile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

st.set_page_config(
    page_title="Weather-Based Activity Planner",
    page_icon="🌍",
    layout="wide",
)

st.markdown(APP_STYLES, unsafe_allow_html=True)

st.markdown(
    '<div class="main-title">🌤️ Weather-Based Activity Planner</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">AI-powered activity suggestions based on weather data</div>',
    unsafe_allow_html=True,
)

gc = geonamescache.GeonamesCache()
countries_data = gc.get_countries()
cities_data = gc.get_cities()

st.sidebar.markdown(
    """<div class="sidebar-title">🌤️ Weather Activity Setup</div>""",
    unsafe_allow_html=True,
)

st.sidebar.markdown('<div class="section-title">COUNTRY</div>', unsafe_allow_html=True)
country_names = sorted([c["name"] for c in countries_data.values()])
country = st.sidebar.selectbox(
    "", country_names, index=None, placeholder="Select a country"
)
country_error_placeholder = st.sidebar.empty()

st.sidebar.markdown('<div class="section-title">CITY</div>', unsafe_allow_html=True)
country_code = None
if country:
    for code, data in countries_data.items():
        if data["name"] == country:
            country_code = code
            break

city_list = []
if country_code:
    city_list = sorted(
        c["name"] for c in cities_data.values() if c["countrycode"] == country_code
    )

city = st.sidebar.selectbox(
    "", city_list if city_list else [], index=None, placeholder="Select a city"
)
city_error_placeholder = st.sidebar.empty()

st.sidebar.markdown('<div class="section-title">PREFERENCES</div>', unsafe_allow_html=True)
like = st.sidebar.text_input(
    "💚 Your Interests ",
    placeholder="Food, Beaches, Museums",
)
dislike = st.sidebar.text_input(
    "💔 Your Exclusions",
    placeholder="Crowds, Hiking, Nightlife",
)
pref_error_placeholder = st.sidebar.empty()

st.sidebar.markdown("<hr>", unsafe_allow_html=True)
run = st.sidebar.button("✨ Generate My Plan")

if run:
    has_error = False

    if not country:
        country_error_placeholder.error("Please select a country")
        has_error = True
    else:
        country_error_placeholder.empty()

    if not city:
        city_error_placeholder.error("Please select a city")
        has_error = True
    else:
        city_error_placeholder.empty()

    if not like and not dislike:
        pref_error_placeholder.error("Please enter at least one preference")
        has_error = True
    else:
        pref_error_placeholder.empty()

    if has_error:
        st.stop()

    save_profile(
        {
            "likes": [x.strip() for x in like.split(",") if x.strip()] if like else [],
            "dislikes": [x.strip() for x in dislike.split(",") if x.strip()]
            if dislike
            else [],
            "preferred_activity": None,
        }
    )

    profile = load_profile()

    weather = get_weather(city, country_code)
    if weather.get("error"):
        st.error(weather["error"])
        st.stop()

    st.subheader("🌤 Weather Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("City", weather.get("city", city))
    c2.metric("Temp", f"{weather.get('temperature', 'N/A')} °C")
    c3.metric("Humidity", f"{weather.get('humidity', 'N/A')} %")
    c4.metric("Wind", f"{weather.get('wind_speed', 'N/A')} km/h")
    st.caption(
        f"Condition: {weather.get('condition', 'N/A')} "
        f"({weather.get('weather', 'N/A')}) · "
        f"Feels like {weather.get('feels_like', 'N/A')} °C"
    )
    if weather.get("guidance"):
        st.info(weather["guidance"])

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=weather.get("temperature", 0),
            title={"text": "Temperature"},
            gauge={"axis": {"range": [-10, 50]}},
        )
    )
    st.plotly_chart(fig, use_container_width=True)

    loading_box = st.empty()
    loading_box.markdown(
        """<div class="loading-box">🧠 AI is analyzing your preferences<span class="loading-dots"></span></div>""",
        unsafe_allow_html=True,
    )
    time.sleep(0.4)

    loading_box.markdown(
        """<div class="loading-box">🌤 Checking weather conditions<span class="loading-dots"></span></div>""",
        unsafe_allow_html=True,
    )
    time.sleep(0.4)

    activities = generate_activities(weather, city, profile)

    loading_box.markdown(
        """<div class="loading-box">🛡 Running safety evaluation<span class="loading-dots"></span></div>""",
        unsafe_allow_html=True,
    )

    if activities:
        evaluated = []

        for activity in activities:
            loading_box.markdown(f"🛡 Evaluating: {activity.get('name', 'activity')}")

            result = evaluate_activity_with_llm(activity, profile, weather) or {}

            if result.get("approved"):
                activity["score"] = result.get("final_score", activity.get("score", 7))
                activity["reasoning"] = result.get("reasoning") or activity.get("why", "")
                evaluated.append(activity)
            else:
                fallback = generate_fallback(activity, profile, weather, city=city)

                if not isinstance(fallback, dict):
                    continue

                # FIX: previously the fallback's score/reasoning were taken
                # from `result` — the evaluation of the ORIGINAL rejected
                # activity, not the new fallback content. That caused
                # mismatched cards: a brand-new fallback activity displayed
                # with a stale rejection reason (e.g. "too generic") that
                # had nothing to do with the fallback's actual name/content.
                # Fix: re-evaluate the fallback itself, and only fall back
                # to its own `why`/`score` if a second evaluation can't be
                # obtained for some reason.
                fallback_result = evaluate_activity_with_llm(fallback, profile, weather) or {}

                if fallback_result:
                    fallback["score"] = fallback_result.get(
                        "final_score", fallback.get("score", 6)
                    )
                    fallback["reasoning"] = (
                        fallback_result.get("reasoning")
                        or fallback.get("why", "Adjusted to match your constraints.")
                    )
                else:
                    fallback["score"] = fallback.get("score", 6)
                    fallback["reasoning"] = fallback.get(
                        "why", "Adjusted to match your constraints."
                    )

                # Only show fallbacks that themselves pass evaluation (or
                # at least weren't hard-rejected) and clear a minimum
                # quality bar. A fallback that ALSO fails evaluation
                # shouldn't be shown as a "recommended" experience.
                if fallback_result.get("approved", True) and fallback["score"] >= 5:
                    evaluated.append(fallback)

        loading_box.markdown(" Ranking best experiences...")
        evaluated = sorted(evaluated, key=lambda x: x.get("score", 0), reverse=True)

        # FIX: activity_agent.filter_activities() only de-dupes within the
        # initial LLM batch. It can't see fallbacks generated later in
        # app.py's evaluation loop, and generate_fallback() has no
        # awareness of other fallbacks or already-accepted activities
        # either. Two independently-rejected activities can each get
        # replaced with the same fallback venue (confirmed in production:
        # "Palau de la Música Catalana" appeared twice, both as fallbacks).
        # Re-run the same fingerprint-based de-dup here, over the FULL
        # final list, after sorting by score so the higher-scored copy
        # of any duplicate is the one kept.
        deduped = []
        seen_fingerprints: list[str] = []
        for item in evaluated:
            fingerprint = _venue_fingerprint(item.get("name", ""))
            if _is_duplicate_venue(fingerprint, seen_fingerprints):
                continue
            seen_fingerprints.append(fingerprint)
            deduped.append(item)
        evaluated = deduped

        top = evaluated[:10]

        loading_box.markdown(
            """<div class="loading-box">✨ Finalizing your personalized travel experience...</div>""",
            unsafe_allow_html=True,
        )
        time.sleep(0.4)
        loading_box.success("Your plan is ready!")

        if not top:
            st.warning(
                "No activities passed our quality and safety checks. "
                "Try adjusting your preferences or selecting a different city."
            )
        else:
            st.subheader("🎯 Recommended Experiences")

            cols = st.columns(2)
            for i, activity in enumerate(top):
                place_name = html.escape(str(activity.get("name", "Unknown Activity")))
                activity_type = activity.get("type", "Relax")
                score = activity.get("score", 0)
                time_of_day = activity.get("time_of_day", "N/A")
                reasoning = html.escape(
                    str(activity.get("reasoning") or activity.get("why", ""))
                )
                location = html.escape(str(activity.get("location", "")))

                if score >= 9:
                    accent = "#22c55e"
                elif score >= 8:
                    accent = "#3b82f6"
                else:
                    accent = "#f97316"

                type_key = str(activity_type).lower()
                if type_key == "outdoor":
                    icon = "🏃‍♂️"
                elif type_key == "indoor":
                    icon = "🏛️"
                else:
                    icon = "☕"

                with cols[i % 2]:
                    st.markdown(
                        f"""
<div class="activity-card" style="border-left:5px solid {accent}; padding:15px; border-radius:12px; margin-bottom:15px;">
    <h3>{icon} {place_name}</h3>
    <div>📍 {location}</div>
    <div class="type">Type: {activity_type} · {str(time_of_day).title()}</div>
    <div class="score">🔥 Score: {score} / 10</div>
    <p style="opacity:0.8">{reasoning}</p>
</div>
""",
                        unsafe_allow_html=True,
                    )
    else:
        st.warning("No activities generated. Try another city or adjust your preferences.")

else:
    st.markdown(
        """
<div class="empty-state">
    <div class="emoji">🧭</div>
    <div class="title">Your Weather-Based Plan</div>
    <div class="subtitle">Select a destination from the sidebar, then generate your personalized activities.</div>
</div>
""",
        unsafe_allow_html=True,
    )