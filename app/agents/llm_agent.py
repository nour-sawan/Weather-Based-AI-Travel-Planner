import os
from openai import OpenAI
from dotenv import load_dotenv
from utils.user_profile import load_profile

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def explain_and_recommend(weather_data, activities):
    profile = load_profile()

    prompt = f"""
You are a personalized AI activity planner.

USER PROFILE:
Likes: {profile["likes"]}
Dislikes: {profile["dislikes"]}

WEATHER:
{weather_data}

ACTIVITIES:
{activities}

TASK:
1. Personalize recommendations based on user preferences
2. Avoid disliked activities
3. Rank best activities
4. Explain reasoning simply
5. Give final suggestion
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content