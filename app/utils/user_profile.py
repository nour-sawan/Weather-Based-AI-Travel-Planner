import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_FILE = os.path.join(APP_DIR, "data", "user_profile.json")

_DEFAULT_PROFILE = {
    "likes": [],
    "dislikes": [],
    "preferred_activity": None,
}


def _get_streamlit_session_state():
    """Return Streamlit's session_state if we're running inside a Streamlit
    app, otherwise None. Done as a soft import so this module still works
    unchanged for main.py's plain CLI usage, where there is no Streamlit
    session and per-file storage is the correct (and only) option.
    """
    try:
        import streamlit as st
    except ImportError:
        return None

    try:
        # st.session_state raises outside a real Streamlit run context
        return st.session_state
    except Exception:
        return None


def load_profile():
    # FIX: previously this always read/wrote a single shared JSON file at
    # PROFILE_FILE, with no per-user or per-session key anywhere. In the
    # Streamlit app, that means two people using the deployed app at the
    # same time overwrite each other's likes/dislikes — whoever clicks
    # "Generate" last wins for everyone. When running inside Streamlit,
    # keep the profile in st.session_state instead, which is already
    # isolated per browser session. Falls back to the shared file only
    # when there's no Streamlit session at all (e.g. main.py's CLI usage),
    # preserving the original behavior there.
    session_state = _get_streamlit_session_state()
    if session_state is not None:
        if "user_profile" not in session_state:
            session_state["user_profile"] = _load_profile_from_file()
        return session_state["user_profile"]

    return _load_profile_from_file()


def save_profile(profile):
    session_state = _get_streamlit_session_state()
    if session_state is not None:
        session_state["user_profile"] = profile
        return

    _save_profile_to_file(profile)


def update_profile(new_like=None, new_dislike=None):
    profile = load_profile()

    if new_like and new_like not in profile["likes"]:
        profile["likes"].append(new_like)

    if new_dislike and new_dislike not in profile["dislikes"]:
        profile["dislikes"].append(new_dislike)

    save_profile(profile)

    return profile


def _load_profile_from_file():
    if not os.path.exists(PROFILE_FILE):
        return dict(_DEFAULT_PROFILE)

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_profile_to_file(profile):
    os.makedirs(os.path.dirname(PROFILE_FILE), exist_ok=True)

    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=4)