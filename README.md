# 🤖 Training Coach Community — Multi-User KI-Trainingsplaner

Ein Telegram-Bot der als persönlicher Trainer fungiert. Du schickst ihm deine Leistungsdaten (TSS, CTL, HRV etc.) und er erstellt dir einen detaillierten Wochenplan mit konkreten Sessions, Aufwärmen, Übungen und Cooldown — individuell auf deine Sportarten, dein Fitnesslevel und das aktuelle Wetter abgestimmt.

Der Bot verbindet sich mit Suunto, Strava, COROS und Sigma-Uhren, holt Workout-Daten automatisch, zeigt Rad-Events in deiner Nähe, schlägt Komoot-Routen vor und erinnert dich sonntags an deinen neuen Plan. Mehrere User können den Bot gleichzeitig nutzen — jeder bekommt sein eigenes Profil.

Komplett kostenlos. Läuft auf Render, powered by Groq (Llama 3.3 70B).

## Was kann der Bot?

| Feature | Beschreibung | Quelle | Kosten |
|---------|-------------|--------|--------|
| 🤖 KI-Coach | Individuelle Wochenpläne mit konkreten Sessions | Groq (Llama 3.3 70B) | Kostenlos |
| ⌚ Suunto | Workouts + Schlaf + Recovery automatisch | Suunto Cloud API | Kostenlos |
| 🔗 Strava | Workouts automatisch abrufen | Strava API | Kostenlos |
| ⌚ COROS | Via Strava (direkte API wird beantragt) | Strava API | Kostenlos |
| 🚴 Sigma ROX | Via Strava (Sigma Ride → Strava) | Strava API | Kostenlos |
| 🌤️ Wetter | 7-Tage Vorhersage für deinen Standort | Open-Meteo | Kostenlos |
| 🚴 Rad-Events | RTF, CTF, Gravelrides in deiner Nähe | rad-net.de | Kostenlos |
| 🏊 Schwimmbäder | Öffnungszeiten Hannover | Lokale Daten | Kostenlos |
| �️ Routenvorschläge | Komoot-Links für Rad/Lauf im Plan | Komoot | Kostenlos |
| �📊 Schätzwerte | TSS/CTL/ATL/TSB zwischen den Plänen | Eigene Berechnung | — |
| 👥 Multi-User | Jeder User hat sein eigenes Profil | SQLite | — |
| 👥 Community | Anonymisierte Insights anderer Athleten | SQLite | — |
| ⏰ Reminders | Wöchentliche Erinnerung an /plan (So 18:00) | Eingebaut | — |
| 🔒 GDPR | Daten exportieren und löschen | Eingebaut | — |

## Befehle im Telegram-Chat

```
/start      — Bot starten / Profil einrichten
/plan       — Neuen Wochenplan erstellen
/checkin    — Midweek Check-in
/profil     — Dein Profil anzeigen
/sportarten — Sportarten ändern
/strava     — Strava verbinden
/suunto     — Suunto verbinden
/schwimmen  — Offene Bäder heute
/standort   — PLZ setzen (für lokales Wetter)
/anleitung  — Kurzanleitung anzeigen
/feedback   — Feedback geben
/export     — Alle deine Daten exportieren (GDPR)
/delete     — Alle deine Daten löschen (GDPR)
/reset      — Konversation zurücksetzen
/help       — Hilfe anzeigen
```

## Unterstützte Geräte

| Gerät | Anbindung | Wie verbinden? |
|-------|-----------|---------------|
| Suunto (alle Modelle) | Direkte API | /suunto im Chat |
| Garmin (alle Modelle) | Via Strava | Garmin Connect → Strava, dann /strava |
| COROS (alle Modelle) | Via Strava | COROS App → Strava, dann /strava |
| Sigma ROX | Via Strava | Sigma Ride App → Strava, dann /strava |
| Apple Watch | Via Strava | Strava App nutzen, dann /strava |
| Andere | Manuell | Daten bei /plan eingeben |

**Sigma ROX Hinweis**: Sigma hat keine öffentliche API. Verbinde die Sigma Ride App mit Strava (Einstellungen → Verbundene Apps → Strava), dann werden deine Fahrten automatisch synchronisiert.

## Installation (lokal)

### 1. Python installieren

