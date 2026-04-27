import logging
import httpx
from cache import cache

logger = logging.getLogger(__name__)

# Hannover Koordinaten (Standard-Fallback)
DEFAULT_LAT = 52.37
DEFAULT_LON = 9.73
DEFAULT_CITY = "Hannover"

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# WMO Weathercodes → lesbare Beschreibung + Emoji
WEATHER_CODES = {
    0: ("☀️", "Klar"),
    1: ("🌤️", "Überwiegend klar"),
    2: ("⛅", "Teilweise bewölkt"),
    3: ("☁️", "Bewölkt"),
    45: ("🌫️", "Nebel"),
    48: ("🌫️", "Nebel mit Reif"),
    51: ("🌦️", "Leichter Nieselregen"),
    53: ("🌦️", "Nieselregen"),
    55: ("🌧️", "Starker Nieselregen"),
    61: ("🌧️", "Leichter Regen"),
    63: ("🌧️", "Regen"),
    65: ("🌧️", "Starker Regen"),
    71: ("🌨️", "Leichter Schnee"),
    73: ("🌨️", "Schnee"),
    75: ("🌨️", "Starker Schnee"),
    80: ("🌦️", "Regenschauer"),
    81: ("🌧️", "Starke Regenschauer"),
    82: ("⛈️", "Heftige Regenschauer"),
    85: ("🌨️", "Schneeschauer"),
    95: ("⛈️", "Gewitter"),
    96: ("⛈️", "Gewitter mit Hagel"),
    99: ("⛈️", "Gewitter mit starkem Hagel"),
}


def geocode_plz(plz: str) -> tuple[float, float, str] | None:
    """PLZ → (lat, lon, ortsname) via Open-Meteo Geocoding. Cached für 30 Tage."""
    cache_key = f"geo_{plz}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": plz, "count": 10, "language": "de", "format": "json"},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            # Deutschland bevorzugen
            for r in results:
                if r.get("country_code", "").upper() == "DE":
                    result = (r["latitude"], r["longitude"], r.get("name", plz))
                    cache.set(cache_key, result, ttl_seconds=2592000)
                    return result
            # Fallback: erstes Ergebnis
            if results:
                r = results[0]
                result = (r["latitude"], r["longitude"], r.get("name", plz))
                cache.set(cache_key, result, ttl_seconds=2592000)
                return result
    except Exception as e:
        logger.warning(f"Geocoding für PLZ {plz} fehlgeschlagen: {e}")
    return None


def fetch_weekly_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, city: str = DEFAULT_CITY) -> list[dict] | None:
    """Holt 7-Tage Wettervorhersage von Open-Meteo. Cached für 1 Stunde."""
    cache_key = f"weather_{lat}_{lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode",
                "timezone": "Europe/Berlin",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"Open-Meteo error: {resp.status_code}")
            return None

        data = resp.json()["daily"]
        days = []
        for i in range(len(data["time"])):
            code = data["weathercode"][i]
            emoji, desc = WEATHER_CODES.get(code, ("❓", f"Code {code}"))
            days.append({
                "date": data["time"][i],
                "temp_max": data["temperature_2m_max"][i],
                "temp_min": data["temperature_2m_min"][i],
                "rain_mm": data["precipitation_sum"][i],
                "wind_kmh": data["windspeed_10m_max"][i],
                "code": code,
                "emoji": emoji,
                "description": desc,
                "outdoor_score": _calc_outdoor_score(
                    data["precipitation_sum"][i],
                    data["windspeed_10m_max"][i],
                    data["temperature_2m_max"][i],
                    code,
                ),
            })
        cache.set(cache_key, days, ttl_seconds=3600)
        return days

    except Exception as e:
        logger.error(f"Weather fetch error: {e}")
        return None


def _calc_outdoor_score(rain_mm: float, wind_kmh: float, temp_max: float, code: int) -> str:
    """Bewertet wie gut ein Tag für Outdoor-Training ist."""
    # Gewitter/Hagel → immer indoor
    if code >= 95:
        return "indoor"

    # Starker Regen (>5mm) oder starker Wind (>40km/h) → indoor
    if rain_mm > 5 or wind_kmh > 40:
        return "indoor"

    # Leichter Regen oder mäßiger Wind → bedingt outdoor
    if rain_mm > 1 or wind_kmh > 25:
        return "bedingt"

    # Kalt (<3°C) → bedingt
    if temp_max < 3:
        return "bedingt"

    # Hitze (>32°C) → bedingt (früh morgens oder abends)
    if temp_max > 32:
        return "bedingt"

    return "outdoor"


def format_weather_for_bot(days: list[dict], city: str = DEFAULT_CITY) -> str:
    """Formatiert Wetter für Telegram-Anzeige."""
    if not days:
        return ""

    from datetime import datetime

    lines = [f"🌤️ **Wetter diese Woche ({city}):**\n"]
    for day in days:
        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        weekday = WEEKDAYS[dt.weekday()]

        score_emoji = {"outdoor": "✅", "bedingt": "⚠️", "indoor": "❌"}.get(day["outdoor_score"], "❓")

        lines.append(
            f"{day['emoji']} **{weekday}** {day['description']} | "
            f"{day['temp_min']:.0f}-{day['temp_max']:.0f}°C | "
            f"💧{day['rain_mm']:.1f}mm | 💨{day['wind_kmh']:.0f}km/h | "
            f"Outdoor: {score_emoji}"
        )

    # Zusammenfassung
    outdoor_days = sum(1 for d in days if d["outdoor_score"] == "outdoor")
    indoor_days = sum(1 for d in days if d["outdoor_score"] == "indoor")
    lines.append(f"\n✅ {outdoor_days} gute Outdoor-Tage | ❌ {indoor_days} Indoor-Tage")

    return "\n".join(lines)


def format_weather_for_prompt(days: list[dict], city: str = DEFAULT_CITY) -> str:
    """Kompakte Wetter-Info für den Coach-Prompt."""
    if not days:
        return ""

    from datetime import datetime

    lines = [f"WETTER {city.upper()} (7-Tage Vorhersage):"]
    for day in days:
        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        weekday = WEEKDAYS[dt.weekday()]
        lines.append(
            f"- {weekday}: {day['description']}, {day['temp_min']:.0f}-{day['temp_max']:.0f}°C, "
            f"Regen {day['rain_mm']:.1f}mm, Wind {day['wind_kmh']:.0f}km/h → {day['outdoor_score'].upper()}"
        )

    lines.append(
        "\nREGELN FÜR WETTERANPASSUNG:"
        "\n- OUTDOOR (Laufen, Radfahren) nur an Tagen mit Score 'OUTDOOR' oder 'BEDINGT' planen"
        "\n- An INDOOR-Tagen: Schwimmen, Kraft, Bouldern, Yoga bevorzugen"
        "\n- Bei 'BEDINGT': Outdoor möglich aber Hinweis geben (z.B. Regenjacke, früh morgens bei Hitze)"
        "\n- Beste Outdoor-Tage für die längsten/wichtigsten Outdoor-Einheiten nutzen"
        "\n- Bei starkem Wind (>25km/h): Kein Rennrad, MTB im Wald oder Gravel bevorzugen"
        "\n- Bei Hitze (>30°C): Frühmorgens oder abends trainieren, Freibad vorschlagen"
    )
    return "\n".join(lines)
