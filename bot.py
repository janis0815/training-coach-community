import os
import time
import logging
from datetime import date
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from coach import CoachAI
from database import init_db, get_user, create_user, update_user, save_training_log, get_suunto_tokens, get_recent_suunto_sleep, get_recent_suunto_recovery, get_recent_logs, delete_user_data, export_user_data, get_all_active_users, save_feedback
from onboarding import get_setup_message, process_setup_input, AVAILABLE_SPORTS, SPORT_EMOJIS, SPORT_LABELS, WATCH_LABELS, DATA_SOURCE_LABELS
from prompts import build_full_prompt, build_chat_prompt, build_data_request, WEEKLY_CHECK_IN_PROMPT
from schwimmbaeder import get_offene_baeder, ist_freibad_saison, WOCHENTAGE
from strava import get_strava_auth_link, is_strava_connected, fetch_weekly_activities, format_activities_for_coach
from suunto import get_suunto_auth_link, is_suunto_connected as is_suunto_connected_fn, fetch_workouts as suunto_fetch_workouts, format_workouts_for_coach as suunto_format_workouts, format_sleep_for_coach, format_recovery_for_coach
from rad_events import scrape_events, get_events_for_week, format_events_for_bot, format_events_for_prompt
from wetter import fetch_weekly_weather, format_weather_for_bot, format_weather_for_prompt, geocode_plz, DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY
from estimator import parse_metrics_from_text, estimate_current_metrics, format_estimated_metrics

# Konfigurierbare OAuth-URL
OAUTH_BASE_URL = os.getenv("OAUTH_BASE_URL", "http://localhost:5000")
SUUNTO_REDIRECT_URI = f"{OAUTH_BASE_URL}/suunto/callback"

# Max Eingabelängen (Input-Validierung)
MAX_NAME_LENGTH = 50
MAX_NOTES_LENGTH = 500

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

coach = CoachAI(api_key=os.getenv("GROQ_API_KEY"))

# ── Rate-Limiting (3 Ebenen) ──────────────────────────────────────────

# 1. Pro User: max 20 Nachrichten pro Stunde
USER_RATE_LIMIT = 20
USER_RATE_WINDOW = 3600
_user_requests: dict[int, list[float]] = {}

# 2. Global: max 25 pro Minute (unter Groq's 30/min)
GLOBAL_RATE_LIMIT_PER_MIN = 25
_global_requests_min: list[float] = []

# 3. Global: max 12.000 pro Tag (unter Groq's 14.400/Tag)
GLOBAL_RATE_LIMIT_PER_DAY = 12000
_global_requests_day: list[float] = []


def _check_rate_limit(chat_id: int) -> str | None:
    """Prüft alle Rate-Limits. Gibt None zurück wenn OK, sonst eine Fehlermeldung."""
    now = time.time()

    # Global pro Minute
    _global_requests_min[:] = [t for t in _global_requests_min if now - t < 60]
    if len(_global_requests_min) >= GLOBAL_RATE_LIMIT_PER_MIN:
        return "⏳ Server ist gerade ausgelastet. Versuch es in einer Minute nochmal!"

    # Global pro Tag
    _global_requests_day[:] = [t for t in _global_requests_day if now - t < 86400]
    if len(_global_requests_day) >= GLOBAL_RATE_LIMIT_PER_DAY:
        return "⏳ Tageslimit erreicht. Versuch es morgen nochmal!"

    # Pro User
    if chat_id not in _user_requests:
        _user_requests[chat_id] = []
    _user_requests[chat_id] = [t for t in _user_requests[chat_id] if now - t < USER_RATE_WINDOW]
    if len(_user_requests[chat_id]) >= USER_RATE_LIMIT:
        return "⏳ Du sendest zu viele Nachrichten. Warte ein paar Minuten!"

    # Alles OK — Request zählen
    _user_requests[chat_id].append(now)
    _global_requests_min.append(now)
    _global_requests_day.append(now)
    return None


# Track welche User gerade auf /plan-Daten warten
_awaiting_plan_data: set[int] = set()


