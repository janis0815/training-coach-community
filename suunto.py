import os
import time
import base64
import hmac
import hashlib
import logging
import httpx
from datetime import datetime, timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# --- Konstanten ---

SUUNTO_AUTH_URL = "https://cloudapi-oauth.suunto.com/oauth/authorize"
SUUNTO_TOKEN_URL = "https://cloudapi-oauth.suunto.com/oauth/token"
SUUNTO_API_URL = "https://cloudapi.suunto.com"

# Suunto Activity-ID → Sportart-Mapping (deutsch)
ACTIVITY_MAP = {
    1: "Sonstiges",
    2: "Multisport",
    3: "🏃 Laufen",
    4: "🚴 Radfahren",
    5: "🏊 Schwimmen",
    11: "🏃 Trail Running",
    15: "💪 Krafttraining",
    20: "🧘 Yoga",
    23: "🧗 Bouldern",
    24: "🧗 Klettern",
}

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


# --- Umgebungsvariablen ---

def _get_env(name: str) -> str:
    """Liest eine Umgebungsvariable oder loggt einen Fehler."""
    value = os.getenv(name)
    if not value:
        logger.error(f"Umgebungsvariable {name} ist nicht gesetzt! Bitte in .env konfigurieren.")
    return value or ""


def _get_client_id() -> str:
    return _get_env("SUUNTO_CLIENT_ID")


def _get_client_secret() -> str:
    return _get_env("SUUNTO_CLIENT_SECRET")


def _get_subscription_key() -> str:
    return _get_env("SUUNTO_SUBSCRIPTION_KEY")


# --- OAuth & Token-Management ---

def get_suunto_auth_link(chat_id: int, redirect_uri: str) -> str:
    """Generiert den Suunto OAuth2-Autorisierungslink mit chat_id als state."""
    client_id = _get_client_id()
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": str(chat_id),
    })
    return f"{SUUNTO_AUTH_URL}?{params}"


