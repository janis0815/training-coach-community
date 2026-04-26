# 📚 Training Coach Community — Technische Dokumentation

Ausführliche Dokumentation aller Features, Architektur, Sicherheitsmaßnahmen und Integrationen.

---

## Inhaltsverzeichnis

1. [Architektur](#architektur)
2. [Features im Detail](#features-im-detail)
3. [Integrationen](#integrationen)
4. [Datenbank](#datenbank)
5. [Sicherheit](#sicherheit)
6. [Rate-Limiting](#rate-limiting)
7. [GDPR / Datenschutz](#gdpr--datenschutz)
8. [KI-Coach System](#ki-coach-system)
9. [Onboarding-Flow](#onboarding-flow)
10. [Hosting & Deployment](#hosting--deployment)
11. [Dateistruktur](#dateistruktur)
12. [Umgebungsvariablen](#umgebungsvariablen)
13. [Bekannte Einschränkungen](#bekannte-einschränkungen)
14. [Roadmap](#roadmap)

---

## Architektur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Telegram User   │────▶│    bot.py         │────▶│   coach.py      │
│  (Smartphone)    │◀────│  (Commands,       │◀────│  (Groq LLM,     │
└─────────────────┘     │   Messages,       │     │   History)      │
                        │   Rate-Limiting)  │     └─────────────────┘
                        └──────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────┐   ┌──────────────┐  ┌──────────────┐
     │ database.py │   │ onboarding.py│  │  prompts.py  │
     │ (SQLite)    │   │ (Setup-Flow) │  │ (System-     │
     └──────┬─────┘   └──────────────┘  │  Prompts)    │
            │                            └──────────────┘
            │
     ┌──────┴──────────────────────────────────┐
     │           Externe Integrationen          │
     ├──────────────┬──────────────┬────────────┤
     │  suunto.py   │  strava.py   │ wetter.py  │
     │  (OAuth,     │  (OAuth,     │ (Open-     │
     │   Workouts,  │   Workouts)  │  Meteo)    │
     │   Sleep,     │              │            │
     │   Recovery)  │              │            │
     ├──────────────┼──────────────┼────────────┤
     │ rad_events.py│schwimmbaeder │ cache.py   │
     │ (Scraper)    │  .py (lokal) │ (TTL)      │
     └──────────────┴──────────────┴────────────┘

     ┌──────────────────────────────────────────┐
     │         oauth_server.py                   │
     │  (OAuth Callbacks + Suunto Webhooks)      │
     │  Port 5000, HTTPS via Render              │
     └──────────────────────────────────────────┘
```

Der Bot besteht aus zwei Prozessen:
- `bot.py` — Telegram-Bot (Polling)
- `oauth_server.py` — HTTP-Server für OAuth-Callbacks und Webhooks

Beide laufen in einem Docker-Container auf Render.

---

## Features im Detail

### 🤖 KI-Coach (coach.py + prompts.py)

- **Modelle**: Llama 3.3 70B (Wochenpläne) + Llama 3.1 8B (Chat)
- **Anbieter**: Groq (kostenlos, 14.400 Requests/Tag)
- **Conversation History**: Persistent in SQLite, überlebt Bot-Neustarts
- **History-Limits**: 20 Messages (Full Model), 10 Messages (Light Model)
- **Automatische Modell-Wahl**: Erkennt Trainingsdaten (TSS, CTL etc.) → volles Modell
- **Community Insights**: Anonymisierte Logs anderer User fließen in den Prompt ein

### 📊 Metriken-Schätzung (estimator.py)

Zwischen den Wochenplänen schätzt der Bot aktuelle Werte:
- **hrTSS-Berechnung**: Aus HR-Daten + Dauer der Suunto-Workouts
- **CTL/ATL**: Exponentiell gewichteter Durchschnitt (42/7 Tage)
- **TSB**: CTL minus ATL
- **Basis**: Letzte manuell eingegebene Werte + seitdem absolvierte Workouts
- **Kennzeichnung**: Immer als "Schätzwerte" markiert

### 🌤️ Wetter (wetter.py)

- **API**: Open-Meteo (kostenlos, kein API-Key)
- **Daten**: 7-Tage Vorhersage (Temperatur, Regen, Wind, Wetter-Code)
- **Outdoor-Score**: Bewertet jeden Tag als outdoor/bedingt/indoor
- **PLZ-basiert**: Geocoding über Open-Meteo API, Fallback Hannover
- **Cache**: 1 Stunde TTL
- **Regeln im Prompt**: Outdoor-Training nur an guten Tagen, Wind-Empfehlungen etc.

### 🚴 Rad-Events (rad_events.py)

- **Quelle**: rad-net.de Breitensportkalender (BDR)
- **Methode**: Playwright Headless-Browser Scraping
- **Daten**: RTF, CTF, Gravelrides mit Datum, Strecken, Entfernung, Verein
- **Filter**: PLZ + Umkreis (Standard 20km)
- **Cache**: 6 Stunden TTL
- **Integration**: Events werden dem Coach-Prompt hinzugefügt

### 🏊 Schwimmbäder (schwimmbaeder.py)

- **Daten**: 8 Hallenbäder + 6 Freibäder + 2 besondere Bäder in Hannover
- **Öffnungszeiten**: Pro Wochentag, inkl. Sonderzeiten (Frauen, Kinder)
- **Freibad-Saison**: 14.05. - 13.09.2026
- **Sanierungen**: Nord-Ost-Bad bis Frühjahr 2027 geschlossen

### ⏰ Scheduled Reminders

- **Zeitpunkt**: Sonntag 18:00 UTC
- **Empfänger**: Alle User mit abgeschlossenem Setup
- **Inhalt**: Erinnerung an /plan für den neuen Wochenplan

### 💬 Feedback-System

- **Befehl**: `/feedback Dein Text hier`
- **Speicherung**: In SQLite feedback-Tabelle
- **Längenlimit**: 500 Zeichen

---

## Integrationen

### ⌚ Suunto (suunto.py)

**Verbindung**: OAuth2 über Suunto Cloud API
- Auth-URL: `https://cloudapi-oauth.suunto.com/oauth/authorize`
- Token-URL: `https://cloudapi-oauth.suunto.com/oauth/token`
- API-URL: `https://cloudapi.suunto.com`
- Auth-Methode: Basic Auth (Base64 client_id:client_secret)
- Token-Ablauf: 24 Stunden, automatischer Refresh

**Daten per API-Abruf**:
- Workouts (Sportart, Dauer, Distanz, HR avg/max, Aufstieg/Abstieg)
- Activity-ID Mapping: Laufen (3), Radfahren (4), Schwimmen (5), Trail (11), Kraft (15), Yoga (20), Bouldern (23), Klettern (24)

**Daten per Webhook** (wenn konfiguriert):
- Schlaf: Tiefschlaf, Leichtschlaf, REM, HR, Qualitäts-Score, HRV
- Recovery: Balance, Stress-Level
- Workouts: Echtzeit-Benachrichtigung bei neuen Workouts
- Signatur: HMAC-SHA256 Verifikation

**Nicht verfügbar per API**: TSS, CTL, ATL, TSB, VO2max (nur in der Suunto App sichtbar)

### 🔗 Strava (strava.py)

**Verbindung**: OAuth2 über Strava API
- Auth-URL: `https://www.strava.com/oauth/authorize`
- Token-URL: `https://www.strava.com/oauth/token`
- API-URL: `https://www.strava.com/api/v3`
- Token-Ablauf: 6 Stunden, automatischer Refresh

**Daten**: Aktivitäten der letzten 7 Tage (Sportart, Dauer, Distanz, HR, Relative Effort)

**Geräte via Strava**: Garmin, COROS, Sigma ROX, Apple Watch — alle synchronisieren zu Strava

### ⌚ COROS

- Keine direkte API (wird beantragt)
- Aktuell: Via Strava (COROS App → Strava → Bot)

### 🚴 Sigma ROX

- Keine öffentliche API
- Via Strava (Sigma Ride App → Strava → Bot)

---

## Datenbank

SQLite-Datenbank unter `data/users.db`.

### Tabellen

**users** — Benutzerprofile
```
chat_id, name, sports, kraft_fokus, has_dog, dog_name, has_hangboard,
watch, data_source, strava_access_token, strava_refresh_token,
strava_token_expires, suunto_access_token, suunto_refresh_token,
suunto_token_expires, suunto_username, city, plz, umkreis,
setup_complete, setup_step, extra_notes, privacy_accepted
```

**training_logs** — Wochenpläne und Eingabedaten
```
id, chat_id, week_start, data_json, plan_json, created_at
```

**conversation_history** — Persistenter Chat-Verlauf
```
id, chat_id, role, content, created_at
```

**suunto_sleep_logs** — Schlaf-Daten (via Webhook)
```
id, chat_id, date, deep_sleep_min, light_sleep_min, rem_sleep_min,
hr_avg, hr_min, sleep_quality_score, avg_hrv, created_at
```

**suunto_recovery_logs** — Recovery-Daten (via Webhook)
```
id, chat_id, date, balance, stress_state, created_at
```

**suunto_webhook_workouts** — Webhook-Workouts
```
id, chat_id, workout_key, sport, duration_sec, distance_m,
hr_avg, hr_max, ascent_m, descent_m, created_at
```

**feedback** — User-Feedback
```
id, chat_id, text, created_at
```

### Migrationen

Neue Spalten und Tabellen werden automatisch beim Start angelegt (ALTER TABLE mit try/except, CREATE TABLE IF NOT EXISTS). Bestehende Daten bleiben erhalten.

---

## Sicherheit

### SQL Injection Schutz
- `update_user()` nutzt eine Whitelist erlaubter Spaltennamen (`_ALLOWED_USER_COLUMNS`)
- Alle Queries verwenden parametrisierte Statements (`?` Platzhalter)

### OAuth CSRF-Schutz
- State-Parameter: Kryptographisch sichere Tokens (`secrets.token_urlsafe(32)`)
- Einmalig verwendbar: Token wird nach Validierung gelöscht
- Fallback: Kompatibilität mit einfacher chat_id als State

### Webhook-Sicherheit
- HMAC-SHA256 Signaturverifikation für alle Suunto-Webhooks
- Leeres Secret = Webhook wird abgelehnt (nicht stillschweigend akzeptiert)
- Unbekannte Webhook-Typen werden ignoriert (HTTP 200)

### HTTPS
- Render terminiert SSL automatisch
- `REQUIRE_HTTPS=true`: Prüft `X-Forwarded-Proto` Header
- HTTP-Requests werden auf HTTPS umgeleitet (301)
- Optional: Eigene SSL-Zertifikate (`SSL_CERTFILE`, `SSL_KEYFILE`)

### Input-Validierung
- Name: max 50 Zeichen, darf nicht leer sein
- Hundename: max 30 Zeichen
- Kraft-Fokus: max 100 Zeichen
- Extra-Notizen: max 500 Zeichen
- PLZ: Strikte Regex `^\d{5}$`
- Feedback: max 500 Zeichen

### Token-Speicherung
- OAuth-Tokens in SQLite (Klartext — Verschlüsselung geplant)
- `.env` in `.gitignore` (wird nicht gepusht)
- Render Environment Variables (verschlüsselt)

---

## Rate-Limiting

Drei Ebenen zum Schutz der Groq API:

| Ebene | Limit | Fenster | Fehlermeldung |
|-------|-------|---------|---------------|
| Pro User | 20 Nachrichten | 1 Stunde | "Du sendest zu viele Nachrichten" |
| Global/Minute | 25 Requests | 1 Minute | "Server ist gerade ausgelastet" |
| Global/Tag | 12.000 Requests | 24 Stunden | "Tageslimit erreicht" |
| OAuth-Server | 5 Requests/IP | 1 Minute | HTTP 429 |

Groq Free Tier: 30 Requests/Minute, 14.400/Tag. Unsere Limits liegen bewusst darunter.

---

## GDPR / Datenschutz

### Datenschutz-Zustimmung
- Erster Schritt im Onboarding (vor Namenseingabe)
- User muss `ja` schreiben um fortzufahren
- `privacy_accepted` Flag in der Datenbank

### Datenexport
- `/export` — Exportiert alle User-Daten als JSON
- Enthält: Profil, Trainingspläne, Schlaf-/Recovery-Daten
- Tokens werden NICHT exportiert
- Bei großen Datenmengen: Als JSON-Datei gesendet

### Datenlöschung
- `/delete BESTÄTIGEN` — Löscht alle Daten unwiderruflich
- Betrifft: User-Profil, Training-Logs, Schlaf/Recovery, Webhooks, Conversation History
- Bestätigungsschritt verhindert versehentliches Löschen

### Drittanbieter
- Groq: Keine dauerhafte Speicherung der Nachrichten
- Suunto/Strava: Nur bei aktiver Verbindung, jederzeit trennbar
- Open-Meteo: Keine persönlichen Daten übermittelt (nur PLZ → Koordinaten)
- rad-net.de: Keine persönlichen Daten übermittelt (nur PLZ)
- Render: Hosting in der EU

---

## KI-Coach System

### System-Prompt (prompts.py)

Der Coach-Prompt enthält:
- Zonen-System: GA1/GA2/WSA (nie Zone 1/2/3)
- Wochentyp-Logik: TSB < -30 → DELOAD, stabil + HRV gut → BUILD, sonst BASE
- Muskelgruppen-Management: Konfliktvermeidung (Schwimmen+Klettern nie hintereinander)
- Session-Strukturen: Konkrete Übungen für jede Sportart
- Smart Adaptation: HRV sinkt → Recovery, Nase zu → kein Laufen
- Hund-Logik: Laufen immer GA1, Run/Walk Struktur
- Hangboard: Submaximal, 5-8min Micro-Sessions
- Kraft-Fokus: 70% Fokus-Bereich, 30% Ganzkörper

### Modell-Auswahl

| Situation | Modell | Max Tokens | History |
|-----------|--------|-----------|---------|
| Trainingsdaten erkannt (≥3 Keywords) | Llama 3.3 70B | 4.000 | 20 Messages |
| Nach /plan (nächste Nachricht) | Llama 3.3 70B | 4.000 | 20 Messages |
| Normaler Chat | Llama 3.1 8B | 800 | 10 Messages |

### Kontext-Anreicherung

Bei Wochenplänen wird der User-Input automatisch angereichert mit:
1. Schwimmbad-Öffnungszeiten (wenn Schwimmen in Sportarten)
2. Wetter-Vorhersage (PLZ-basiert) — Coach plant kein Outdoor bei schlechtem Wetter
3. Suunto Schlaf-/Recovery-Daten (wenn verbunden)
4. Rad-Events (wenn Radfahren + PLZ vorhanden) — Coach schlägt Events als Trainingseinheit vor
5. Geschätzte Metriken (wenn zwischen Plänen)
6. Community Insights (anonymisierte Logs anderer User)

### Plan-Flow

1. User schickt `/plan` → Bot zeigt Datenabfrage (Leistungsdaten, Training, Zustand, Wünsche)
2. User schickt die ausgefüllten Daten → Bot erstellt Plan mit vollem Modell
3. Nach dem Plan: Wetter-Vorhersage wird angezeigt
4. Nach dem Wetter: Rad-Events werden angezeigt (nur wenn welche gefunden werden)

Wetter und Events fließen in den Coach-Prompt ein — der Plan berücksichtigt sie bereits.

---

## Onboarding-Flow

```
/start
  └→ Datenschutz-Zustimmung (ja)
      └→ Name
          └→ Uhr-Auswahl (Suunto/Garmin/COROS/Apple Watch/Sigma/Keine)
              ├→ Keine Uhr → Manuell → Sportarten
              ├→ Suunto → Datenquelle (API/Strava) → Sportarten
              ├→ Garmin → Datenquelle (API*/Strava) → Sportarten
              ├→ COROS → Automatisch Strava → Sportarten
              ├→ Sigma → Automatisch Strava → Sportarten
              └→ Apple Watch → Datenquelle (Manuell/Strava) → Sportarten
                  └→ Sportarten (Multi-Select)
                      ├→ Radfahren? → PLZ für Events
                      ├→ Laufen? → Hund (Name/Nein)
                      ├→ Bouldern/Klettern? → Hangboard (Ja/Nein)
                      ├→ Krafttraining? → Fokus (Freitext)
                      └→ Extra-Notizen
                          └→ Profil-Summary + Kurzanleitung
```

*Garmin API: Platzhalter, noch nicht implementiert

---

## Hosting & Deployment

### Render (Produktion)

- **Plan**: Free Tier
- **Runtime**: Docker
- **Region**: Frankfurt (EU Central)
- **Prozesse**: Bot + OAuth-Server in einem Container (`start_render.sh`)
- **Health-Check**: `/health` Endpoint
- **Keep-Alive**: UptimeRobot pingt alle 10 Minuten
- **Auto-Deploy**: Bei jedem Push auf `main`

### Lokal (Entwicklung)

- **Windows**: `start.bat` / `stop.bat`
- **Manuell**: `python oauth_server.py` + `python bot.py`
- **Playwright**: `playwright install chromium` für Rad-Events

---

## Dateistruktur

```
training-coach-community/
├── bot.py                 # Telegram-Bot (Commands, Messages, Rate-Limiting)
├── coach.py               # Groq LLM (persistente History)
├── database.py            # SQLite (User, Logs, Tokens, Sleep, Recovery)
├── onboarding.py          # Interaktives Setup mit Datenschutz
├── prompts.py             # System-Prompts + Community Insights
├── estimator.py           # TSS/CTL/ATL/TSB Schätzung
├── suunto.py              # Suunto API (OAuth, Workouts, Webhooks)
├── strava.py              # Strava API (OAuth, Aktivitäten)
├── oauth_server.py        # OAuth-Callbacks + Webhooks (HTTPS)
├── wetter.py              # Open-Meteo Wetter-API
├── rad_events.py          # rad-net.de Scraper (Playwright)
├── schwimmbaeder.py       # Schwimmbad-Öffnungszeiten
├── cache.py               # In-Memory Cache mit TTL
├── requirements.txt       # Python-Dependencies
├── Dockerfile             # Docker-Container für Render
├── start_render.sh        # Start-Script für Render
├── render.yaml            # Render-Konfiguration
├── start.bat / stop.bat   # Windows Start/Stop
├── .env                   # Credentials (nicht im Repo)
├── .gitignore             # Ignorierte Dateien
├── README.md              # Kurzübersicht
├── DOCS.md                # Diese Dokumentation
├── DEPLOY.md              # Deployment-Anleitung
├── DATENSCHUTZ.md         # Datenschutzerklärung
└── data/
    └── users.db           # SQLite-Datenbank
```

---

## Umgebungsvariablen

| Variable | Pflicht | Beschreibung |
|----------|---------|-------------|
| `GROQ_API_KEY` | Ja | Groq LLM API Key |
| `TELEGRAM_BOT_TOKEN` | Ja | Telegram Bot Token |
| `STRAVA_CLIENT_ID` | Nein | Strava OAuth Client ID |
| `STRAVA_CLIENT_SECRET` | Nein | Strava OAuth Client Secret |
| `SUUNTO_CLIENT_ID` | Nein | Suunto OAuth Client ID |
| `SUUNTO_CLIENT_SECRET` | Nein | Suunto OAuth Client Secret |
| `SUUNTO_SUBSCRIPTION_KEY` | Nein | Suunto API Subscription Key |
| `SUUNTO_WEBHOOK_SECRET` | Nein | Suunto Webhook HMAC Secret |
| `OAUTH_BASE_URL` | Nein | OAuth Redirect Base-URL (Default: localhost:5000) |
| `OAUTH_HOST` | Nein | Server-Host (Default: localhost, Render: 0.0.0.0) |
| `OAUTH_PORT` | Nein | Server-Port (Default: 5000) |
| `REQUIRE_HTTPS` | Nein | HTTPS erzwingen (Default: false) |

---

## Bekannte Einschränkungen

- **SQLite auf Render**: Datenbank wird bei Redeploy zurückgesetzt (kein persistentes Filesystem im Free Tier)
- **Suunto API**: TSS, CTL, ATL, TSB, VO2max nicht per API verfügbar (nur in der App)
- **Garmin API**: Noch nicht implementiert (Platzhalter im Onboarding)
- **COROS API**: Beantragt, noch nicht genehmigt
- **Sigma**: Keine API, nur via Strava
- **Rad-Events Scraping**: Abhängig von rad-net.de HTML-Struktur, kann brechen
- **Tokens im Klartext**: OAuth-Tokens in SQLite nicht verschlüsselt
- **Render Spin-Down**: Free Tier schläft nach 15 Min Inaktivität ein (UptimeRobot als Workaround)

---

## Roadmap

- [ ] COROS direkte API-Integration (wenn genehmigt)
- [ ] Token-Verschlüsselung in der Datenbank
- [ ] Persistente Datenbank (Render Disk oder externe DB)
- [ ] Garmin API-Integration
- [ ] Multi-Sprache (Englisch)
- [ ] Web-Dashboard für Trainingsanalyse
- [ ] Telegram Inline-Keyboards für Onboarding
