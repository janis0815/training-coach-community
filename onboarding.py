import re
from database import AVAILABLE_SPORTS, get_user, update_user

# Input-Validierung: Längenlimits
MAX_NAME_LENGTH = 50
MAX_DOG_NAME_LENGTH = 30
MAX_KRAFT_FOKUS_LENGTH = 100
MAX_EXTRA_NOTES_LENGTH = 500

SPORT_EMOJIS = {
    "laufen": "🏃", "radfahren": "🚴", "bouldern": "🧗", "seilklettern": "🧗",
    "schwimmen": "🏊", "krafttraining": "💪", "crossfit": "🏋️", "yoga": "🧘",
    "meditation": "🧠", "faszienrolle": "🔵",
}

SPORT_LABELS = {
    "laufen": "Laufen (Trail & Straße)",
    "radfahren": "Radfahren (Gravel, Rennrad, MTB, Enduro)",
    "bouldern": "Bouldern",
    "seilklettern": "Seilklettern",
    "schwimmen": "Schwimmen",
    "krafttraining": "Krafttraining",
    "crossfit": "CrossFit (Kurse)",
    "yoga": "Yoga",
    "meditation": "Meditation",
    "faszienrolle": "Faszienrolle",
}

WATCH_OPTIONS = {"1": "suunto", "2": "garmin", "3": "coros", "4": "apple_watch", "5": "sigma", "6": "manuell"}

WATCH_LABELS = {
    "suunto": "⌚ Suunto",
    "garmin": "⌚ Garmin",
    "coros": "⌚ COROS",
    "apple_watch": "⌚ Apple Watch",
    "sigma": "🚴 Sigma (ROX)",
    "manuell": "📝 Keine Uhr",
}

DATA_SOURCE_LABELS = {
    "manuell": "📝 Manuelle Eingabe",
    "api": "🔗 Direkte API",
    "suunto_api": "🔗 Suunto API",
    "strava": "🔗 Via Strava",
}


def get_setup_message(step: str, user: dict) -> str:
    if step == "privacy":
        return (
            "Hey! 👋 Willkommen beim Training Coach!\n\n"
            "Bevor wir loslegen, kurz zum Datenschutz:\n\n"
            "📋 Ich speichere deinen Namen, Sportarten und Trainingsdaten.\n"
            "🤖 Deine Nachrichten werden von einer KI (Groq) verarbeitet — nichts wird dort dauerhaft gespeichert.\n"
            "🔗 Suunto/Strava-Daten nur wenn du dich verbindest.\n"
            "🗑️ Du kannst jederzeit alles löschen mit /delete.\n"
            "📦 Deine Daten exportieren mit /export."
        )

    if step == "name":
        return "Cool! 🎉 Wie heißt du?"

    if step == "watch":
        return (
            f"Cool, {user['name']}! ⌚\n\n"
            "Welche Uhr/Tracker nutzt du?\n\n"
            "1. ⌚ Suunto\n"
            "2. ⌚ Garmin\n"
            "3. ⌚ COROS\n"
            "4. ⌚ Apple Watch\n"
            "5. 🚴 Sigma (ROX Fahrradcomputer)\n"
            "6. 📝 Keine Uhr / anderer Tracker\n\n"
            "Schick mir die Nummer."
        )

    if step == "data_mode":
        return (
            "📊 Wie möchtest du deine Trainingsdaten pflegen?\n\n"
            "1. 📝 **Manuell** — Ich frage dich jede Woche nach deinen Daten\n"
            "2. 🔗 **Automatisch** — Daten werden automatisch abgerufen\n\n"
            "Schick mir die Nummer."
        )

    if step == "data_source_suunto":
        return (
            "🔗 Wie sollen deine Suunto-Daten abgerufen werden?\n\n"
            "1. 🔗 Suunto API — Direkt von Suunto\n"
            "2. 🔗 Via Strava — Suunto synchronisiert zu Strava\n\n"
            "Schick mir die Nummer."
        )

    if step == "data_source_garmin":
        return (
            "🔗 Wie sollen deine Garmin-Daten abgerufen werden?\n\n"
            "1. 🔗 **Garmin API** — Direkt von Garmin Connect (wird eingerichtet sobald verfügbar)\n"
            "2. 🔗 **Via Strava** — Garmin synchronisiert zu Strava, wir holen die Daten dort\n\n"
            "Schick mir die Nummer."
        )

    if step == "data_source_apple":
        return (
            "🍎 Apple Watch hat leider keine direkte API.\n\n"
            "Deine Optionen:\n"
            "1. 📝 **Manuell** — Ich frage dich jede Woche\n"
            "2. 🔗 **Via Strava** — Wenn du Strava nutzt, synchronisiert die Apple Watch automatisch dorthin\n\n"
            "Schick mir die Nummer."
        )

    if step == "sports":
        sport_list = "\n".join(
            f"{i+1}. {SPORT_EMOJIS[s]} {SPORT_LABELS[s]}" for i, s in enumerate(AVAILABLE_SPORTS)
        )
        return (
            f"Welche Sportarten machst du? Nummern mit Komma:\n"
            f"z.B. `1, 3, 5, 7`\n\n{sport_list}"
        )

    if step == "dog":
        return (
            "🐕 Hast du einen Hund, mit dem du laufen gehst?\n\n"
            "Wenn ja, schreib den Namen (z.B. `Luna`).\n"
            "Wenn nein, schreib `nein`."
        )

    if step == "hangboard":
        return (
            "🤏 Hast du ein Hangboard zuhause?\n\n"
            "Damit kann ich dir kurze Finger-Kraft Sessions für Bildschirmpausen einbauen.\n"
            "Schreib `ja` oder `nein`."
        )

    if step == "kraft_fokus":
        return (
            "💪 Worauf willst du beim Krafttraining den Fokus legen?\n\n"
            "Beispiele:\n"
            "- `Beine` (Schnellkraft, Power)\n"
            "- `Oberkörper` (Brust, Rücken, Schultern)\n"
            "- `Ganzkörper` (ausgewogen)\n"
            "- `Core` (Rumpfstabilität)\n"
            "- Oder was Eigenes, z.B. `Beine + Schultern`"
        )

    if step == "extra":
        return (
            "📝 Gibt es noch etwas, das ich wissen sollte?\n\n"
            "z.B. Verletzungen, Einschränkungen, Ziele, Wettkämpfe...\n"
            "Wenn nichts, schreib `nein`."
        )

    if step == "plz":
        return (
            "🚴 Du fährst Rad! Soll ich dir Rad-Events (RTF, CTF, Gravelrides) in deiner Nähe vorschlagen?\n\n"
            "Wenn ja, schick mir deine **PLZ** (z.B. `30171`).\n"
            "Wenn nein, schreib `nein`."
        )

    return ""