def _get_user_weather(user: dict) -> tuple[list[dict] | None, str]:
    """Holt Wetter für den User-Standort (PLZ oder Fallback Hannover)."""
    lat, lon, city = DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY
    plz = user.get("plz", "")
    if plz:
        geo = geocode_plz(plz)
        if geo:
            lat, lon, city = geo
    weather = fetch_weekly_weather(lat=lat, lon=lon, city=city)
    return weather, city


def _get_estimated_metrics(chat_id: int, user: dict) -> str:
    """Holt geschätzte Metriken aus letztem Plan + Suunto-Workouts seit dem letzten Plan."""
    try:
        logs = get_recent_logs(chat_id, limit=1)
        if not logs:
            return ""

        last_log = logs[0]
        last_data = last_log.get("data_json", "")
        last_metrics = parse_metrics_from_text(last_data)

        if not last_metrics.get("ctl") and not last_metrics.get("tss"):
            return ""  # Keine verwertbaren Daten im letzten Plan

        # Tage seit letztem Plan
        from datetime import datetime
        created = last_log.get("created_at", "")
        if created:
            try:
                last_date = datetime.fromisoformat(created.replace("Z", "+00:00"))
                days_since = (datetime.now() - last_date.replace(tzinfo=None)).days
            except (ValueError, TypeError):
                days_since = 7
        else:
            days_since = 7

        if days_since <= 0:
            return ""

        # Suunto-Workouts seit letztem Plan holen
        workouts = []
        if user.get("data_source") == "suunto_api":
            tokens = get_suunto_tokens(chat_id)
            if tokens and is_suunto_connected_fn(tokens.get("suunto_access_token")):
                from suunto import get_valid_token
                valid_token = get_valid_token(
                    tokens["suunto_access_token"],
                    tokens["suunto_refresh_token"],
                    tokens["suunto_token_expires"],
                    on_refresh=lambda td: update_user(chat_id,
                        suunto_access_token=td.get("access_token", ""),
                        suunto_refresh_token=td.get("refresh_token", ""),
                        suunto_token_expires=td.get("expires_at", 0)),
                )
                if valid_token:
                    workouts = suunto_fetch_workouts(valid_token, since_days=days_since) or []

        estimated = estimate_current_metrics(last_metrics, days_since, workouts)
        return format_estimated_metrics(estimated)
    except Exception as e:
        logger.warning(f"Metriken-Schätzung Fehler: {e}")
        return ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if user and user["setup_complete"]:
        await update.message.reply_text(
            f"Hey {user['name']}! 👋 Schön dich wiederzusehen!\n\n"
            "**Befehle:**\n"
            "/plan — Neuen Wochenplan\n"
            "/checkin — Midweek Check-in\n"
            "/profil — Dein Profil\n"
            "/sportarten — Sportarten ändern\n"
            "/strava — Strava verbinden\n"
            "/suunto — Suunto verbinden\n"
            "/schwimmen — Offene Bäder heute\n"
            "/standort — PLZ setzen (lokales Wetter)\n"
            "/reset — Konversation zurücksetzen\n\n"
            "Oder schreib mir einfach! 💬",
            parse_mode="Markdown",
        )
    else:
        create_user(chat_id)
        user = get_user(chat_id)
        msg = get_setup_message("privacy", user)
        await update.message.reply_text(msg, parse_mode="Markdown")


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    # User wartet jetzt auf Plan-Daten → nächste Nachricht immer mit vollem Modell
    _awaiting_plan_data.add(chat_id)

    # Strava verbunden? Daten automatisch holen!
    if user.get("data_source") == "strava" and is_strava_connected(chat_id):
        await update.message.reply_text("⏳ Hole deine Strava-Daten...")
        activities = fetch_weekly_activities(chat_id)

        if activities:
            strava_text = format_activities_for_coach(activities)
            await update.message.reply_text(
                f"{strava_text}\n\n"
                "📝 Bitte ergänze noch:\n"
                "- HRV 7d-Mittel:\n"
                "- Schlaf 7d-Mittel:\n"
                "- VO2max:\n"
                "- Nase/Gesundheit:\n"
                "- Wie fühlst du dich?\n"
                "- Wünsche für nächste Woche?\n\n"
                "Schick mir das und ich baue den Plan! 🚀",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "⚠️ Konnte keine Strava-Daten abrufen. Bitte manuell eingeben:\n\n"
                + build_data_request(user),
                parse_mode="Markdown",
            )

    # Suunto verbunden? Daten automatisch holen!
    elif user.get("data_source") == "suunto_api":
        tokens = get_suunto_tokens(chat_id)
        if tokens and is_suunto_connected_fn(tokens.get("suunto_access_token")):
            await update.message.reply_text("⏳ Hole deine Suunto-Daten...")
            try:
                from suunto import get_valid_token
                valid_token = get_valid_token(
                    tokens["suunto_access_token"],
                    tokens["suunto_refresh_token"],
                    tokens["suunto_token_expires"],
                    on_refresh=lambda td: update_user(chat_id,
                        suunto_access_token=td.get("access_token", ""),
                        suunto_refresh_token=td.get("refresh_token", ""),
                        suunto_token_expires=td.get("expires_at", 0)),
                )
                workouts = suunto_fetch_workouts(valid_token) if valid_token else None
            except Exception as e:
                logger.warning(f"Suunto Workout-Abruf Fehler: {e}")
                workouts = None

            if workouts:
                suunto_text = suunto_format_workouts(workouts)
                msg = f"{suunto_text}\n\n"

                # Schlaf-/Recovery-Daten aus DB
                sleep_data = get_recent_suunto_sleep(chat_id, days=7)
                recovery_data = get_recent_suunto_recovery(chat_id, days=7)
                if sleep_data:
                    msg += format_sleep_for_coach(sleep_data) + "\n\n"
                if recovery_data:
                    msg += format_recovery_for_coach(recovery_data) + "\n\n"

                msg += (
                    "📝 Bitte ergänze noch:\n"
                    "- VO2max:\n"
                    "- Nase/Gesundheit:\n"
                    "- Wie fühlst du dich?\n"
                    "- Wünsche für nächste Woche?\n\n"
                    "Schick mir das und ich baue den Plan! 🚀"
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "⚠️ Konnte keine Suunto-Daten abrufen. Bitte manuell eingeben:\n\n"
                    + build_data_request(user),
                    parse_mode="Markdown",
                )
        else:
            await update.message.reply_text(
                "⚠️ Suunto ist nicht verbunden. Verbinde mit /suunto oder gib manuell ein:\n\n"
                + build_data_request(user),
                parse_mode="Markdown",
            )

    else:
        data_request = build_data_request(user)
        await update.message.reply_text(data_request, parse_mode="Markdown")

    # Wetter anzeigen
    try:
        weather, city = _get_user_weather(user)
        if weather:
            await update.message.reply_text(format_weather_for_bot(weather, city), parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Wetter Fehler: {e}")

    # Rad-Events anzeigen wenn User Radfahren macht und PLZ hat
    if "radfahren" in user.get("sports", []) and user.get("plz"):
        try:
            from datetime import datetime, timedelta
            # Nächsten Montag als Wochenstart
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            next_sunday = next_monday + timedelta(days=6)

            await update.message.reply_text("🔍 Suche Rad-Events in deiner Nähe...")
            events = scrape_events(
                plz=user["plz"],
                umkreis=user.get("umkreis", 20),
                start_date=next_monday.strftime("%d.%m.%Y"),
                end_date=next_sunday.strftime("%d.%m.%Y"),
            )
            if events:
                week_events = get_events_for_week(events, next_monday)
                if week_events:
                    events_text = format_events_for_bot(week_events)
                    await update.message.reply_text(events_text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Rad-Events Fehler: {e}")


async def strava_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    if is_strava_connected(chat_id):
        await update.message.reply_text(
            "✅ Strava ist bereits verbunden!\n\n"
            "Deine Trainingsdaten werden automatisch abgerufen wenn du /plan nutzt."
        )
        return

    auth_link = get_strava_auth_link(chat_id)
    await update.message.reply_text(
        "🔗 **Strava verbinden**\n\n"
        "Klicke auf den Link, melde dich bei Strava an und erlaube den Zugriff:\n\n"
        f"[👉 Mit Strava verbinden]({auth_link})\n\n"
        "Danach kannst du dieses Fenster schließen und zurück hierher kommen.\n"
        "⚠️ Der Strava OAuth Server muss laufen (`python oauth_server.py`)",
        parse_mode="Markdown",
    )


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_chat.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    prompt = WEEKLY_CHECK_IN_PROMPT
    if user["has_dog"]:
        prompt += f"\n7. 🐕 **{user['dog_name']}**: Ruhig/normal/chaotisch?"

    await update.message.reply_text(prompt, parse_mode="Markdown")


async def suunto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)

    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    tokens = get_suunto_tokens(chat_id)
    if tokens and is_suunto_connected_fn(tokens.get("suunto_access_token")):
        await update.message.reply_text(
            "✅ Suunto ist verbunden!\n\n"
            "Deine Trainingsdaten werden automatisch abgerufen wenn du /plan nutzt."
        )
        return

    auth_link = get_suunto_auth_link(chat_id, SUUNTO_REDIRECT_URI)
    await update.message.reply_text(
        "🔗 **Suunto verbinden**\n\n"
        "Klicke auf den Link, melde dich bei Suunto an und erlaube den Zugriff:\n\n"
        f"[👉 Mit Suunto verbinden]({auth_link})\n\n"
        "Danach kannst du dieses Fenster schließen und zurück hierher kommen.\n"
        "⚠️ Der OAuth Server muss laufen (`python oauth_server.py`)",
        parse_mode="Markdown",
    )


async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    sports_str = ", ".join(f"{SPORT_EMOJIS.get(s, '')} {SPORT_LABELS.get(s, s)}" for s in user["sports"])
    text = f"👤 **Profil: {user['name']}**\n\n"
    text += f"⌚ **Tracking:** {WATCH_LABELS.get(user.get('watch', 'manuell'), 'Keine Uhr')}"
    if user.get('watch') != 'manuell':
        text += f" → {DATA_SOURCE_LABELS.get(user.get('data_source', 'manuell'), 'Manuell')}"
    text += "\n"

    # Strava Status
    if user.get("data_source") == "strava":
        if is_strava_connected(chat_id):
            text += "🔗 **Strava:** ✅ Verbunden\n"
        else:
            text += "🔗 **Strava:** ❌ Nicht verbunden (/strava zum Verbinden)\n"

    # Suunto Status
    if user.get("data_source") == "suunto_api":
        tokens = get_suunto_tokens(chat_id)
        if tokens and is_suunto_connected_fn(tokens.get("suunto_access_token")):
            text += "🔗 **Suunto:** ✅ Verbunden\n"
        else:
            text += "🔗 **Suunto:** ❌ Nicht verbunden (/suunto zum Verbinden)\n"

    text += f"🏋️ **Sportarten:** {sports_str}\n"

    if user["has_dog"]:
        text += f"🐕 **Hund:** {user['dog_name']}\n"
    if user["has_hangboard"]:
        text += "🤏 **Hangboard:** Ja\n"
    if user["kraft_fokus"]:
        text += f"💪 **Kraft-Fokus:** {user['kraft_fokus']}\n"
    if user["extra_notes"]:
        text += f"📝 **Notizen:** {user['extra_notes']}\n"

    text += "\nÄndern mit /sportarten"
    await update.message.reply_text(text, parse_mode="Markdown")


async def sportarten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_chat.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    update_user(update.effective_chat.id, setup_complete=0, setup_step="sports")
    sport_list = "\n".join(
        f"{i+1}. {SPORT_EMOJIS[s]} {SPORT_LABELS[s]}" for i, s in enumerate(AVAILABLE_SPORTS)
    )
    await update.message.reply_text(
        f"Welche Sportarten machst du jetzt? Nummern mit Komma:\n\n{sport_list}",
        parse_mode="Markdown",
    )


async def schwimmen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_chat.id)
    if user and "schwimmen" not in user.get("sports", []):
        await update.message.reply_text(
            "🏊 Schwimmen ist nicht in deinen Sportarten.\n"
            "Füge es mit /sportarten hinzu wenn du willst!"
        )
        return

    heute = date.today()
    wochentag = WOCHENTAGE[heute.weekday()]
    saison = "🏖️ Freibad-Saison aktiv!" if ist_freibad_saison(heute) else "❄️ Keine Freibad-Saison (14.05.-13.09.)"
    baeder = get_offene_baeder(wochentag, heute)

    await update.message.reply_text(
        f"🏊 **Bäder heute ({wochentag}):**\n\n{saison}\n\n{baeder}",
        parse_mode="Markdown",
    )