Python 3.11 oder neuer. Download: https://www.python.org/downloads/

### 2. Abhängigkeiten installieren

```
pip install -r requirements.txt
playwright install chromium
```

### 3. `.env`-Datei einrichten

```
GROQ_API_KEY=dein_groq_api_key
TELEGRAM_BOT_TOKEN=dein_telegram_bot_token
STRAVA_CLIENT_ID=deine_strava_client_id
STRAVA_CLIENT_SECRET=dein_strava_client_secret
SUUNTO_CLIENT_ID=dein_suunto_client_id
SUUNTO_CLIENT_SECRET=dein_suunto_client_secret
SUUNTO_SUBSCRIPTION_KEY=dein_suunto_subscription_key
OAUTH_BASE_URL=http://localhost:5000
```

### 4. Starten

**Windows**: Doppelklick auf `start.bat` / `stop.bat`

**Manuell**:
```
python oauth_server.py   # Terminal 1
python bot.py             # Terminal 2
```

## Deployment (Render)

Siehe `DEPLOY.md` für die Schritt-für-Schritt Anleitung.

**Wichtig**: Render Free Tier schläft nach Inaktivität ein — die erste Antwort kann dann bis zu 50 Sekunden dauern. UptimeRobot pingt den Server alle 10 Minuten um das zu verhindern.

## Wie funktioniert's?

1. User schreibt `/start` → Datenschutz akzeptieren → Onboarding (Name, Uhr, Sportarten etc.)
2. User schreibt `/plan` → Bot fragt Leistungsdaten ab (TSS, CTL, HRV etc.)
3. User schickt die Daten → Bot erstellt detaillierten Wochenplan
4. Nach dem Plan: Wetter-Vorhersage und Rad-Events (wenn vorhanden) werden angezeigt
5. Zwischen den Plänen: Einfach Fragen stellen, Bot nutzt geschätzte Werte
6. Sonntag 18:00: Automatische Erinnerung an den neuen Wochenplan

Der Coach berücksichtigt automatisch das Wetter (kein Outdoor bei Regen), schlägt Rad-Events als Trainingseinheit vor und fügt bei Outdoor-Einheiten passende Komoot-Routenvorschläge ein.

## Dateien

| Datei | Was macht sie? |
|-------|---------------|
| `bot.py` | Telegram-Bot (Befehle, Nachrichten, Rate-Limiting) |
| `coach.py` | KI-Anbindung (Groq API, persistente History) |
| `database.py` | SQLite-Datenbank (User, Logs, Tokens, Schlaf, Recovery) |
| `onboarding.py` | Interaktives Profil-Setup mit Datenschutz-Zustimmung |
| `prompts.py` | System-Prompts + Community Insights |
| `suunto.py` | Suunto API (OAuth, Workouts, Schlaf, Recovery) |
| `strava.py` | Strava API (OAuth, Aktivitäten) |
| `oauth_server.py` | OAuth-Callback + Webhook-Server (HTTPS-fähig) |
| `estimator.py` | Schätzt TSS/CTL/ATL/TSB zwischen Plänen |
| `wetter.py` | Wetter-API (Open-Meteo, PLZ-basiert) |
| `rad_events.py` | Rad-Events Scraper (rad-net.de) |
| `schwimmbaeder.py` | Schwimmbad-Öffnungszeiten |
| `cache.py` | In-Memory Cache (Wetter 1h, Events 6h) |
| `start.bat` / `stop.bat` | Start/Stop für Windows |
| `Dockerfile` | Docker-Container für Render |
| `start_render.sh` | Start-Script für Render |

## Sicherheit

- Rate-Limiting: 20/User/Stunde, 25 global/Minute, 12.000/Tag
- OAuth: CSRF-Schutz mit kryptographischen State-Tokens
- Webhooks: HMAC-SHA256 Signaturverifikation
- SQL: Whitelist für Spaltennamen (kein SQL Injection)
- HTTPS: Automatisch via Render, HTTP→HTTPS Redirect
- Token-Verschlüsselung: Fernet (AES-128-CBC) wenn ENCRYPTION_KEY gesetzt
- GDPR: Datenschutz-Zustimmung beim Start, /export und /delete
- Input-Validierung: Längenlimits für alle Textfelder