def _basic_auth_header() -> str:
    """Erstellt den Basic-Auth-Header (Base64 client_id:client_secret)."""
    client_id = _get_client_id()
    client_secret = _get_client_secret()
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def exchange_code_for_token(code: str, redirect_uri: str) -> dict | None:
    """Tauscht den Authorization Code gegen JWT-Tokens via Basic Auth.
    Gibt dict mit access_token, refresh_token, expires_in, user zurück."""
    try:
        resp = httpx.post(
            SUUNTO_TOKEN_URL,
            headers={"Authorization": _basic_auth_header()},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            # expires_at berechnen falls nur expires_in vorhanden
            if "expires_at" not in data and "expires_in" in data:
                data["expires_at"] = int(time.time()) + data["expires_in"]
            return data
        logger.error(f"Suunto Token-Austausch fehlgeschlagen: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Suunto Token-Austausch Fehler: {e}")
    return None


def refresh_access_token(refresh_token: str) -> dict | None:
    """Erneuert den Access Token mit dem Refresh Token via Basic Auth."""
    try:
        resp = httpx.post(
            SUUNTO_TOKEN_URL,
            headers={"Authorization": _basic_auth_header()},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            if "expires_at" not in data and "expires_in" in data:
                data["expires_at"] = int(time.time()) + data["expires_in"]
            return data
        logger.error(f"Suunto Token-Refresh fehlgeschlagen: {resp.status_code}")
    except Exception as e:
        logger.error(f"Suunto Token-Refresh Fehler: {e}")
    return None


def get_valid_token(
    access_token: str,
    refresh_token: str,
    expires_at: int,
    on_refresh: callable = None,
) -> str | None:
    """Gibt einen gültigen Access Token zurück, refresht bei Bedarf.
    Ruft on_refresh(token_data) auf wenn ein neuer Token geholt wurde."""
    if not access_token:
        return None

    # Token noch gültig?
    if expires_at > time.time():
        return access_token

    # Token abgelaufen → Refresh
    token_data = refresh_access_token(refresh_token)
    if token_data:
        if on_refresh:
            on_refresh(token_data)
        return token_data.get("access_token")

    return None


def _suunto_headers(access_token: str) -> dict:
    """Baut die erforderlichen Headers: Authorization + Ocp-Apim-Subscription-Key."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Ocp-Apim-Subscription-Key": _get_subscription_key(),
    }


def is_suunto_connected(access_token: str | None) -> bool:
    """Prüft ob gültige Suunto-Tokens vorliegen."""
    return bool(access_token)


# --- API-Aufrufe ---

def fetch_workouts(access_token: str, since_days: int = 7) -> list[dict] | None:
    """Holt Workouts der letzten N Tage von GET /v2/workouts."""
    since_ms = int((time.time() - since_days * 86400) * 1000)

    try:
        resp = httpx.get(
            f"{SUUNTO_API_URL}/v2/workouts",
            headers=_suunto_headers(access_token),
            params={"since": since_ms},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Suunto Workout-Abruf fehlgeschlagen: {resp.status_code}")
    except Exception as e:
        logger.error(f"Suunto Workout-Abruf Fehler: {e}")
    return None


# --- Formatierung ---

def format_workouts_for_coach(workouts: list[dict]) -> str:
    """Formatiert Suunto-Workouts als Text für den Coach-Prompt.
    Analoges Format wie format_activities_for_coach() in strava.py."""
    if not workouts:
        return "Keine Workouts bei Suunto gefunden."

    lines = ["📊 **Suunto-Daten der letzten Woche:**\n"]

    # Sortieren nach Startzeit
    workouts.sort(key=lambda w: w.get("startTime", 0))

    total_time = 0
    total_distance = 0

    for w in workouts:
        activity_id = w.get("activityId", 1)
        sport = ACTIVITY_MAP.get(activity_id, f"Aktivität ({activity_id})")

        duration_sec = w.get("totalTime", 0)
        duration_min = round(duration_sec / 60)
        distance_m = w.get("totalDistance", 0)
        distance_km = round(distance_m / 1000, 1)

        hr_data = w.get("hrdata", {})
        hr_avg = hr_data.get("workoutAvgHR", "-")
        hr_max = hr_data.get("workoutMaxHR", "-")

        # Wochentag aus startTime (Millisekunden-Timestamp)
        start_ms = w.get("startTime", 0)
        dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        weekday = WEEKDAYS[dt.weekday()]

        line = f"- **{weekday}** {sport}: {duration_min}min"
        if distance_km > 0:
            line += f", {distance_km}km"
        if hr_avg != "-":
            line += f", Ø{hr_avg}bpm"
        if hr_max != "-":
            line += f", max {hr_max}bpm"

        lines.append(line)

        total_time += duration_min
        total_distance += distance_km

    lines.append(f"\n**Gesamt:** {total_time}min, {total_distance}km")
    lines.append(f"\n*Hinweis: HRV, Schlaf und VO2max werden automatisch aus Suunto-Daten ergänzt.*")

    return "\n".join(lines)


def format_sleep_for_coach(sleep_data: list[dict]) -> str:
    """Formatiert Schlaf-Daten als Text für den Coach-Prompt."""
    if not sleep_data:
        return ""

    lines = ["😴 **Suunto Schlaf-Daten:**\n"]

    for entry in sleep_data:
        date = entry.get("date", "?")
        deep = entry.get("deep_sleep_min", 0)
        light = entry.get("light_sleep_min", 0)
        rem = entry.get("rem_sleep_min", 0)
        total = round(deep + light + rem)
        hr_avg = entry.get("hr_avg", "-")
        hr_min = entry.get("hr_min", "-")
        quality = entry.get("sleep_quality_score", "-")
        hrv = entry.get("avg_hrv", "-")

        lines.append(f"- **{date}**: {total}min gesamt (Tief: {deep}min, Leicht: {light}min, REM: {rem}min)")
        lines.append(f"  HR: Ø{hr_avg}, min {hr_min} | Qualität: {quality} | HRV: {hrv}")

    return "\n".join(lines)


def format_recovery_for_coach(recovery_data: list[dict]) -> str:
    """Formatiert Recovery-Daten als Text für den Coach-Prompt."""
    if not recovery_data:
        return ""

    lines = ["💚 **Suunto Recovery-Daten:**\n"]

    for entry in recovery_data:
        date = entry.get("date", "?")
        balance = entry.get("balance", "-")
        stress = entry.get("stress_state", "-")

        # Balance als Prozent anzeigen wenn numerisch
        if isinstance(balance, (int, float)):
            balance_str = f"{round(balance * 100)}%"
        else:
            balance_str = str(balance)

        lines.append(f"- **{date}**: Balance: {balance_str}, Stress: {stress}")

    return "\n".join(lines)


# --- Webhook-Verifikation ---

def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Prüft die HMAC-SHA256-Signatur einer Webhook-Benachrichtigung.
    Gibt False zurück wenn kein Secret konfiguriert ist."""
    if not secret:
        logger.error("Webhook-Verifikation fehlgeschlagen: kein Secret konfiguriert!")
        return False
    if not signature:
        return False
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