def _next_step_after_sports(user: dict) -> str:
    if "radfahren" in user["sports"]:
        return "plz"
    if "laufen" in user["sports"]:
        return "dog"
    if any(s in user["sports"] for s in ["bouldern", "seilklettern"]):
        return "hangboard"
    if "krafttraining" in user["sports"]:
        return "kraft_fokus"
    return "extra"


def _next_step_after_plz(user: dict) -> str:
    if "laufen" in user["sports"]:
        return "dog"
    if any(s in user["sports"] for s in ["bouldern", "seilklettern"]):
        return "hangboard"
    if "krafttraining" in user["sports"]:
        return "kraft_fokus"
    return "extra"


def _next_step_after_dog(user: dict) -> str:
    if any(s in user["sports"] for s in ["bouldern", "seilklettern"]):
        return "hangboard"
    if "krafttraining" in user["sports"]:
        return "kraft_fokus"
    return "extra"


def _next_step_after_hangboard(user: dict) -> str:
    if "krafttraining" in user["sports"]:
        return "kraft_fokus"
    return "extra"


def process_setup_input(user: dict, text: str) -> tuple[str, bool]:
    """Verarbeitet User-Input im Setup. Returns (Antwort, setup_fertig)."""
    step = user["setup_step"]
    chat_id = user["chat_id"]

    if step == "privacy":
        if text.strip().lower() == "ja":
            update_user(chat_id, privacy_accepted=1, setup_step="name")
            return get_setup_message("name", user), False
        return "Bitte schreib `ja` um den Datenschutzhinweis zu akzeptieren.", False

    if step == "name":
        name = text.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return f"❌ Bitte einen Namen eingeben (max {MAX_NAME_LENGTH} Zeichen).", False
        update_user(chat_id, name=name, setup_step="watch")
        user["name"] = name
        return get_setup_message("watch", user), False

    if step == "watch":
        choice = text.strip()
        if choice not in WATCH_OPTIONS:
            return "❌ Bitte schick mir eine Nummer (1-6).", False

        watch = WATCH_OPTIONS[choice]
        update_user(chat_id, watch=watch)
        user["watch"] = watch

        if watch == "manuell":
            # Keine Uhr → direkt manuell, weiter zu Sportarten
            update_user(chat_id, data_source="manuell", setup_step="sports")
            return (
                "👍 Kein Problem! Ich frage dich jede Woche nach deinen Daten.\n\n"
                + get_setup_message("sports", user)
            ), False
        else:
            # Hat eine Uhr → fragen ob manuell oder automatisch
            update_user(chat_id, setup_step="data_mode")
            return get_setup_message("data_mode", user), False

    if step == "data_mode":
        choice = text.strip()
        if choice not in ("1", "2"):
            return "❌ Bitte schick mir `1` oder `2`.", False

        if choice == "1":
            # Manuell gewählt
            update_user(chat_id, data_source="manuell", setup_step="sports")
            return (
                "👍 Alles klar, manuelle Eingabe!\n\n"
                + get_setup_message("sports", user)
            ), False
        else:
            # Automatisch → je nach Uhr unterschiedliche Optionen
            watch = user.get("watch", "manuell")
            if watch == "suunto":
                update_user(chat_id, setup_step="data_source_suunto")
                return get_setup_message("data_source_suunto", user), False
            elif watch == "garmin":
                update_user(chat_id, setup_step="data_source_garmin")
                return get_setup_message("data_source_garmin", user), False
            elif watch == "apple_watch":
                update_user(chat_id, setup_step="data_source_apple")
                return get_setup_message("data_source_apple", user), False
            elif watch == "coros":
                # COROS → direkt Strava empfehlen (API wird beantragt)
                update_user(chat_id, data_source="strava", setup_step="sports")
                return (
                    "⌚ COROS synchronisiert automatisch mit Strava!\n\n"
                    "Stelle sicher, dass in der COROS App unter Profil → Drittanbieter → Strava aktiviert ist.\n"
                    "Verbinde dann Strava mit /strava nach dem Setup.\n\n"
                    + get_setup_message("sports", user)
                ), False
            elif watch == "sigma":
                # Sigma hat keine API → Strava empfehlen
                update_user(chat_id, data_source="strava", setup_step="sports")
                return (
                    "🚴 Sigma ROX hat leider keine direkte API.\n\n"
                    "Aber: Verbinde die Sigma Ride App mit Strava, dann holen wir die Daten automatisch von dort!\n"
                    "In der Sigma Ride App: Einstellungen → Verbundene Apps → Strava aktivieren.\n"
                    "Verbinde dann Strava mit /strava nach dem Setup.\n\n"
                    + get_setup_message("sports", user)
                ), False

    if step == "data_source_suunto":
        choice = text.strip()
        if choice not in ("1", "2"):
            return "❌ Bitte schick mir `1` oder `2`.", False

        if choice == "1":
            import os
            from suunto import get_suunto_auth_link
            oauth_base = os.getenv("OAUTH_BASE_URL", "http://localhost:5000")
            auth_link = get_suunto_auth_link(chat_id, f"{oauth_base}/suunto/callback")
            update_user(chat_id, data_source="suunto_api", setup_step="sports")
            return (
                "🔗 Suunto API verbinden\n\n"
                "Klicke auf den Link und erlaube den Zugriff:\n\n"
                f"{auth_link}\n\n"
                "Danach kannst du das Fenster schließen und hierher zurückkommen.\n\n"
                + get_setup_message("sports", user)
            ), False
        else:
            update_user(chat_id, data_source="strava", setup_step="sports")
            return (
                "🔗 Strava-Anbindung wird eingerichtet! Stelle sicher, dass deine Suunto App mit Strava synchronisiert.\n"
                "Bis dahin frage ich dich manuell.\n\n"
                + get_setup_message("sports", user)
            ), False

    if step == "data_source_garmin":
        choice = text.strip()
        if choice not in ("1", "2"):
            return "❌ Bitte schick mir `1` oder `2`.", False

        if choice == "1":
            update_user(chat_id, data_source="api", setup_step="sports")
            return (
                "🔗 Garmin API wird eingerichtet! Sobald verfügbar, hole ich deine Daten automatisch.\n"
                "Bis dahin frage ich dich manuell.\n\n"
                + get_setup_message("sports", user)
            ), False
        else:
            update_user(chat_id, data_source="strava", setup_step="sports")
            return (
                "🔗 Strava-Anbindung wird eingerichtet! Stelle sicher, dass Garmin Connect mit Strava synchronisiert.\n"
                "Bis dahin frage ich dich manuell.\n\n"
                + get_setup_message("sports", user)
            ), False

    if step == "data_source_apple":
        choice = text.strip()
        if choice not in ("1", "2"):
            return "❌ Bitte schick mir `1` oder `2`.", False

        if choice == "1":
            update_user(chat_id, data_source="manuell", setup_step="sports")
            return (
                "👍 Manuelle Eingabe! Ich frage dich jede Woche.\n\n"
                + get_setup_message("sports", user)
            ), False
        else:
            update_user(chat_id, data_source="strava", setup_step="sports")
            return (
                "🔗 Strava-Anbindung wird eingerichtet! Stelle sicher, dass deine Apple Watch Workouts zu Strava synchronisiert werden.\n"
                "Bis dahin frage ich dich manuell.\n\n"
                + get_setup_message("sports", user)
            ), False

    if step == "sports":
        try:
            indices = [int(x.strip()) - 1 for x in text.split(",")]
            selected = [AVAILABLE_SPORTS[i] for i in indices if 0 <= i < len(AVAILABLE_SPORTS)]
        except (ValueError, IndexError):
            return "❌ Bitte schick mir die Nummern getrennt durch Komma, z.B. `1, 3, 5`", False

        if not selected:
            return "❌ Bitte wähle mindestens eine Sportart!", False

        update_user(chat_id, sports=selected)
        user["sports"] = selected

        next_step = _next_step_after_sports(user)
        update_user(chat_id, setup_step=next_step)
        return get_setup_message(next_step, user), False

    if step == "plz":
        if text.strip().lower() == "nein":
            update_user(chat_id, plz="")
        else:
            plz = text.strip()
            if not re.match(r"^\d{5}$", plz):
                return "❌ Bitte eine gültige 5-stellige PLZ eingeben, z.B. `30171`.", False
            update_user(chat_id, plz=plz)

        next_step = _next_step_after_plz(user)
        update_user(chat_id, setup_step=next_step)
        return get_setup_message(next_step, user), False

    if step == "dog":
        if text.strip().lower() == "nein":
            update_user(chat_id, has_dog=0, dog_name="")
        else:
            dog_name = text.strip()[:MAX_DOG_NAME_LENGTH]
            update_user(chat_id, has_dog=1, dog_name=dog_name)

        next_step = _next_step_after_dog(user)
        update_user(chat_id, setup_step=next_step)
        return get_setup_message(next_step, user), False

    if step == "hangboard":
        update_user(chat_id, has_hangboard=1 if text.strip().lower() == "ja" else 0)

        next_step = _next_step_after_hangboard(user)
        update_user(chat_id, setup_step=next_step)
        return get_setup_message(next_step, user), False

    if step == "kraft_fokus":
        fokus = text.strip()[:MAX_KRAFT_FOKUS_LENGTH]
        update_user(chat_id, kraft_fokus=fokus, setup_step="extra")
        return get_setup_message("extra", user), False

    if step == "extra":
        if text.strip().lower() != "nein":
            notes = text.strip()[:MAX_EXTRA_NOTES_LENGTH]
            update_user(chat_id, extra_notes=notes)
        update_user(chat_id, setup_complete=1, setup_step="done")
        return _build_profile_summary(chat_id), True

    return "", True