async def standort(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("Bitte zuerst /start um dein Profil einzurichten!")
        return

    # PLZ als Argument?
    import re
    args = update.message.text.split(maxsplit=1)
    if len(args) > 1:
        plz = args[1].strip()
        if re.match(r"^\d{5}$", plz):
            geo = geocode_plz(plz)
            if geo:
                lat, lon, city = geo
                update_user(chat_id, plz=plz)
                await update.message.reply_text(
                    f"📍 Standort gesetzt: {city} (PLZ {plz})\n"
                    f"Wetter wird jetzt für deinen Standort angezeigt!",
                )
            else:
                await update.message.reply_text("❌ Konnte die PLZ nicht auflösen. Versuch es nochmal.")
        else:
            await update.message.reply_text("❌ Bitte eine gültige 5-stellige PLZ, z.B. `/standort 30171`")
    else:
        current = user.get("plz", "")
        if current:
            geo = geocode_plz(current)
            city = geo[2] if geo else current
            await update.message.reply_text(
                f"📍 Dein Standort: {city} (PLZ {current})\n\n"
                f"Ändern mit `/standort 12345`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "📍 Kein Standort gesetzt.\n\n"
                "Setz deine PLZ mit `/standort 30171` — "
                "dann bekommst du lokales Wetter!",
                parse_mode="Markdown",
            )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    coach.reset(chat_id)
    _awaiting_plan_data.discard(chat_id)
    await update.message.reply_text("🔄 Konversation zurückgesetzt!")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Training Coach — Hilfe*\n\n"
        "📋 *Befehle:*\n"
        "/start — Bot starten / Willkommen\n"
        "/plan — Neuen Wochenplan erstellen\n"
        "/checkin — Midweek Check-in\n"
        "/profil — Dein Profil anzeigen\n"
        "/sportarten — Sportarten ändern\n"
        "/strava — Strava verbinden\n"
        "/suunto — Suunto verbinden\n"
        "/schwimmen — Offene Bäder heute\n"
        "/standort — PLZ setzen (für lokales Wetter)\n"
        "/export — Deine Daten exportieren\n"
        "/delete — Alle Daten löschen\n"
        "/anleitung — Anleitung nochmal anzeigen\n"
        "/feedback — Feedback geben\n"
        "/reset — Konversation zurücksetzen\n"
        "/help — Diese Hilfe\n\n"
        "💬 *Oder schreib mir einfach!*\n"
        "Ich kann Trainingsfragen beantworten, Tipps geben "
        "und deinen Wochenplan anpassen.",
        parse_mode="Markdown",
    )


