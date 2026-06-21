import requests

def get_places(city):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": city,
        "format": "json",
        "limit": 15
    }

    headers = {
        "User-Agent": "AI-Weather-App"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code != 200:
        return []

    data = response.json()

    places = []

    for i, item in enumerate(data):
        if "display_name" in item:
            places.append({
                "id": i,
                "name": item["display_name"].split(",")[0]
            })

    return places