def _build_profile_summary(chat_id: int) -> str:
    user = get_user(chat_id)
    sports_str = ", ".join(f"{SPORT_EMOJIS.get(s, '')} {SPORT_LABELS.get(s, s)}" for s in user["sports"])

    # Tracking-Info zusammenbauen
    watch_label = WATCH_LABELS.get(user["watch"], "Keine Uhr")
    source_label = DATA_SOURCE_LABELS.get(user["data_source"], "Manuell")
    if user["watch"] == "manuell":
        tracking_str = "📝 Manuelle Eingabe"
    else:
        tracking_str = f"{watch_label} → {source_label}"

    summary = f"✅ **Profil erstellt, {user['name']}!**\n\n"
    summary += f"⌚ **Tracking:** {tracking_str}\n"
    summary += f"🏋️ **Sportarten:** {sports_str}\n"

    if user["has_dog"]:
        summary += f"🐕 **Hund:** {user['dog_name']}\n"
    if user["has_hangboard"]:
        summary += "🤏 **Hangboard:** Ja\n"
    if user["kraft_fokus"]:
        summary += f"💪 **Kraft-Fokus:** {user['kraft_fokus']}\n"
    if user["extra_notes"]:
        summary += f"📝 **Notizen:** {user['extra_notes']}\n"
    if user.get("plz"):
        summary += f"🚴 **Rad-Events:** PLZ {user['plz']}, Umkreis {user.get('umkreis', 20)}km\n"

    summary += (
        "\n⚡ *Dieser Bot läuft auf kostenlosen Servern — "
        "wenn du ihn eine Weile nicht benutzt hast, kann die erste Antwort bis zu 50 Sekunden dauern. Danach geht's flott!*\n\n"
        "**Befehle:**\n"
        "/plan — Neuen Wochenplan starten\n"
        "/checkin — Midweek Check-in\n"
        "/anleitung — Kurzanleitung\n"
        "/feedback — Feedback geben\n"
        "/help — Alle Befehle\n\n"
        "Los geht's! Schick /plan für deinen ersten Wochenplan 🚀"
    )
    return summary