async def anleitung(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Kurzanleitung*\n\n"
        "1️⃣ /plan — Schick mir deine Trainingsdaten und ich baue dir einen Wochenplan\n"
        "2️⃣ Zwischen den Plänen kannst du mir einfach Fragen stellen\n"
        "3️⃣ /checkin — Midweek Update, damit ich den Plan anpassen kann\n"
        "4️⃣ /suunto oder /strava — Verbinde deine Uhr für automatische Daten\n\n"
        "📱 *Geräte verbinden:*\n"
        "• Suunto → /suunto (direkte API)\n"
        "• Garmin → /strava (Garmin Connect → Strava)\n"
        "• COROS → /strava (COROS App → Strava)\n"
        "• Sigma ROX → /strava (Sigma Ride App → Strava)\n"
        "• Apple Watch → /strava (wenn Strava genutzt wird)\n\n"
        "⚡ *Gut zu wissen:*\n"
        "Dieser Bot läuft auf kostenlosen Servern. "
        "Wenn du ihn eine Weile nicht benutzt hast, schläft er ein — "
        "die erste Antwort kann dann bis zu 50 Sekunden dauern. "
        "Danach geht's wieder flott. 😊\n\n"
        "💤 Bot reagiert nicht? Öffne diesen Link im Browser zum Aufwecken:\n"
        "https://training-coach-community.onrender.com/health\n\n"
        "Sonntag 18:00 erinnere ich dich automatisch an deinen neuen Wochenplan!",
        parse_mode="Markdown",
    )


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user:
        await update.message.reply_text("Bitte zuerst /start!")
        return

    args = update.message.text.split(maxsplit=1)
    if len(args) > 1 and len(args[1].strip()) > 0:
        text = args[1].strip()[:500]
        save_feedback(chat_id, text)
        await update.message.reply_text("🙏 Danke für dein Feedback!")
    else:
        await update.message.reply_text(
            "💬 Schreib dein Feedback direkt hinter den Befehl:\n"
            "`/feedback Das und das finde ich gut/schlecht`",
            parse_mode="Markdown",
        )


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GDPR: Exportiert alle User-Daten als JSON."""
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user:
        await update.message.reply_text("Keine Daten vorhanden.")
        return

    import json as json_mod
    data = export_user_data(chat_id)
    export_text = json_mod.dumps(data, indent=2, ensure_ascii=False, default=str)

    if len(export_text) <= 4096:
        await update.message.reply_text(f"📦 Deine Daten:\n```\n{export_text}\n```", parse_mode="Markdown")
    else:
        # Als Datei senden
        from io import BytesIO
        file = BytesIO(export_text.encode("utf-8"))
        file.name = "meine_daten.json"
        await update.message.reply_document(document=file, caption="📦 Hier sind alle deine Daten.")


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GDPR: Löscht alle User-Daten nach Bestätigung."""
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if not user:
        await update.message.reply_text("Keine Daten vorhanden.")
        return

    # Prüfe ob Bestätigung mitgegeben wurde
    args = update.message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip().upper() == "BESTÄTIGEN":
        delete_user_data(chat_id)
        coach.reset(chat_id)
        _awaiting_plan_data.discard(chat_id)
        await update.message.reply_text(
            "🗑️ Alle deine Daten wurden gelöscht.\n"
            "Du kannst jederzeit mit /start neu anfangen."
        )
    else:
        await update.message.reply_text(
            "⚠️ Bist du sicher? Das löscht ALLE deine Daten unwiderruflich:\n"
            "- Profil und Einstellungen\n"
            "- Trainingspläne und Logs\n"
            "- Schlaf- und Recovery-Daten\n"
            "- Strava/Suunto-Verbindungen\n\n"
            "Zum Bestätigen schreib: `/delete BESTÄTIGEN`",
            parse_mode="Markdown",
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    user = get_user(chat_id)

    if not user:
        create_user(chat_id)
        user = get_user(chat_id)
        msg = get_setup_message("privacy", user)
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if not user["setup_complete"]:
        reply, done = process_setup_input(user, text)
        if done:
            _awaiting_plan_data.discard(chat_id)
        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply)
        return

    # Rate-Limiting (3 Ebenen: User, Global/Minute, Global/Tag)
    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    # Volles Modell wenn: nach /plan oder Trainingsdaten erkannt
    data_keywords = ["tss", "ctl", "atl", "tsb", "vo2", "hrv", "schlaf", "strava"]
    has_training_data = sum(1 for kw in data_keywords if kw in text.lower()) >= 3
    use_full = has_training_data or chat_id in _awaiting_plan_data

    if use_full:
        _awaiting_plan_data.discard(chat_id)
        full_prompt = build_full_prompt(user)
        enriched = f"{text}\n\n"

        if "schwimmen" in user["sports"]:
            heute = date.today()
            swim_tag = WOCHENTAGE[heute.weekday()]
            swim_info = get_offene_baeder(swim_tag, heute)
            enriched += f"[Schwimmbäder {swim_tag}: {swim_info}]\n"

        # Wetter in den Prompt einbauen
        try:
            weather, city = _get_user_weather(user)
            if weather:
                enriched += f"[{format_weather_for_prompt(weather, city)}]\n"
        except Exception as e:
            logger.warning(f"Wetter für Prompt: {e}")

        # Suunto Schlaf-/Recovery-Daten in den Prompt einbauen
        if user.get("data_source") == "suunto_api":
            try:
                tokens = get_suunto_tokens(chat_id)
                if tokens and is_suunto_connected_fn(tokens.get("suunto_access_token")):
                    sleep_data = get_recent_suunto_sleep(chat_id, days=7)
                    recovery_data = get_recent_suunto_recovery(chat_id, days=7)
                    if sleep_data:
                        enriched += f"[{format_sleep_for_coach(sleep_data)}]\n"
                    if recovery_data:
                        enriched += f"[{format_recovery_for_coach(recovery_data)}]\n"
            except Exception as e:
                logger.warning(f"Suunto-Daten für Prompt: {e}")

        # Rad-Events in den Prompt einbauen
        if "radfahren" in user.get("sports", []) and user.get("plz"):
            try:
                from datetime import datetime, timedelta
                today = datetime.now()
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                next_monday = today + timedelta(days=days_until_monday)
                next_sunday = next_monday + timedelta(days=6)
                events = scrape_events(
                    plz=user["plz"],
                    umkreis=user.get("umkreis", 20),
                    start_date=next_monday.strftime("%d.%m.%Y"),
                    end_date=next_sunday.strftime("%d.%m.%Y"),
                )
                week_events = get_events_for_week(events, next_monday)
                if week_events:
                    enriched += f"[{format_events_for_prompt(week_events)}]\n"
            except Exception as e:
                logger.warning(f"Rad-Events für Prompt: {e}")

        enriched += (
            "[ANWEISUNGEN:\n"
            "1. Wochentyp STRIKT nach TSB\n"
            "2. Muskelgruppen-Konflikte prüfen\n"
            "3. JEDE Session: Aufwärmen → Hauptteil → Cooldown mit konkreten Übungen\n"
            "4. Übersichtstabelle mit Muskelgruppen am Ende\n"
            "5. Wenn Rad-Events vorhanden: Vorschlagen als Trainingseinheit einzubauen]"
        )

        reply = coach.chat(chat_id, enriched, system_prompt=full_prompt, use_full_model=True)
        save_training_log(chat_id, str(date.today()), text, reply)
    else:
        chat_prompt = build_chat_prompt(user)

        # Geschätzte Metriken als Kontext mitgeben wenn verfügbar
        estimated = _get_estimated_metrics(chat_id, user)
        if estimated:
            enriched_text = f"{text}\n\n[{estimated}]"
            reply = coach.chat(chat_id, enriched_text, system_prompt=chat_prompt, use_full_model=False)
        else:
            reply = coach.chat(chat_id, text, system_prompt=chat_prompt, use_full_model=False)

    await _send_reply(update, reply)


