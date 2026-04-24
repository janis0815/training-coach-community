"""
Schätzt aktuelle Trainingsmetriken (TSS, CTL, ATL, TSB) basierend auf
den letzten manuell eingegebenen Werten + seitdem absolvierten Workouts.

hrTSS-Formel (vereinfacht):
  hrTSS = (Dauer_min * HR_avg * IF) / (LTHR * 3600) * 100
  wobei IF = HR_avg / LTHR (Intensity Factor)
  LTHR geschätzt als 85% von HR_max (wenn nicht bekannt)

CTL = exponentiell gewichteter Durchschnitt über 42 Tage
ATL = exponentiell gewichteter Durchschnitt über 7 Tage
TSB = CTL - ATL
"""
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Standard-LTHR falls nicht bekannt (wird aus HR_max geschätzt)
DEFAULT_LTHR = 160


def estimate_workout_tss(duration_sec: int, hr_avg: int, hr_max: int = 0) -> float:
    """Schätzt TSS für ein einzelnes Workout basierend auf HR-Daten."""
    if duration_sec <= 0 or hr_avg <= 0:
        return 0

    # LTHR schätzen: 85% von HR_max, oder Default
    lthr = int(hr_max * 0.85) if hr_max > 100 else DEFAULT_LTHR

    duration_hours = duration_sec / 3600
    intensity_factor = hr_avg / lthr
    # hrTSS = Dauer(h) * IF^2 * 100
    tss = duration_hours * (intensity_factor ** 2) * 100
    return round(tss, 1)


def parse_metrics_from_text(text: str) -> dict:
    """Extrahiert TSS, CTL, ATL, TSB, VO2max, HRV, Schlaf aus Freitext.
    Gibt dict mit gefundenen Werten zurück (nur was gefunden wurde)."""
    metrics = {}

    patterns = {
        "tss": r"tss[:\s]*(\d+(?:\.\d+)?)",
        "ctl": r"ctl[:\s]*(\d+(?:\.\d+)?)",
        "atl": r"atl[:\s]*(\d+(?:\.\d+)?)",
        "tsb": r"tsb[:\s]*(-?\d+(?:\.\d+)?)",
        "vo2max": r"vo2(?:max)?[:\s]*(\d+(?:\.\d+)?)",
        "hrv": r"hrv[:\s]*(\d+(?:\.\d+)?)",
        "schlaf": r"schlaf[:\s]*(\d+(?:\.\d+)?)",
    }

    text_lower = text.lower()
    for key, pattern in patterns.items():
        match = re.search(pattern, text_lower)
        if match:
            metrics[key] = float(match.group(1))

    return metrics


def estimate_current_metrics(
    last_metrics: dict,
    days_since: int,
    workouts_since: list[dict],
) -> dict:
    """Berechnet geschätzte aktuelle Metriken basierend auf letzten Werten + neue Workouts.

    Args:
        last_metrics: Dict mit tss, ctl, atl, tsb, vo2max aus dem letzten Plan
        days_since: Tage seit dem letzten Plan
        workouts_since: Liste von Workout-Dicts mit duration_sec, hr_avg, hr_max

    Returns:
        Dict mit geschätzten aktuellen Werten + Kennzeichnung als Schätzwert
    """
    old_ctl = last_metrics.get("ctl", 50)
    old_atl = last_metrics.get("atl", 50)

    # TSS pro Tag aus neuen Workouts berechnen
    total_new_tss = 0
    for w in workouts_since:
        tss = estimate_workout_tss(
            w.get("duration_sec", w.get("totalTime", 0)),
            w.get("hr_avg", w.get("hrdata", {}).get("workoutAvgHR", 0) if isinstance(w.get("hrdata"), dict) else 0),
            w.get("hr_max", w.get("hrdata", {}).get("workoutMaxHR", 0) if isinstance(w.get("hrdata"), dict) else 0),
        )
        total_new_tss += tss

    # Täglicher Durchschnitts-TSS
    daily_tss = total_new_tss / max(days_since, 1)

    # CTL und ATL mit exponentieller Glättung aktualisieren
    # CTL: k = 2/(42+1), ATL: k = 2/(7+1)
    ctl = old_ctl
    atl = old_atl
    k_ctl = 2 / 43
    k_atl = 2 / 8

    for _ in range(days_since):
        ctl = ctl + k_ctl * (daily_tss - ctl)
        atl = atl + k_atl * (daily_tss - atl)

    tsb = ctl - atl

    result = {
        "tss_woche": round(total_new_tss, 1),
        "ctl": round(ctl, 1),
        "atl": round(atl, 1),
        "tsb": round(tsb, 1),
        "vo2max": last_metrics.get("vo2max", "?"),
        "ist_schaetzung": True,
    }

    return result


def format_estimated_metrics(metrics: dict) -> str:
    """Formatiert geschätzte Metriken als Text für den Coach-Prompt."""
    if not metrics or not metrics.get("ist_schaetzung"):
        return ""

    return (
        "📊 **Geschätzte aktuelle Werte** (basierend auf letztem Plan + Suunto-Workouts):\n"
        f"- TSS (Woche): ~{metrics['tss_woche']}\n"
        f"- CTL (Fitness): ~{metrics['ctl']}\n"
        f"- ATL (Ermüdung): ~{metrics['atl']}\n"
        f"- TSB (Form): ~{metrics['tsb']}\n"
        f"- VO2max: {metrics['vo2max']}\n"
        f"⚠️ *Dies sind Schätzwerte! Für genaue Werte schau in deine Suunto App.*"
    )
