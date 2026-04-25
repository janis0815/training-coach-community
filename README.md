# 🤖 Training Coach Community — Multi-User KI-Trainingsplaner

Ein Telegram-Bot für mehrere User, der individuelle Wochenpläne erstellt. Mit Suunto- und Strava-Anbindung, Wetter, Rad-Events, Schwimmbädern und Community-Insights.

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
| 📊 Schätzwerte | TSS/CTL/ATL/TSB zwischen den Plänen | Eigene Berechnung | — |
| 👥 Multi-User | Jeder User hat sein eigenes Profil | SQLite | — |
| 👥 Community | Anonymisierte Insights anderer Athleten | SQLite | — |
| ⏰ Reminders | Wöchentliche Erinnerung an /plan (So 18:00) | Eingebaut | — |

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
/export     — Alle deine Daten exportieren (GDPR)
/delete     — Alle deine Daten löschen (GDPR)
/reset      — Konversation zurücksetzen
/help       — Hilfe anzeigen
```

## Installation

### 1. Python installieren

Python 3.11 oder neuer. Download: https://www.python.org/downloads/

### 2. Abhängigkeiten installieren

```
pip install -r requirements.txt
playwright install chromium
```

(`playwright` wird für das Rad-Events-Scraping benötigt)

### 3. `.env`-Datei einrichten

Erstelle oder bearbeite die `.env`-Datei:

```
GROQ_API_KEY=dein_groq_api_key
TELEGRAM_BOT_TOKEN=dein_telegram_bot_token

# Strava (optional)
STRAVA_CLIENT_ID=deine_strava_client_id
STRAVA_CLIENT_SECRET=dein_strava_client_secret

# Suunto (optional)
SUUNTO_CLIENT_ID=dein_suunto_client_id
SUUNTO_CLIENT_SECRET=dein_suunto_client_secret
SUUNTO_SUBSCRIPTION_KEY=dein_suunto_subscription_key
SUUNTO_WEBHOOK_SECRET=dein_suunto_webhook_secret

# OAuth Server URL (für Produktion ändern)
OAUTH_BASE_URL=http://localhost:5000
```

**Wo bekomme ich die Keys?**

- **Groq**: Kostenlos auf https://console.groq.com → API Keys
- **Telegram**: Schreib `/newbot` an @BotFather in Telegram
- **Strava**: https://www.strava.com/settings/api
- **Suunto**: https://apizone.suunto.com/profile (Partner Programm nötig)

### 4. Suunto einrichten (optional)

1. Geh zu https://apizone.suunto.com/profile
2. Subscribe zur "Developer API" → kopiere den Primary Key
3. Unter "OAuth Application Settings":
   - Redirect URI: `http://localhost:5000/suunto/callback`
   - Client ID kopieren
   - Client Secret vergeben
4. Alles in `.env` eintragen

### 5. Strava einrichten (optional)

1. Geh zu https://www.strava.com/settings/api
2. Erstelle eine App
3. Redirect URI: `http://localhost:5000/strava/callback`
4. Client ID + Secret in `.env` eintragen

## Starten

### Option A: Doppelklick (Windows)

- **Starten**: Doppelklick auf `start.bat`
- **Stoppen**: Doppelklick auf `stop.bat`

### Option B: Manuell

Terminal 1 (OAuth-Server):
```
python oauth_server.py
```

Terminal 2 (Bot):
```
python bot.py
```

## Wie funktioniert's?

1. User schreibt `/start` → Onboarding fragt Name, Uhr, Sportarten, etc.
2. User schreibt `/plan` → Bot holt Suunto/Strava-Daten, zeigt Wetter + Events
3. User ergänzt fehlende Daten (TSS, CTL, VO2max etc.)
4. Bot erstellt detaillierten Wochenplan mit konkreten Sessions
5. Zwischen den Plänen: Einfach Fragen stellen, Bot nutzt geschätzte Werte
6. Sonntag 18:00: Automatische Erinnerung an den neuen Wochenplan

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

## Dateien

| Datei | Was macht sie? |
|-------|---------------|
| `bot.py` | Telegram-Bot (Befehle, Nachrichten, Rate-Limiting) |
| `coach.py` | KI-Anbindung (Groq API, persistente History) |
| `database.py` | SQLite-Datenbank (User, Logs, Tokens, Schlaf, Recovery) |
| `onboarding.py` | Interaktives Profil-Setup |
| `prompts.py` | System-Prompts + Community Insights |
| `suunto.py` | Suunto API (OAuth, Workouts, Schlaf, Recovery) |
| `strava.py` | Strava API (OAuth, Aktivitäten) |
| `oauth_server.py` | OAuth-Callback + Webhook-Server |
| `estimator.py` | Schätzt TSS/CTL/ATL/TSB zwischen Plänen |
| `wetter.py` | Wetter-API (Open-Meteo, PLZ-basiert) |
| `rad_events.py` | Rad-Events Scraper (rad-net.de) |
| `schwimmbaeder.py` | Schwimmbad-Öffnungszeiten |
| `cache.py` | In-Memory Cache (Wetter 1h, Events 6h) |
| `start.bat` | Startet Bot + OAuth-Server (Windows) |
| `stop.bat` | Stoppt beides (Windows) |

## Sicherheit

- Rate-Limiting: 20/User/Stunde, 25 global/Minute, 12.000/Tag
- OAuth: CSRF-Schutz mit kryptographischen State-Tokens
- Webhooks: HMAC-SHA256 Signaturverifikation
- SQL: Whitelist für Spaltennamen (kein SQL Injection)
- GDPR: `/export` und `/delete` für User-Daten

## Unterschied zum Solo-Bot

| | Solo-Bot | Community-Bot |
|---|---------|--------------|
| User | 1 | Unbegrenzt |
| Datenbank | JSON-Dateien | SQLite |
| Strava | ❌ | ✅ |
| Wetter | ❌ | ✅ (PLZ-basiert) |
| Rad-Events | ❌ | ✅ |
| Webhooks | ❌ | ✅ (Suunto Sleep/Recovery) |
| Community Insights | ❌ | ✅ |
| Reminders | ❌ | ✅ (Sonntag 18:00) |
| GDPR | ❌ | ✅ (/export, /delete) |