async def _send_reply(update: Update, reply: str):
    """Sendet Antwort mit Markdown. Fällt auf Plain-Text zurück bei Parse-Fehlern."""
    chunks = [reply[i : i + 4096] for i in range(0, len(reply), 4096)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # Markdown-Parsing fehlgeschlagen → Plain-Text senden
            await update.message.reply_text(chunk)


async def weekly_plan_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Sendet wöchentliche Erinnerung an alle aktiven User (Sonntag 18:00)."""
    users = get_all_active_users()
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["chat_id"],
                text=(
                    f"Hey {user['name']}! 📅\n\n"
                    "Zeit für deinen neuen Wochenplan!\n"
                    "Schick mir /plan und ich erstelle dir einen Plan für nächste Woche. 💪"
                ),
            )
        except Exception as e:
            logger.warning(f"Reminder für {user['chat_id']} fehlgeschlagen: {e}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN nicht in .env gesetzt!")

    init_db()

    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("checkin", checkin))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CommandHandler("sportarten", sportarten))
    app.add_handler(CommandHandler("strava", strava_cmd))
    app.add_handler(CommandHandler("suunto", suunto_cmd))
    app.add_handler(CommandHandler("schwimmen", schwimmen))
    app.add_handler(CommandHandler("standort", standort))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("anleitung", anleitung))
    app.add_handler(CommandHandler("feedback", feedback_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Community Coach Bot gestartet! 🚀")

    # Wöchentlicher Reminder: Sonntag 18:00 Uhr
    from datetime import time as dt_time, timezone as tz
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_daily(
            weekly_plan_reminder,
            time=dt_time(hour=18, minute=0, tzinfo=tz.utc),
            days=(6,),  # 6 = Sonntag
            name="weekly_plan_reminder",
        )
        logger.info("Wöchentlicher Plan-Reminder eingerichtet (So 18:00 UTC)")

    app.run_polling()


if __name__ == "__main__":
    main()
