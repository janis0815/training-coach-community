import os
import time
import logging
import httpx
from database import update_user, get_user

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_URL = "https://www.strava.com/api/v3"


def get_strava_auth_link(chat_id: int) -> str:
    """Generiert den Strava OAuth-Link für einen User."""
    client_id = os.getenv("STRAVA_CLIENT_ID")
    # State enthält die chat_id damit wir den User nach OAuth zuordnen können
    return (
        f"{STRAVA_AUTH_URL}"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri=http://localhost:5000/strava/callback"
        f"&scope=read,activity:read_all"
        f"&state={chat_id}"
    )


def exchange_code_for_token(code: str) -> dict | None:
    """Tauscht den OAuth-Code gegen Access + Refresh Token."""
    try:
        resp = httpx.post(STRAVA_TOKEN_URL, data={
            "client_id": os.getenv("STRAVA_CLIENT_ID"),
            "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
        })
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Strava token exchange failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Strava token exchange error: {e}")
    return None


def refresh_access_token(refresh_token: str) -> dict | None:
    """Erneuert den Access Token mit dem Refresh Token."""
    try:
        resp = httpx.post(STRAVA_TOKEN_URL, data={
            "client_id": os.getenv("STRAVA_CLIENT_ID"),
            "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Strava refresh failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Strava refresh error: {e}")
    return None


def save_strava_tokens(chat_id: int, token_data: dict):
    """Speichert Strava Tokens in der User-DB."""
    update_user(
        chat_id,
        strava_access_token=token_data["access_token"],
        strava_refresh_token=token_data["refresh_token"],
        strava_token_expires=token_data["expires_at"],
    )


def get_valid_token(chat_id: int) -> str | None:
    """Holt einen gültigen Access Token, refresht wenn nötig."""
    user = get_user(chat_id)
    if not user or not user.get("strava_access_token"):
        return None

    # Token abgelaufen? Refreshen
    if user.get("strava_token_expires", 0) < time.time():
        token_data = refresh_access_token(user["strava_refresh_token"])
        if token_data:
            save_strava_tokens(chat_id, token_data)
            return token_data["access_token"]
        return None

    return user["strava_access_token"]


def fetch_weekly_activities(chat_id: int, days: int = 7) -> list[dict] | None:
    """Holt die Aktivitäten der letzten X Tage von Strava."""
    token = get_valid_token(chat_id)
    if not token:
        return None

    after = int(time.time()) - (days * 86400)

    try:
        resp = httpx.get(
            f"{STRAVA_API_URL}/athlete/activities",
            headers={"Authorization": f"Bearer {token}"},
            params={"after": after, "per_page": 50},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Strava activities fetch failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Strava activities error: {e}")
    return None


def format_activities_for_coach(activities: list[dict]) -> str:
    """Formatiert Strava-Aktivitäten als Text für den Coach-Prompt."""
    if not activities:
        return "Keine Aktivitäten in Strava gefunden."

    SPORT_MAP = {
        "Run": "🏃 Laufen", "Trail Run": "🏃 Trail",
        "Ride": "🚴 Rad", "GravelRide": "🚴 Gravel", "MountainBikeRide": "🚴 MTB",
        "Swim": "🏊 Schwimmen",
        "WeightTraining": "💪 Kraft", "Workout": "💪 Training",
        "RockClimbing": "🧗 Klettern", "Bouldering": "🧗 Bouldern",
        "Yoga": "🧘 Yoga",
    }

    WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    lines = ["📊 **Strava-Daten der letzten Woche:**\n"]

    # Sortieren nach Datum
    activities.sort(key=lambda a: a["start_date"])

    total_time = 0
    total_distance = 0
    total_suffer = 0

    for act in activities:
        sport = SPORT_MAP.get(act.get("sport_type", ""), act.get("sport_type", "Aktivität"))
        duration_min = round(act.get("moving_time", 0) / 60)
        distance_km = round(act.get("distance", 0) / 1000, 1)
        hr_avg = act.get("average_heartrate", "-")
        suffer = act.get("suffer_score", 0) or 0

        # Wochentag
        from datetime import datetime
        dt = datetime.fromisoformat(act["start_date"].replace("Z", "+00:00"))
        weekday = WEEKDAYS[dt.weekday()]

        line = f"- **{weekday}** {sport}: {duration_min}min"
        if distance_km > 0:
            line += f", {distance_km}km"
        if hr_avg != "-":
            line += f", Ø{hr_avg}bpm"
        if suffer > 0:
            line += f", Relative Effort: {suffer}"

        lines.append(line)

        total_time += duration_min
        total_distance += distance_km
        total_suffer += suffer

    lines.append(f"\n**Gesamt:** {total_time}min, {total_distance}km, Relative Effort: {total_suffer}")
    lines.append(f"\n*Hinweis: HRV, Schlaf und VO2max bitte manuell ergänzen.*")

    return "\n".join(lines)


def is_strava_connected(chat_id: int) -> bool:
    """Prüft ob ein User Strava verbunden hat."""
    user = get_user(chat_id)
    return bool(user and user.get("strava_access_token"))
